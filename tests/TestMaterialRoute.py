"""Synthetic offline behavior checks; these fixtures are not live qualification."""

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from src.overworld.controller import HuntAbort, HuntCancelled, HuntState
from src.overworld.material_route import (
    CampSegment, InventoryObservation, MaterialRoute, MaterialRouteRuntime,
    ReviewedNavigator, TransitionObservation, known_beacon_transition, run_material_route,
)
from src.overworld.navigation import NavigationStatus
from src.overworld.navigation.player_locator import SurfaceProfile
from src.overworld.planner import cluster_spawns
from src.overworld.qualification import RuntimeQualification, file_sha256
from tests.TestHuntController import Navigator, Runtime, position, spawn


class TestMaterialRoute(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.profile_path = self.folder / "profile.json"
        self.profile_path.write_text("synthetic offline profile", encoding="utf-8")
        self.profile = SurfaceProfile(self.folder / "map", self.folder / "db", "Target", 8, "",
                                      position(0).coordinate, 1, (1920, 1080), frozenset({"a", "b"}))
        self.spawns = (spawn("a", 100), spawn("b", 200))
        self.camps = cluster_spawns(self.spawns, radius=20)
        self.route = MaterialRoute(
            self.folder / "route.json", "synthetic-only", self.profile_path,
            file_sha256(self.profile_path), "material-fixture", "Target", (8, ""),
            tuple(CampSegment(c.camp_id, frozenset(s.spawn_id for s in c.spawns),
                              (position(0 if i == 0 else 100), c.position))
                  for i, c in enumerate(self.camps)),
            10, 60, {}, {})
        self.runtime = Runtime()
        self.navigator = Navigator(self.runtime)
        self.reads = 0

    def inventory(self, material_id):
        self.reads += 1
        return InventoryObservation(material_id, (self.reads - 1) * 2,
                                    self.runtime.time, str(self.reads), "ITEM_DETAIL")

    def run_route(self, *, target=99, read_inventory=None, pickup=None):
        return run_material_route(self.route, self.profile, self.spawns, self.navigator,
                                  self.runtime, target=target,
                                  read_inventory=read_inventory or self.inventory,
                                  pickup=pickup or Mock(), clock=lambda: self.runtime.time)

    def test_two_camps_reuse_existing_controller_and_observe_each_receipt(self):
        run, material = self.run_route()
        self.assertEqual(HuntState.COMPLETE, run.state)
        self.assertEqual(2, len(run.session.cleared_camps))
        self.assertEqual([2, 2], [r["received"] for r in material.receipts])
        self.assertEqual(3, self.reads)
        self.assertFalse(material.goal_reached())

    def test_observed_goal_stops_before_next_camp(self):
        run, material = self.run_route(target=2)
        self.assertEqual(1, len(run.session.cleared_camps))
        self.assertEqual("Observed material inventory reached target", run.reason)
        self.assertEqual(2, self.reads)
        self.assertTrue(material.goal_reached())

    def test_already_satisfied_inventory_never_moves_or_picks_up(self):
        pickup = Mock()
        read = lambda m: InventoryObservation(m, 5, self.runtime.time, "first", "ITEM_DETAIL")
        run, _ = self.run_route(target=4, read_inventory=read, pickup=pickup)
        self.assertEqual(HuntState.COMPLETE, run.state)
        self.assertEqual([], self.navigator.targets)
        pickup.assert_not_called()

    def test_empty_camp_and_issued_pickup_do_not_prove_drop(self):
        serial = iter(range(3))

        def empty(material):
            return InventoryObservation(material, 0, self.runtime.time, str(next(serial)), "ITEM_DETAIL")

        pickup = Mock()
        _, material = self.run_route(target=1, read_inventory=empty, pickup=pickup)
        self.assertEqual(2, pickup.call_count)
        self.assertEqual([0, 0], [r["received"] for r in material.receipts])
        self.assertFalse(material.goal_reached())

    def test_duplicate_or_stale_inventory_frame_stops_uncertain(self):
        for duplicate in (True, False):
            with self.subTest(duplicate=duplicate):
                self.runtime = Runtime()
                self.navigator = Navigator(self.runtime)

                def bad(material):
                    return InventoryObservation(material, 0, 0 if duplicate else -10,
                                                "same", "ITEM_DETAIL")

                with self.assertRaisesRegex(HuntAbort, "Fresh"):
                    self.run_route(read_inventory=bad)

    def test_ambiguous_inventory_decrease_does_not_advance_goal(self):
        counts = iter([5, 4])

        def decreasing(material):
            return InventoryObservation(material, next(counts), self.runtime.time,
                                        str(self.runtime.time), "ITEM_DETAIL")

        with self.assertRaisesRegex(HuntAbort, "uncertainty"):
            self.run_route(read_inventory=decreasing)

    def test_wrong_layer_and_changed_profile_rejected_before_navigation(self):
        original = self.route
        for route in (replace(original, layer=(8, "B1")),
                      replace(original, profile_sha256="0" * 64)):
            with self.subTest(route=route.layer):
                self.route = route
                with self.assertRaises(ValueError):
                    self.run_route()
                self.assertEqual([], self.navigator.targets)

    def test_off_route_position_refuses_shortcut(self):
        self.runtime.position = position(55)
        with self.assertRaisesRegex(HuntAbort, "rejoin"):
            self.run_route()
        self.assertEqual([], self.navigator.targets)

    def test_post_combat_relocalization_outside_reviewed_path_aborts(self):
        self.navigator.results = [NavigationStatus.COMBAT]
        self.runtime.post_combat_position = position(55)
        with self.assertRaisesRegex(HuntAbort, "rejoin"):
            self.run_route()
        self.assertIn(("combat",), self.runtime.events)
        self.assertEqual(("stop",), self.runtime.events[-1])

    def test_cancellation_cleans_navigation_without_inventory_retry(self):
        self.navigator.results = [NavigationStatus.CANCELLED]
        run, _ = self.run_route()
        self.assertEqual(HuntState.CANCELLED, run.state)
        self.assertEqual(1, self.reads)
        self.assertEqual(("stop",), self.runtime.events[-1])

    def test_total_time_budget_propagates_failure(self):
        self.route = replace(self.route, max_seconds=1)
        with self.assertRaisesRegex(HuntAbort, "time limit"):
            self.run_route()
        self.assertEqual(("stop",), self.runtime.events[-1])

    def test_completed_route_emits_one_cleared_transition_per_camp(self):
        run, material = self.run_route()
        self.assertEqual(HuntState.COMPLETE, run.state)
        self.assertEqual(2, len(material.receipts))
        self.assertEqual(
            len(material.receipts),
            sum(event == ("CLEARED",) for event in self.runtime.events),
        )

    def test_cancel_before_pickup_refuses_new_input_and_receipt(self):
        pickup = Mock()
        material = MaterialRouteRuntime(
            self.runtime, self.route, 10,
            read_inventory=self.inventory, pickup=pickup,
            clock=lambda: self.runtime.time,
        )
        material.observe_inventory()
        self.runtime.cancel = True
        with self.assertRaises(HuntCancelled):
            material.camp_cleared(self.camps[0], Mock())
        pickup.assert_not_called()
        self.assertEqual(1, self.reads)
        self.assertEqual([], material.receipts)

    def test_cancel_during_pickup_prevents_inventory_ui_reentry(self):
        def cancel_on_pickup(_camp):
            self.runtime.cancel = True

        pickup = Mock(side_effect=cancel_on_pickup)
        material = MaterialRouteRuntime(
            self.runtime, self.route, 10,
            read_inventory=self.inventory, pickup=pickup,
            clock=lambda: self.runtime.time,
        )
        material.observe_inventory()
        with self.assertRaises(HuntCancelled):
            material.camp_cleared(self.camps[0], Mock())
        pickup.assert_called_once()
        self.assertEqual(1, self.reads)
        self.assertIsNotNone(material.observation)
        self.assertEqual([], material.receipts)

    def test_cancel_during_inventory_observation_is_not_a_receipt(self):
        def interrupted_read(material_id):
            self.runtime.cancel = True
            return InventoryObservation(
                material_id, 25, self.runtime.time, "interrupted", "ITEM_DETAIL"
            )

        material = MaterialRouteRuntime(
            self.runtime, self.route, 30,
            read_inventory=interrupted_read, pickup=Mock(),
            clock=lambda: self.runtime.time,
        )
        with self.assertRaises(HuntCancelled):
            material.observe_inventory()
        self.assertIsNone(material.observation)
        self.assertEqual([], material.receipts)

    def test_camp_receipt_requires_prior_inventory_baseline(self):
        pickup = Mock()
        material = MaterialRouteRuntime(
            self.runtime, self.route, 10,
            read_inventory=self.inventory, pickup=pickup,
            clock=lambda: self.runtime.time,
        )
        with self.assertRaisesRegex(HuntAbort, "baseline"):
            material.camp_cleared(self.camps[0], Mock())
        pickup.assert_not_called()
        self.assertEqual([], material.receipts)

    def manifest(self):
        (self.folder / "evidence.txt").write_text("Synthetic test data, not live evidence.", encoding="utf-8")
        return {"schema_version": 1, "status": "REVIEWED", "route_id": "offline-test-only",
                "surface_only": True, "state_id": 8, "floor_id": "",
                "profile": "profile.json", "profile_sha256": file_sha256(self.profile_path),
                "segments": [{"camp_id": s.camp_id, "spawn_ids": list(s.spawn_ids),
                              "waypoints": [[p.coordinate.x, p.coordinate.y] for p in s.waypoints],
                              "evidence": "evidence.txt"} for s in self.route.segments],
                "rejoin_radius": 10, "max_seconds": 60,
                "material_source": {"kind": "observed_mob_drop", "material_id": "fixture",
                                    "target_mob": "Target", "item_text": "Fixture Material",
                                    "evidence": "evidence.txt"},
                "evidence_sha256": {"evidence.txt": file_sha256(self.folder / "evidence.txt")},
                "inventory_reader": {"screen_feature": "fixture_detail", "item_text": "Fixture Material",
                                     "evidence": "evidence.txt", "label_box": [.1, .1, .3, .2],
                                     "quantity_box": [.1, .3, .3, .4],
                                     "open_steps": [{"screen_feature": "world", "key": "b"}],
                                     "close_steps": [{"screen_feature": "fixture_detail", "key": "esc"}],
                                     "pickup": {"evidence": "evidence.txt", "prompt_text": "Fixture Material"}}}

    def load_manifest(self, data):
        path = self.folder / "route.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return MaterialRoute.load(path)

    def test_only_explicitly_reviewed_bounded_manifest_loads(self):
        data = self.manifest()
        self.assertEqual(2, len(self.load_manifest(data).segments))
        for field, value in (("status", "LIVE_VERIFICATION_PENDING"), ("segments", []),
                             ("max_seconds", 1900), ("rejoin_radius", float("nan"))):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    self.load_manifest(dict(data, **{field: value}))

    def test_four_camps_and_unobserved_segment_or_material_rejected(self):
        data = self.manifest()
        for changed in (dict(data, segments=data["segments"] * 2),
                        dict(data, material_source={"kind": "guessed"}),
                        dict(data, segments=[dict(data["segments"][0], evidence="missing.png")])):
            with self.assertRaises(ValueError):
                self.load_manifest(changed)

    def test_stale_evidence_hash_and_unqualified_inventory_steps_rejected(self):
        data = self.manifest()
        (self.folder / "evidence.txt").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Stale"):
            self.load_manifest(data)
        data = self.manifest()
        data["inventory_reader"]["open_steps"] = [{"key": "b"}]
        with self.assertRaisesRegex(ValueError, "observed"):
            self.load_manifest(data)


class TestKnownBeacon(unittest.TestCase):
    def setUp(self):
        self.time = 0
        self.frames = iter(["BEACON_READY", "LOADING", "WORLD"])
        self.serial = 0
        self.issue = Mock()

    def wait(self, seconds):
        self.time += seconds

    def observe(self):
        self.time += .01
        self.serial += 1
        return TransitionObservation(next(self.frames), str(self.serial), self.time)

    def transition(self, **kwargs):
        qualification = Mock(spec=RuntimeQualification)
        qualification.data = {"known_beacons": {"fixture": {"destination": [8, "", 100, 0],
                                                           "destination_radius": 1,
                                                           "evidence": "offline-only.png"}},
                              "evidence_sha256": {"offline-only.png": "synthetic"}}
        return known_beacon_transition(
            observe=kwargs.get("observe", self.observe), issue=self.issue,
            locate=kwargs.get("locate", lambda: position(100)), destination=position(100),
            qualification=kwargs.get("qualification", qualification), profile_path="fixture-profile",
            beacon_id="fixture",
            profile=Mock(), runtime_version="fixture", game_version="fixture", source_root="fixture",
            clock=lambda: self.time, wait=self.wait, cancelled=lambda: False, timeout=1)

    def test_loading_and_fresh_destination_required_before_success(self):
        self.assertEqual(position(100), self.transition())
        self.issue.assert_called_once()

    def test_unknown_screen_never_repeats_issued_transition(self):
        self.frames = iter(["BEACON_READY", "UNKNOWN"])
        with self.assertRaisesRegex(HuntAbort, "Unknown"):
            self.transition()
        self.issue.assert_called_once()

    def test_stale_frames_and_wrong_destination_do_not_pass(self):
        with self.assertRaisesRegex(HuntAbort, "destination"):
            self.transition(locate=lambda: position(100, floor="B1"))
        self.issue.reset_mock()
        with self.assertRaisesRegex(HuntAbort, "stale"):
            self.transition(observe=lambda: TransitionObservation("BEACON_READY", "old", -10))
        self.issue.assert_not_called()

    def test_missing_runtime_qualification_refuses_beacon_input(self):
        qualification = Mock(spec=RuntimeQualification)
        qualification.assert_compatible.side_effect = ValueError("LIVE_VERIFICATION_PENDING")
        with self.assertRaisesRegex(ValueError, "LIVE_VERIFICATION_PENDING"):
            self.transition(qualification=qualification)
        self.issue.assert_not_called()


if __name__ == "__main__":
    unittest.main()
