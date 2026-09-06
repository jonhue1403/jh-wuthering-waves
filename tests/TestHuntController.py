import unittest
from unittest.mock import Mock

from src.overworld.controller import HuntCancelled, HuntController, HuntOptions, HuntState
from src.overworld.models import HuntPosition, MapCoordinate, MobSpawn
from src.overworld.navigation import NavigationResult, NavigationStatus
from src.overworld.planner import DryRunRoutePlanner, TravelCostModel, cluster_spawns


def position(x, state=8, floor=""):
    return HuntPosition(state, floor, MapCoordinate(x, 0))


def spawn(name, x, state=8, floor=""):
    return MobSpawn(name, "mob", "Target", state, floor, MapCoordinate(x, 0))


class Runtime:
    def __init__(self):
        self.position = position(0)
        self.time = 0
        self.events = []
        self.cancel = False
        self.combat = False
        self.enemy = False
        self.post_combat_position = position(90)

    def locate(self):
        self.events.append(("locate", self.position))
        return self.position

    def cancelled(self):
        return self.cancel

    def in_combat(self):
        return self.combat

    def enemy_present(self):
        return self.enemy

    def combat_once(self):
        self.events.append(("combat",))
        self.position = self.post_combat_position
        self.combat = False

    def wait(self, seconds):
        self.time += seconds

    def report(self, state, camp, run):
        self.events.append((state.value,))


class Navigator:
    def __init__(self, runtime):
        self.runtime = runtime
        self.results = []
        self.targets = []
        self.approaches = []

    def stop(self):
        self.runtime.events.append(("stop",))
        return True

    def follow_to(self, target, **kwargs):
        self.targets.append(target)
        self.runtime.events.append(("navigate", target))
        status = self.results.pop(0) if self.results else NavigationStatus.ARRIVED
        if status is NavigationStatus.ARRIVED:
            self.runtime.position = target
        return NavigationResult(status)

    def follow_waypoints(self, targets, **kwargs):
        self.approaches.append(targets)
        self.runtime.position = targets[-1]
        return NavigationResult(NavigationStatus.ARRIVED)


class TestHuntController(unittest.TestCase):
    def setUp(self):
        self.runtime = Runtime()
        self.navigator = Navigator(self.runtime)
        real_planner = DryRunRoutePlanner(cluster_radius=10,
                                         travel_cost=TravelCostModel(100, 34, 500))
        self.planner = Mock(wraps=real_planner)
        self.origins = []

        def plan(*args, **kwargs):
            self.origins.append(kwargs["session"].current_position)
            self.runtime.events.append(("plan",))
            return real_planner.plan(*args, **kwargs)

        self.planner.plan.side_effect = plan

    def run_hunt(self, spawns=None, **options):
        self.controller = HuntController(self.planner, self.navigator, self.runtime,
                                         options=HuntOptions(arrival_radius=5, **options),
                                         clock=lambda: self.runtime.time)
        return self.controller.run("Target", spawns or [spawn("a", 100)], layer=(8, ""))

    def test_planner_selected_camp_is_passed_to_navigation(self):
        self.run_hunt([spawn("far", 200), spawn("near", 100)])
        self.assertEqual(position(100), self.navigator.targets[0])

    def test_arrival_enters_approach_and_bounded_clear_workflow(self):
        result = self.run_hunt()
        states = [event[0] for event in self.runtime.events]
        self.assertLess(states.index("APPROACH"), states.index("CLEAR_CHECK"))
        self.assertEqual([[position(100)]], self.navigator.approaches)
        self.assertGreaterEqual(self.runtime.time, 3)
        self.assertEqual(1, len(result.session.cleared_camps))

    def test_unexpected_combat_releases_inputs_then_combat_localizes_and_replans(self):
        self.navigator.results = [NavigationStatus.COMBAT]
        self.run_hunt()
        events = [e[0] for e in self.runtime.events]
        fight = events.index("combat")
        self.assertEqual(["stop", "COMBAT"], events[fight - 2:fight])
        self.assertLess(events.index("locate", fight), events.index("plan", fight))
        self.assertEqual(position(90), self.origins[1])
        self.assertEqual(2, len(self.navigator.targets))

    def test_unclear_camp_is_not_marked_cleared(self):
        self.runtime.enemy = True
        result = self.run_hunt(max_retries=0)
        self.assertFalse(result.session.cleared_camps)
        self.assertEqual(1, len(result.session.failed_camps))

    def test_retry_limit_and_failed_camp_does_not_abort_session(self):
        self.navigator.results = [NavigationStatus.STUCK] * 3
        result = self.run_hunt([spawn("a", 100), spawn("b", 200)], max_camps=2, max_retries=2)
        self.assertEqual([position(100)] * 3 + [position(200)], self.navigator.targets)
        self.assertEqual(1, len(result.session.failed_camps))
        self.assertEqual(1, len(result.session.cleared_camps))
        self.assertEqual(HuntState.COMPLETE, result.state)

    def test_camp_combat_error_does_not_abort_other_camps(self):
        self.navigator.results = [NavigationStatus.COMBAT]
        self.runtime.combat_once = Mock(side_effect=RuntimeError("combat failed"))
        result = self.run_hunt([spawn("a", 100), spawn("b", 200)], max_camps=2, max_retries=0)
        self.assertEqual(1, len(result.session.failed_camps))
        self.assertEqual(1, len(result.session.cleared_camps))

    def test_replans_after_clear_from_actual_position(self):
        original_wait = self.runtime.wait

        def drift(seconds):
            original_wait(seconds)
            self.runtime.position = position(104)

        self.runtime.wait = drift
        self.run_hunt()
        self.assertEqual(position(104), self.origins[-1])

    def test_reacquired_combat_during_clear_replans_without_clearing_camp(self):
        original_approach = self.navigator.follow_waypoints

        def approach(*args, **kwargs):
            result = original_approach(*args, **kwargs)
            self.runtime.combat = len(self.navigator.approaches) == 1
            return result

        self.navigator.follow_waypoints = approach
        self.run_hunt()
        self.assertEqual(2, len(self.navigator.targets))
        self.assertEqual(position(90), self.origins[1])

    def test_cancellation_releases_inputs(self):
        self.navigator.results = [NavigationStatus.CANCELLED]
        result = self.run_hunt()
        self.assertEqual(HuntState.CANCELLED, result.state)
        self.assertEqual(("stop",), self.runtime.events[-1])
        self.assertFalse(result.session.cleared_camps)

    def test_cancellation_during_combat_releases_inputs(self):
        self.navigator.results = [NavigationStatus.COMBAT]
        self.runtime.combat_once = Mock(side_effect=HuntCancelled())
        result = self.run_hunt()
        self.assertEqual(HuntState.CANCELLED, result.state)
        self.assertEqual(("stop",), self.runtime.events[-1])

    def test_cleanup_failure_prevents_combat(self):
        self.navigator.results = [NavigationStatus.COMBAT]
        calls = 0

        def stop():
            nonlocal calls
            calls += 1
            return calls == 1

        self.navigator.stop = stop
        with self.assertRaisesRegex(RuntimeError, "input release"):
            self.run_hunt()
        self.assertNotIn(("combat",), self.runtime.events)

    def test_wrong_layer_camps_never_execute_and_teleport_step_stops(self):
        result = self.run_hunt([spawn("floor", 1, floor="B1"), spawn("state", 1, state=9),
                               spawn("far", 10000)])
        self.assertEqual([], self.navigator.targets)
        self.assertEqual(HuntState.COMPLETE, result.state)

    def test_lost_player_localization_stops_without_guessing(self):
        self.runtime.position = None
        with self.assertRaisesRegex(RuntimeError, "localization"):
            self.run_hunt()
        self.assertEqual([], self.navigator.targets)

    def test_interruption_budget_prevents_infinite_combat_loop(self):
        self.navigator.results = [NavigationStatus.COMBAT] * 4
        result = self.run_hunt(max_interruptions=2, max_retries=1)
        self.assertEqual(4, len(self.navigator.targets))
        self.assertEqual(1, len(result.session.failed_camps))

    def test_empty_arrival_does_not_skip_other_spawn_points(self):
        spawns = [spawn("a", 100), spawn("b", 105)]
        result = self.run_hunt(spawns)
        self.assertEqual([[position(100), position(105)]], self.navigator.approaches)
        self.assertIn(cluster_spawns(spawns, radius=10)[0].camp_id, result.session.cleared_camps)

    def test_clear_check_leaving_camp_fails(self):
        self.runtime.wait = lambda _: setattr(self.runtime, "position", position(1000))
        result = self.run_hunt(max_retries=0)
        self.assertFalse(result.session.cleared_camps)
        self.assertTrue(result.session.failed_camps)


if __name__ == "__main__":
    unittest.main()
