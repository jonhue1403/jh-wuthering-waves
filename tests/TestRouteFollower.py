import unittest

from src.overworld.navigation import (
    MovementState,
    NavigationStatus,
    RecoveryStage,
    SlidingWindowStuckDetector,
    WaypointObservation,
    WorldRouteNavigator,
)
from src.overworld.navigation.ok_adapter import WWTaskNavigationBackend


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def advance(self, seconds=0.1):
        self.value += seconds


class FakeBackend:
    def __init__(self, clock, observations=None, combat_after=None, raise_on_navigate=False):
        self.clock = clock
        self.observations = observations or {}
        self.combat_after = combat_after
        self.raise_on_navigate = raise_on_navigate
        self.observed = []
        self.navigation_calls = 0
        self.stop_calls = []
        self.recovery_calls = []

    def next_frame(self):
        self.clock.advance()

    def observe(self, waypoint):
        self.observed.append(waypoint)
        values = self.observations.get(waypoint, [WaypointObservation(100, 0, (0, 0))])
        if len(values) > 1:
            return values.pop(0)
        return values[0]

    def in_combat(self):
        return self.combat_after is not None and self.clock.value >= self.combat_after

    def navigate(self, observation, state):
        if self.raise_on_navigate:
            raise RuntimeError("navigation failed")
        self.navigation_calls += 1
        return MovementState("w")

    def stop(self, state):
        self.stop_calls.append(state)

    def recover(self, stage):
        self.recovery_calls.append(stage)


class TestSlidingWindowStuckDetector(unittest.TestCase):
    def test_irregular_frame_times_still_detect_stall(self):
        clock = FakeClock()
        detector = SlidingWindowStuckDetector(window_seconds=1, clock=clock)
        results = []
        for timestamp in (0, 0.31, 0.69, 1.07):
            results.append(detector.record(position=(0, 0), distance=10,
                                          movement_active=True, timestamp=timestamp))
        self.assertEqual([False, False, False, True], results)

    def test_progress_detection_uses_thresholds_not_exact_float_equality(self):
        clock = FakeClock()
        detector = SlidingWindowStuckDetector(
            window_seconds=1,
            position_threshold=0.1,
            distance_threshold=0.1,
            clock=clock,
        )

        self.assertFalse(detector.record(position=(0, 0), distance=10.0, movement_active=True))
        clock.advance(1)
        stuck = detector.record(position=(0.01, 0), distance=9.95, movement_active=True)

        self.assertTrue(stuck)


class TestWorldRouteNavigator(unittest.TestCase):
    def make_navigator(self, backend, clock, **kwargs):
        return WorldRouteNavigator(
            backend,
            clock=clock,
            stuck_window_seconds=kwargs.pop("stuck_window_seconds", 10),
            **kwargs,
        )

    def test_waypoint_arrival_advances_to_next_waypoint(self):
        clock = FakeClock()
        backend = FakeBackend(clock, {
            "a": [WaypointObservation(1, 0, (0, 0))],
            "b": [WaypointObservation(100, 0, (0, 0)), WaypointObservation(1, 0, (1, 0))],
        })
        result = self.make_navigator(backend, clock).follow_waypoints(
            ["a", "b"], arrival_threshold=5
        )

        self.assertEqual(NavigationStatus.ARRIVED, result.status)
        self.assertEqual(["a", "b", "b"], backend.observed)
        self.assertEqual(2, result.waypoint_index)

    def test_final_waypoint_returns_arrived(self):
        clock = FakeClock()
        backend = FakeBackend(clock, {"final": [WaypointObservation(1, 0, (0, 0))]})

        result = self.make_navigator(backend, clock).follow_to("final", arrival_threshold=5)

        self.assertEqual(NavigationStatus.ARRIVED, result.status)
        self.assertEqual("final", result.waypoint)

    def test_combat_stops_navigation_and_releases_controls(self):
        clock = FakeClock()
        backend = FakeBackend(clock, combat_after=0.1)

        result = self.make_navigator(backend, clock).follow_to("target", arrival_threshold=1)

        self.assertEqual(NavigationStatus.COMBAT, result.status)
        self.assertGreaterEqual(len(backend.stop_calls), 1)

    def test_timeout_returns_timeout(self):
        clock = FakeClock()
        backend = FakeBackend(clock)

        result = self.make_navigator(backend, clock).follow_to(
            "target", arrival_threshold=1, timeout=0.25
        )

        self.assertEqual(NavigationStatus.TIMEOUT, result.status)

    def test_recovery_attempts_are_bounded(self):
        clock = FakeClock()
        backend = FakeBackend(clock, {
            "target": [
                WaypointObservation(10.0, 0, (0, 0)),
                WaypointObservation(9.95, 0, (0.01, 0)),
            ]
        })
        navigator = self.make_navigator(
            backend,
            clock,
            stuck_window_seconds=0.2,
            position_threshold=0.1,
            distance_threshold=0.1,
            max_recovery_attempts=2,
        )

        result = navigator.follow_to("target", arrival_threshold=1)

        self.assertEqual(NavigationStatus.STUCK, result.status)
        self.assertEqual(2, len(backend.recovery_calls))
        self.assertEqual(RecoveryStage.RECENTER, backend.recovery_calls[0])

    def test_controls_are_released_after_exception(self):
        clock = FakeClock()
        backend = FakeBackend(clock, raise_on_navigate=True)

        result = self.make_navigator(backend, clock).follow_to("target", arrival_threshold=1)

        self.assertEqual(NavigationStatus.FAILED, result.status)
        self.assertEqual(1, len(backend.stop_calls))

    def test_controls_are_released_after_cancellation(self):
        clock = FakeClock()
        backend = FakeBackend(clock)

        result = self.make_navigator(backend, clock).follow_to(
            "target", arrival_threshold=1, stop_condition=lambda: clock.value >= 0.1
        )

        self.assertEqual(NavigationStatus.CANCELLED, result.status)
        self.assertEqual(1, len(backend.stop_calls))


class TestWWTaskNavigationBackend(unittest.TestCase):
    def test_stop_releases_tracked_and_possible_movement_controls_and_camera(self):
        class FakeTask:
            def __init__(self):
                self.released = []
                self.mouse_released = []

            def send_key_up(self, key):
                self.released.append(key)

            def _stop_movement(self, direction):
                self.released.append(direction)

            def mouse_up(self, key):
                self.mouse_released.append(key)

        task = FakeTask()
        backend = WWTaskNavigationBackend(task, lambda waypoint: None)

        backend.stop(MovementState("w", "a"))

        self.assertTrue({"w", "a", "s", "d"}.issubset(set(task.released)))
        self.assertEqual(["right", "middle"], task.mouse_released)

    def test_cleanup_attempts_remaining_inputs_and_reports_failure(self):
        from unittest.mock import Mock
        task = Mock(key_config={})
        task.send_key_up.side_effect = RuntimeError("device failed")
        backend = WWTaskNavigationBackend(task, lambda waypoint: None)
        navigator = WorldRouteNavigator(backend)
        self.assertFalse(navigator.stop())
        self.assertGreaterEqual(task.send_key_up.call_count, 6)
        self.assertEqual(2, task.mouse_up.call_count)


if __name__ == "__main__":
    unittest.main()
