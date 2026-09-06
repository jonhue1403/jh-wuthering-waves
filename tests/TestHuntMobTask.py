import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from ok import TaskDisabledException
from src.overworld.controller import HuntAbort, HuntCancelled, HuntController, HuntState
from src.overworld.models import MapCoordinate
from src.overworld.navigation.player_locator import SurfaceProfile
from src.overworld.navigation import NavigationStatus, WorldRouteNavigator
from src.task.BaseCombatTask import BaseCombatTask, CharDeadException
from src.task.HuntMobTask import HuntMobTask
from src.task.WWOneTimeTask import WWOneTimeTask
from tests.TestHuntController import Navigator, Runtime, spawn


class TestHuntMobTask(unittest.TestCase):
    def setUp(self):
        self.task = HuntMobTask(executor=Mock(), app=Mock())
        self.task.config = dict(self.task.default_config)
        self.task.key_config = {}
        self.task.send_key_up = Mock()
        self.task.mouse_up = Mock()

    def test_safe_defaults_and_disabled_transport_enforced_before_inputs(self):
        self.assertTrue(self.task.config["Safe Test Mode"])
        self.assertEqual(1, self.task.config["Max Camps"])
        for key, value in (("Use Teleport", True), ("Use Motorcycle", True),
                           ("Surface Only", False), ("Safe Test Mode", False),
                           ("Max Camps", 2), ("Max Camps", 4), ("Max Camp Retries", -1)):
            with self.subTest(key=key):
                self.task.config = dict(self.task.default_config)
                self.task.config[key] = value
                with self.assertRaises(ValueError):
                    self.task.run()
                self.task.executor.interaction.send_key_down.assert_not_called()

    def test_missing_profile_fails_before_input(self):
        with self.assertRaisesRegex(ValueError, "Hunt Profile"):
            self.task.run()
        self.task.executor.interaction.send_key_down.assert_not_called()

    def test_combat_delegates_to_existing_base_combat(self):
        with patch.object(BaseCombatTask, "combat_once", return_value=True) as combat:
            self.assertTrue(self.task.combat_once())
        combat.assert_called_once_with(wait_combat_time=1, raise_if_not_found=False, target=False)

    def test_framework_cancellation_during_combat_is_preserved(self):
        with patch.object(BaseCombatTask, "combat_once", side_effect=TaskDisabledException()):
            with self.assertRaises(HuntCancelled):
                self.task.combat_once()
        self.task.send_key_up.assert_any_call("e")
        self.task.mouse_up.assert_called_with(key="left")

    def test_death_is_a_session_abort(self):
        with patch.object(BaseCombatTask, "combat_once", side_effect=CharDeadException()):
            with self.assertRaises(HuntAbort):
                self.task.combat_once()

    def test_navigation_framework_cancellation_is_not_camp_failure(self):
        backend = Mock()
        backend.in_combat.return_value = False
        backend.next_frame.side_effect = TaskDisabledException()
        navigator = WorldRouteNavigator(backend, cancellation_exceptions=(TaskDisabledException,))
        result = navigator.follow_to("camp", arrival_threshold=1)
        self.assertEqual(NavigationStatus.CANCELLED, result.status)
        backend.stop.assert_called_once()

    def test_sleep_check_only_belongs_to_combat(self):
        self.task.controller = Mock()
        self.task.cancelled = Mock(return_value=False)
        with patch.object(BaseCombatTask, "sleep_check") as check:
            self.task.controller.run_state.state = HuntState.TRAVELLING
            self.task.sleep_check()
            check.assert_not_called()
            self.task.controller.run_state.state = HuntState.COMBAT
            self.task.sleep_check()
            check.assert_called_once()

    def test_death_does_not_invoke_default_teleport_recovery(self):
        with patch.object(BaseCombatTask, "revive_action") as revive:
            self.assertFalse(self.task.revive_action())
            revive.assert_not_called()

    def test_task_wires_verified_data_into_live_controller(self):
        runtime = Runtime()
        navigator = Navigator(runtime)
        profile = SurfaceProfile(Path("map.png"), Path("map.db"), "Target", 8, "",
                                  MapCoordinate(0, 0), 1, (1920, 1080), frozenset({"a"}))
        locator = Mock()
        locator.locate.side_effect = runtime.locate
        self.task.config.update({"Target Mob": "Target", "Hunt Profile": "profile.json"})
        self.task.cancelled = runtime.cancelled
        self.task.wait = runtime.wait
        self.task.in_combat = runtime.in_combat
        self.task.enemy_present = runtime.enemy_present
        self.task.report = runtime.report
        self.task.log_info = Mock()
        self.task.wait_in_team_and_world = Mock()

        def controller(planner, nav, task, *, options):
            return HuntController(planner, nav, task, options=options, clock=lambda: runtime.time)

        with ExitStack() as stack:
            stack.enter_context(patch.object(WWOneTimeTask, "run"))
            module = "src.task.HuntMobTask."
            stack.enter_context(patch(module + "SurfaceProfile.load", return_value=profile))
            stack.enter_context(patch(module + "np.fromfile", return_value=np.zeros(1, dtype=np.uint8)))
            stack.enter_context(patch(module + "cv2.imdecode", return_value=np.zeros((400, 400, 3))))
            provider = stack.enter_context(patch(module + "KuroMapDataProvider"))
            provider.return_value.query_target_mob_locations.return_value = (spawn("a", 100),)
            stack.enter_context(patch(module + "PlayerLocator", return_value=locator))
            stack.enter_context(patch(module + "WorldRouteNavigator", return_value=navigator))
            stack.enter_context(patch(module + "HuntController", side_effect=controller))
            # The new default Test A must not enter startup or live orchestration.
            with patch.object(self.task, "_run_localization_test", return_value={"sample_count": 10}) as sample:
                self.assertEqual({"sample_count": 10}, self.task.run())
                sample.assert_called_once()
                self.assertEqual([], navigator.targets)
                self.task.send_key_up.assert_not_called()
                self.task.mouse_up.assert_not_called()
            self.task.config["Localization Only"] = False
            provider.return_value.query_target_mob_locations.reset_mock()
            self.task.run()
            provider.return_value.query_target_mob_locations.assert_called_once_with(
                "Target", state_id=8, floor_id="")
        self.assertEqual(1, len(self.task.hunt_run.session.cleared_camps))
        self.assertEqual(HuntState.COMPLETE, self.task.hunt_run.state)
        self.assertEqual(1, len(navigator.targets))
        self.task.mouse_up.assert_called_with(key="left")
