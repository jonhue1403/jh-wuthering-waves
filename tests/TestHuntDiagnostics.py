import json
import unittest
from unittest.mock import Mock, patch

from src.overworld.diagnostics import HuntDiagnostics, stationary_localization
from src.overworld.models import HuntPosition, MapCoordinate
from src.overworld.navigation import NavigationStatus, WorldRouteNavigator
from tests.TestRouteFollower import FakeClock, FakeBackend


class TestHuntDiagnostics(unittest.TestCase):
    def test_progress_is_throttled_but_transitions_and_invalid_localization_are_not_hidden(self):
        clock = FakeClock()
        lines = []
        log = HuntDiagnostics(lines.append, clock=clock)
        for index in range(10):
            log("navigation_progress", distance=100-index)
        log("localization", valid=True)
        log("localization", valid=False)
        log("combat_start")
        log("navigation_cleanup", success=True)
        clock.advance(2)
        log("navigation_progress", distance=80)
        events = [json.loads(line.removeprefix("[HUNT] "))["event"] for line in lines]
        self.assertEqual(2, events.count("navigation_progress"))
        self.assertEqual(2, events.count("localization"))
        self.assertIn("combat_start", events)
        self.assertIn("navigation_cleanup", events)

    def test_broken_log_sink_does_not_prevent_cleanup(self):
        clock = FakeClock()
        backend = FakeBackend(clock)
        log = HuntDiagnostics(Mock(side_effect=RuntimeError("log failed")))
        navigator = WorldRouteNavigator(backend, diagnostic=log)
        result = navigator.follow_to("a", arrival_threshold=1, stop_condition=lambda: True)
        self.assertEqual(NavigationStatus.CANCELLED, result.status)
        self.assertTrue(backend.stop_calls)

    def test_stationary_spread_is_pairwise_and_does_not_claim_absolute_accuracy(self):
        positions = [HuntPosition(8, "", MapCoordinate(x, 0)) for x in (0, 1, -1)]
        report = stationary_localization(Mock(side_effect=positions), Mock(), Mock(),
                                          units_per_pixel=2, tolerance_pixels=0.5, sample_count=3)
        self.assertEqual(1, report["max_pairwise_spread_pixels"])
        self.assertFalse(report["within_tolerance"])
        self.assertIsNone(report["absolute_error"])

    def test_missing_tolerance_does_not_pass_even_perfect_repeatability(self):
        report = stationary_localization(lambda: HuntPosition(8, "", MapCoordinate(0, 0)),
                                          Mock(), Mock(), units_per_pixel=1)
        self.assertEqual(0, report["max_pairwise_spread_pixels"])
        self.assertIsNone(report["within_tolerance"])

    def test_lost_localization_stops_sampling_immediately(self):
        locate, wait = Mock(return_value=None), Mock()
        with self.assertRaisesRegex(RuntimeError, "sample 1"):
            stationary_localization(locate, wait, Mock(), units_per_pixel=1)
        self.assertEqual(1, locate.call_count)
        wait.assert_not_called()

    def test_test_a_has_no_keyboard_mouse_combat_or_navigation_calls(self):
        from src.task.HuntMobTask import HuntMobTask
        task = HuntMobTask(executor=Mock(), app=Mock())
        task._hunt_profile = Mock(units_per_pixel=1, localization_tolerance_pixels=0.5)
        task.locator = Mock(last_confidence=0.9)
        task.locate = Mock(return_value=HuntPosition(8, "", MapCoordinate(0, 0)))
        task.cancelled = Mock(return_value=False)
        task.send_key_down, task.send_key_up, task.mouse_down, task.mouse_up = Mock(), Mock(), Mock(), Mock()
        task.middle_click, task.combat_once = Mock(), Mock()
        with patch.object(task, "wait_in_team_and_world") as startup:
            result = task._run_localization_test()
        self.assertTrue(result["within_tolerance"])
        self.assertEqual(10, task.locate.call_count)
        self.assertEqual(9, task.executor.sleep.call_count)
        for method in (task.send_key_down, task.send_key_up, task.mouse_down, task.mouse_up,
                       task.middle_click, task.combat_once, startup):
            method.assert_not_called()

    def test_test_a_cancel_does_not_enter_navigation(self):
        from src.task.HuntMobTask import HuntMobTask
        task = HuntMobTask(executor=Mock(), app=Mock())
        task._hunt_profile = Mock(units_per_pixel=1, localization_tolerance_pixels=None)
        task.cancelled = Mock(return_value=True)
        task.locate = Mock()
        self.assertIsNone(task._run_localization_test())
        task.locate.assert_not_called()
        task.executor.sleep.assert_not_called()

    def test_pause_unwinds_a_hunt_sleep_for_input_cleanup(self):
        from ok import TaskDisabledException
        from src.task.HuntMobTask import HuntMobTask
        task = HuntMobTask(executor=Mock(), app=Mock())
        task.controller = Mock()
        task.cancelled = Mock(return_value=True)
        with self.assertRaises(TaskDisabledException):
            task.sleep_check()

    def test_facing_match_can_be_cancelled_between_angles(self):
        import numpy as np
        from ok import TaskDisabledException
        from src.task.BaseWWTask import BaseWWTask
        task = Mock()
        task.get_feature_by_name.return_value.mat = np.zeros((10, 10, 3), dtype=np.uint8)
        cancel_check = Mock(side_effect=TaskDisabledException())
        with self.assertRaises(TaskDisabledException):
            BaseWWTask.rotate_arrow_and_find(task, cancel_check=cancel_check)
        task.find_one.assert_not_called()
