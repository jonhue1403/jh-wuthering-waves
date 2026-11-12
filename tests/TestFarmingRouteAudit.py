"""Synthetic route/profile audit regressions; NO gameplay or review authorization."""

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.automation.farming_route_audit import FarmingRouteAudit
from src.automation.farming_view import FarmingAssistantView


class TestFarmingRouteAudit(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.time = [0.0]
        self.audit = FarmingRouteAudit(
            self.folder, ttl_seconds=10, clock=lambda: self.time[0],
        )

    def save(self, name, data):
        (self.folder / name).write_text(
            json.dumps(data, sort_keys=True), encoding="utf-8",
        )

    def fixture(self):
        evidence = {}
        for name in ("source.png", "camp.png", "inventory.png", "pickup.png"):
            payload = ("synthetic-" + name).encode()
            (self.folder / name).write_bytes(payload)
            evidence[name] = sha256(payload).hexdigest()
        profile = {
            "surface_verified": True,
            "target_mob": "310000820",
            "state_id": 8,
            "floor_id": "",
            "spawn_ids": ["spawn-1"],
            "map_image": "synthetic-map.png",
            "kuro_database": "synthetic-db.db",
        }
        self.save("surface.profile.json", profile)
        profile_hash = sha256((self.folder / "surface.profile.json").read_bytes()).hexdigest()
        route = {
            "schema_version": 1,
            "status": "REVIEWED",
            "surface_only": True,
            "route_id": "synthetic-camp-route",
            "profile": "surface.profile.json",
            "profile_sha256": profile_hash,
            "state_id": 8,
            "floor_id": "",
            "rejoin_radius": 5.0,
            "max_seconds": 60,
            "segments": [{
                "camp_id": "camp-1",
                "spawn_ids": ["spawn-1"],
                "waypoints": [[0, 0], [1, 1]],
                "evidence": "camp.png",
            }],
            "evidence_sha256": evidence,
            "material_source": {
                "kind": "observed_mob_drop",
                "material_id": "ff-mech-core",
                "target_mob": "310000820",
                "item_text": "Synthetic item",
                "evidence": "source.png",
            },
            "inventory_reader": {
                "evidence": "inventory.png",
                "screen_feature": "synthetic-item-detail",
                "item_text": "Synthetic item",
                "label_box": [0.1, 0.1, 0.3, 0.3],
                "quantity_box": [0.4, 0.1, 0.6, 0.3],
                "open_steps": [{"screen_feature": "synthetic", "key": "b"}],
                "close_steps": [{"screen_feature": "synthetic", "key": "esc"}],
                "pickup": {"evidence": "pickup.png", "prompt_text": "Synthetic pickup"},
            },
        }
        self.save("test.route.json", route)
        return route, profile

    def refreshed(self):
        self.time[0] += 11
        return self.audit.summary("ff-mech-core")

    def test_empty_audit_is_read_only(self):
        result = self.audit.summary("ff-mech-core")
        self.assertEqual("NO_LOCAL_ROUTES", result["status"])
        self.assertEqual(0, result["route_candidate_count"])
        self.assertFalse(result["can_start"])

    def test_hash_matched_synthetic_route_still_cannot_start(self):
        self.fixture()
        result = self.audit.summary("ff-mech-core")
        self.assertEqual("LOCAL_ROUTE_CANDIDATES_ONLY", result["status"])
        self.assertEqual(1, result["route_candidate_count"])
        self.assertEqual(1, result["routes"][0]["camp_count"])
        self.assertEqual("310000820", result["routes"][0]["game_mob_id"])
        self.assertEqual("local_static_hash_match_only",
                         result["routes"][0]["evidence_level"])
        self.assertFalse(result["can_start"])
        self.assertNotIn(str(self.folder), repr(result))
        view = FarmingAssistantView(route_audit=self.audit)
        preview = view.preview("material", "ff-mech-core")
        self.assertEqual(1, preview["route_calibration"]["route_candidate_count"])
        self.assertEqual([], preview["qualified_route_ids"])
        self.assertFalse(preview["can_start"])

    def test_changed_profile_and_reference_are_rejected(self):
        self.fixture()
        (self.folder / "surface.profile.json").write_text("{}")
        result = self.audit.summary("ff-mech-core")
        self.assertEqual(1, result["rejected_manifest_count"])
        self.assertEqual(0, result["route_candidate_count"])
        self.fixture()
        (self.folder / "camp.png").write_bytes(b"tampered")
        result = self.refreshed()
        self.assertEqual(1, result["rejected_manifest_count"])
        self.assertFalse(result["can_start"])

    def test_target_layer_source_and_spawn_mismatches_fail_closed(self):
        mutations = (
            lambda d: d.update(state_id=9),
            lambda d: d["material_source"].update(target_mob="unknown"),
            lambda d: d["material_source"].update(material_id="../../oops"),
            lambda d: d["segments"][0].update(spawn_ids=["wrong"]),
            lambda d: d["segments"][0].update(waypoints=[[0, 0], [float("nan"), 1]]),
            lambda d: d.update(max_seconds=2000),
            lambda d: d.update(surface_only=False),
            lambda d: d.update(status="DRAFT"),
            lambda d: d["inventory_reader"].update(item_text="Different item"),
        )
        for mutate in mutations:
            with self.subTest(mutate=repr(mutate)):
                data, _ = self.fixture()
                mutate(data)
                self.save("test.route.json", data)
                result = self.refreshed()
                self.assertEqual(0, result["route_candidate_count"])
                self.assertEqual(1, result["rejected_manifest_count"])

    def test_path_traversal_and_missing_evidence_are_rejected(self):
        for change in ("../outside.json", "C:\\Windows\\profile.json", "missing.json"):
            with self.subTest(profile=change):
                data, _ = self.fixture()
                data["profile"] = change
                self.save("test.route.json", data)
                self.assertEqual(1, self.refreshed()["rejected_manifest_count"])
        data, _ = self.fixture()
        data["material_source"]["evidence"] = "nonexistent.png"
        self.save("test.route.json", data)
        self.assertEqual(1, self.refreshed()["rejected_manifest_count"])

    def test_cache_refreshes_after_expiration(self):
        self.fixture()
        self.assertEqual(1, self.audit.summary("ff-mech-core")["route_candidate_count"])
        (self.folder / "source.png").write_bytes(b"changed")
        self.time[0] += 5
        self.assertEqual(1, self.audit.summary("ff-mech-core")["route_candidate_count"])
        self.assertEqual(0, self.refreshed()["route_candidate_count"])

    def test_incomplete_scan_never_qualifies_any_route(self):
        for index in range(9):
            (self.folder / f"overflow-{index:02}.route.json").write_text("{}")
        result = self.audit.summary("ff-mech-core")
        self.assertEqual("ROUTE_AUDIT_INCOMPLETE", result["status"])
        self.assertEqual(8, result["rejected_manifest_count"])
        self.assertFalse(result["can_start"])

    def test_duplicate_route_ids_are_rejected_without_double_counting(self):
        self.fixture()
        # A second manifest filename is not a second distinct route.
        (self.folder / "second.route.json").write_bytes(
            (self.folder / "test.route.json").read_bytes()
        )
        result = self.audit.summary("ff-mech-core")
        self.assertEqual(1, result["route_candidate_count"])
        self.assertEqual(1, result["rejected_manifest_count"])
        self.assertFalse(result["can_start"])

    def test_duplicate_nested_manifest_json_key_is_rejected(self):
        self.fixture()
        path = self.folder / "test.route.json"
        content = path.read_text(encoding="utf-8")
        self.assertIn('"kind": "observed_mob_drop"', content)
        content = content.replace(
            '"kind": "observed_mob_drop"',
            '"kind": "observed_mob_drop", "kind": "observed_mob_drop"',
            1,
        )
        path.write_text(content, encoding="utf-8")
        result = self.audit.summary("ff-mech-core")
        self.assertEqual(0, result["route_candidate_count"])
        self.assertEqual(1, result["rejected_manifest_count"])

    def test_duplicate_profile_json_key_rejected_even_with_fresh_hash(self):
        data, profile = self.fixture()
        profile_path = self.folder / "surface.profile.json"
        raw = profile_path.read_text(encoding="utf-8")
        self.assertIn('"target_mob": "310000820"', raw)
        raw = raw.replace(
            '"target_mob": "310000820"',
            '"target_mob": "310000820", "target_mob": "310000820"',
            1,
        )
        profile_path.write_text(raw, encoding="utf-8")
        data["profile_sha256"] = sha256(raw.encode("utf-8")).hexdigest()
        self.save("test.route.json", data)
        result = self.audit.summary("ff-mech-core")
        self.assertEqual(0, result["route_candidate_count"])
        self.assertEqual(1, result["rejected_manifest_count"])

    def test_nonstandard_nonfinite_literal_is_rejected(self):
        data, _ = self.fixture()
        data["rejoin_radius"] = float("inf")
        self.save("test.route.json", data)
        result = self.audit.summary("ff-mech-core")
        self.assertEqual(0, result["route_candidate_count"])
        self.assertEqual(1, result["rejected_manifest_count"])

    def test_unknown_material_cannot_choose_arbitrary_local_file(self):
        for material in ("../../secret", "", None, "FF Mech Core"):
            with self.subTest(material=material), self.assertRaises(ValueError):
                self.audit.summary(material)

    def test_mob_selection_cannot_infer_numeric_game_id_from_catalog_slug(self):
        self.fixture()
        view = FarmingAssistantView(route_audit=self.audit)
        preview = view.preview("mob", "geospider-s4")
        self.assertEqual("NO_MOB_ROUTE_QUALIFICATION",
                         preview["route_calibration"]["status"])
        self.assertFalse(preview["can_start"])


if __name__ == "__main__":
    unittest.main()
