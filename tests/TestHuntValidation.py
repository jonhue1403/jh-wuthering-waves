from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import numpy as np
from ok import TaskDisabledException

from src.overworld.controller import HuntAbort
from src.overworld.models import MapCoordinate
from src.overworld.navigation import NavigationResult, NavigationStatus
from src.overworld.navigation.player_locator import SurfaceProfile
from src.combat.CombatCheck import CombatCheck
from src.task.HuntMobTask import HuntMobTask
from src.task.WWOneTimeTask import WWOneTimeTask
from tests.TestHuntController import spawn


class TestHuntValidation(unittest.TestCase):
    def setUp(self):
        self.task = HuntMobTask(executor=Mock(), app=Mock())
        self.task.config = {**self.task.default_config, "Hunt Profile": "profile.json",
                            "Target Mob": "Target", "Localization Only": False,
                            "Test Walk Only": True}
        self.task.cancelled = Mock(return_value=False)
        self.task.in_combat = Mock(return_value=False)
        self.task.enemy_present = Mock(return_value=False)
        self.task.combat_once = Mock()
        self.profile = SurfaceProfile(
            Path("map.png"), Path("map.db"), "Target", 8, "", MapCoordinate(0, 0),
            1, (1920, 1080), frozenset({"a"}), localization_tolerance_pixels=1,
            localization_verified=True, test_walk_target=MapCoordinate(20, 20),
        )
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.input_access = self.stack.enter_context(
            patch("src.task.HuntMobTask.require_game_input_access"))
        self.load = self.stack.enter_context(patch("src.task.HuntMobTask.SurfaceProfile.load",
                                                  return_value=self.profile))
        self.stack.enter_context(patch("src.task.HuntMobTask.np.fromfile", return_value=np.zeros(1)))
        self.stack.enter_context(patch("src.task.HuntMobTask.cv2.imdecode",
                                      return_value=np.zeros((400, 400, 3), np.uint8)))
        provider = self.stack.enter_context(patch("src.task.HuntMobTask.KuroMapDataProvider"))
        provider.return_value.query_target_mob_locations.return_value = (spawn("a", 100),)
        self.nav_factory = self.stack.enter_context(patch("src.task.HuntMobTask.WorldRouteNavigator"))
        self.nav = self.nav_factory.return_value
        self.nav.follow_to.return_value = NavigationResult(NavigationStatus.ARRIVED)
        self.nav.stop.return_value = True
        self.startup = self.stack.enter_context(patch.object(WWOneTimeTask, "run"))
        self.preflight = self.stack.enter_context(patch.object(self.task, "_run_localization_test",
                                                               return_value={"within_tolerance": True}))
        self.task.executor.reset_mock()

    def test_walk_never_starts_combat_or_hunt_and_uses_profile_limit(self):
        result = self.task.run()
        self.assertEqual(NavigationStatus.ARRIVED, result.status)
        self.assertIsNone(self.task.controller)
        self.assertIsNone(self.task.hunt_run)
        self.startup.assert_not_called()
        self.task.combat_once.assert_not_called()
        self.assertEqual(0, self.nav_factory.call_args.kwargs["max_recovery_attempts"])
        self.assertEqual(10, self.nav.follow_to.call_args.kwargs["timeout"])
        self.assertEqual(MapCoordinate(20, 20), self.nav.follow_to.call_args.args[0].coordinate)
        self.nav.stop.assert_called_once()

    def test_privilege_mismatch_stops_before_preflight_or_inputs(self):
        self.input_access.side_effect = RuntimeError("game runs as administrator")
        with self.assertRaisesRegex(RuntimeError, "administrator"):
            self.task.run()
        self.preflight.assert_not_called()
        self.nav_factory.assert_not_called()
        self.startup.assert_not_called()
        self.assertEqual([], self.task.executor.interaction.mock_calls)

    def test_localization_does_not_require_input_privileges(self):
        self.task.config["Localization Only"] = True
        self.input_access.side_effect = AssertionError("input privileges checked")
        self.task.run()
        self.input_access.assert_not_called()

    def test_hybrid_can_walk_after_review_and_fresh_preflight(self):
        self.load.return_value = replace(self.profile, matcher_calibration_path=Path("policy.json"))
        with patch("src.task.HuntMobTask.MatcherCalibration.load", return_value=Mock(state_id=8, floor_id="")), \
                patch("src.task.HuntMobTask.HybridMapMatcher") as matcher:
            self.task.run()
        matcher.assert_called_once()
        self.preflight.assert_called_once()
        self.nav.follow_to.assert_called_once()

    def test_unstable_or_cancelled_preflight_sends_no_inputs(self):
        for report in ({"within_tolerance": False}, {"within_tolerance": None}, None):
            with self.subTest(report=report):
                self.preflight.return_value = report
                if report is None:
                    self.assertIsNone(self.task.run())
                else:
                    with self.assertRaisesRegex(ValueError, "Stationary localization"):
                        self.task.run()
        self.nav_factory.assert_not_called()
        self.startup.assert_not_called()
        self.task.executor.interaction.assert_not_called()
        self.assertEqual([], self.task.executor.interaction.mock_calls)

    def test_unreviewed_profile_missing_target_or_tolerance_cannot_move(self):
        for changes in ({"localization_verified": False}, {"test_walk_target": None},
                        {"localization_tolerance_pixels": None},
                        {"test_walk_target": MapCoordinate(500, 20)}):
            with self.subTest(changes=changes):
                self.load.return_value = replace(self.profile, **changes)
                with self.assertRaises(ValueError):
                    self.task.run()
        self.nav_factory.assert_not_called()
        self.preflight.assert_not_called()

    def test_hunt_requires_walk_review(self):
        self.task.config["Test Walk Only"] = False
        with self.assertRaisesRegex(ValueError, "reviewed short walk"):
            self.task.run()
        self.startup.assert_not_called()

    def test_combat_aggro_prevents_start(self):
        self.task.enemy_present.return_value = True
        with self.assertRaisesRegex(ValueError, "outside combat"):
            self.task.run()
        self.nav_factory.assert_not_called()

    def test_combat_loss_timeout_and_cleanup_errors_fail_walk_without_handoff(self):
        for status in (NavigationStatus.COMBAT, NavigationStatus.LOST_LOCALIZATION,
                       NavigationStatus.TIMEOUT, NavigationStatus.FAILED):
            with self.subTest(status=status):
                self.nav.follow_to.return_value = NavigationResult(status)
                with self.assertRaisesRegex(HuntAbort, status.value):
                    self.task.run()
        self.task.combat_once.assert_not_called()
        self.nav.follow_to.return_value = NavigationResult(NavigationStatus.ARRIVED)
        self.nav.stop.return_value = False
        with self.assertRaisesRegex(HuntAbort, "cleanup failed"):
            self.task.run()

    def test_cancellation_releases_controls_and_remains_cancelled(self):
        self.nav.follow_to.return_value = NavigationResult(NavigationStatus.CANCELLED)
        self.assertEqual(NavigationStatus.CANCELLED, self.task.run().status)
        self.nav.stop.assert_called_once()

    def test_reused_task_clears_old_controller_before_read_only_mode(self):
        self.task.controller = Mock()
        self.task.navigator = Mock()
        self.task.config["Localization Only"] = True
        self.task.run()
        self.assertIsNone(self.task.controller)
        self.assertIsNone(self.task.navigator)
        self.nav_factory.assert_not_called()

    def test_pause_interrupts_walk_sleeps_without_a_hunt_controller(self):
        self.task.navigator = self.nav
        self.task.cancelled.return_value = True
        with self.assertRaises(TaskDisabledException):
            self.task.sleep_check()

    def test_navigation_combat_detection_does_not_call_interactive_detector(self):
        del self.task.in_combat
        del self.task.enemy_present
        self.task.has_health_bar = Mock(return_value=False)
        self.task.has_target = Mock(return_value=True)
        with patch.object(CombatCheck, "in_combat") as interactive:
            self.assertTrue(self.task.in_combat())
        interactive.assert_not_called()
        self.task.has_target.assert_called_once_with(allow_recovery=False)

    def test_wide_target_read_only_check_does_not_press_escape_or_wait(self):
        detector = Mock(esc_count=0)
        detector.get_target_names.return_value = ("has_target", "no_target")
        detector.is_browser.return_value = False
        detector.allow_target_box_short_combat_check.return_value = False
        match = Mock()
        match.name = "has_target"
        detector.find_best_match_in_box.side_effect = [None, None, None, match]
        self.assertTrue(CombatCheck.has_target(detector, allow_recovery=False))
        detector.sleep.assert_not_called()
        detector.send_key.assert_not_called()

    def test_walk_sleep_does_not_dismiss_monthly_card_dialog(self):
        self.task.check_for_monthly_card = Mock(side_effect=AssertionError("unexpected dialog input"))
        self.task.sleep(0.1)
        self.task.check_for_monthly_card.assert_not_called()
        self.task.executor.sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()
