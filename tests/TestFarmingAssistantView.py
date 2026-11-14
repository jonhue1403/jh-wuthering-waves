"""Offline read-only UI contract tests; no game session is started."""

import unittest

from src.automation.farming_selection import (
    CandidateRoute, DocumentedMobDrop, FarmingCatalog, FarmingTarget,
    ObservedMobDrop, TargetKind,
)
from src.automation.farming_view import FarmingAssistantView


class TestFarmingAssistantView(unittest.TestCase):
    def setUp(self):
        self.view = FarmingAssistantView()

    def test_material_search_and_mob_filter(self):
        self.assertEqual(["ff-mech-core"], [
            item["id"] for item in self.view.targets("material", "fF mEch")
        ])
        self.assertEqual(["geospider-s4"], [
            item["id"] for item in self.view.targets("mob", "geospider")
        ])
        self.assertEqual([], self.view.targets("mob", "FF Mech"))
        self.assertEqual(5, len(self.view.targets("mob")))

    def test_extended_material_catalog_preserves_featured_entry_and_preview_safety(self):
        listed = self.view.targets("material")
        self.assertEqual(27, len(listed))
        self.assertEqual("ff-mech-core", listed[0]["id"])
        self.assertEqual("SOURCE_DOCUMENTED", listed[0]["readiness"])
        self.assertEqual(27, len({entry["id"] for entry in listed}))
        for name, slug in (
            ("Premium Resonance Potion", "premium-resonance-potion"),
            ("FF Autopuppet Kernel", "ff-autopuppet-kernel"),
            ("Mysterious Code", "mysterious-code"),
            ("Waveworn Residue 239", "waveworn-residue-239"),
        ):
            with self.subTest(name=name):
                self.assertEqual(
                    [slug],
                    [entry["id"] for entry in self.view.targets("material", name)],
                )
                preview = self.view.preview("material", slug, "10")
                self.assertEqual(name, preview["target"]["name"])
                self.assertEqual("SOURCE_UNRESOLVED", preview["readiness"])
                self.assertEqual([], preview["source_candidates"])
                self.assertEqual([], preview["verified_mob_ids"])
                self.assertEqual([], preview["qualified_route_ids"])
                self.assertEqual("INVENTORY_TOTAL",
                                 preview["stop_criterion"]["mode"])
                self.assertEqual(10, preview["stop_criterion"]["requested"])
                self.assertEqual("PLANNED_ONLY",
                                 preview["stop_criterion"]["state"])
                self.assertIsNone(preview["owned_quantity"])
                self.assertFalse(preview["can_start"])
                self.assertFalse(preview["can_pause"])
                self.assertFalse(preview["can_stop"])
                self.assertNotIn("profile.json", repr(preview))

    def test_material_acquisition_method_reference_is_separate_from_route_readiness(self):
        for slug, kind in (
            ("premium-resonance-potion", "SIMULATION_TRAINING"),
            ("flawless-phlogiston", "FORGERY_CHALLENGE"),
            ("ff-autopuppet-kernel", "MOB_DROP"),
            ("mysterious-code", "EXPLORATION_OR_QUEST"),
            ("transducer", "HISTORICAL_SUBSCRIPTION"),
        ):
            with self.subTest(slug=slug):
                result = self.view.preview("material", slug)
                reference = result["acquisition_reference"]
                self.assertEqual("REFERENCE_ONLY", reference["status"])
                self.assertIn(kind, {m["kind"] for m in reference["methods"]})
                self.assertFalse(reference["can_start"])
                self.assertEqual("SOURCE_UNRESOLVED", result["readiness"])
                self.assertEqual([], result["qualified_route_ids"])
                self.assertFalse(result["can_start"])

    def test_preview_includes_source_provenance_without_execution(self):
        preview = self.view.preview("material", "ff-mech-core", "50")
        self.assertEqual("FF Mech Core", preview["target"]["name"])
        self.assertEqual(50, preview["desired_total"])
        self.assertIsNone(preview["owned_quantity"])
        self.assertEqual("SOURCE_DOCUMENTED", preview["readiness"])
        self.assertEqual(5, len(preview["source_candidates"]))
        self.assertTrue(all(
            entry["evidence_level"] == "documented_only"
            and entry["source_url"].startswith("https://")
            for entry in preview["source_candidates"]
        ))
        self.assertEqual("PREVIEW_ONLY", preview["run_state"])
        self.assertFalse(preview["can_start"])
        self.assertFalse(preview["can_pause"])
        self.assertFalse(preview["can_stop"])
        self.assertEqual("CALIBRATION_REQUIRED", preview["preflight"]["status"])
        self.assertEqual("VERSION_NOT_OBSERVED",
                         preview["preflight"]["game_version_check"])
        self.assertFalse(preview["preflight"]["can_start"])
        self.assertEqual(preview["preflight"]["next_action"], preview["next_step"])
        self.assertEqual([], preview["verified_mob_ids"])
        self.assertEqual([], preview["qualified_route_ids"])
        self.assertIn(preview["calibration"]["status"],
                      ("NO_LOCAL_RECEIPTS", "AUDIT_INCOMPLETE",
                       "LOCAL_CANDIDATES_ONLY"))
        self.assertFalse(preview["calibration"]["can_start"])
        self.assertNotIn("profile_path", repr(preview["calibration"]))
        # A developer may already have private candidate files on disk.
        # Their presence never authorizes this user-facing preview.
        self.assertIn(preview["route_calibration"]["status"],
                      ("NO_LOCAL_ROUTES", "LOCAL_ROUTE_CANDIDATES_ONLY",
                       "ROUTE_AUDIT_INCOMPLETE"))
        self.assertFalse(preview["route_calibration"]["can_start"])

    def test_stop_criterion_units_are_distinct_and_never_authorize(self):
        material = self.view.preview("material", "ff-mech-core", "50")
        mob = self.view.preview("mob", "geospider-s4", "3")
        self.assertEqual("INVENTORY_TOTAL", material["stop_criterion"]["mode"])
        self.assertEqual(50, material["stop_criterion"]["requested"])
        self.assertEqual("ENCOUNTER_LIMIT", mob["stop_criterion"]["mode"])
        self.assertEqual(3, mob["stop_criterion"]["requested"])
        for preview in (material, mob):
            criterion = preview["stop_criterion"]
            self.assertEqual("PLANNED_ONLY", criterion["state"])
            self.assertIsNone(criterion["observed"])
            self.assertIs(criterion["enforced"], False)
            self.assertFalse(preview["can_start"])
        no_goal = self.view.preview("mob", "geospider-s4")
        self.assertIsNone(no_goal["stop_criterion"]["requested"])
        self.assertIs(no_goal["stop_criterion"]["enforced"], False)

    def test_mob_selection_remains_unqualified(self):
        preview = self.view.preview("mob", "sabercat-reaver")
        self.assertEqual([], preview["source_candidates"])
        self.assertEqual("ROUTE_UNQUALIFIED", preview["readiness"])
        self.assertEqual("NO_MOB_ROUTE_QUALIFICATION", preview["calibration"]["status"])
        self.assertEqual("NO_MOB_ROUTE_QUALIFICATION",
                         preview["route_calibration"]["status"])
        self.assertFalse(preview["can_start"])
        self.assertEqual("NO_VERIFIED_MOB_ROUTE", preview["preflight"]["route_check"])
        self.assertFalse(preview["preflight"]["can_start"])
        self.assertIsNone(preview["desired_total"])

    def test_no_developer_paths_exposed_in_contract(self):
        preview = self.view.preview("material", "ff-mech-core")
        output = repr(preview)
        for secret in ("Hunt Profile", "Route Manifest", "Runtime Qualification",
                       "Plan Path", "profile_path", ".json", "C:\\", "Z:\\"):
            self.assertNotIn(secret, output)

    def test_invalid_search_and_identifiers_rejected(self):
        for kind in ("Material", "", "route", None, False):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.view.targets(kind, "")
        for query in (None, 1, "x" * 121):
            with self.subTest(query=query), self.assertRaises(ValueError):
                self.view.targets("material", query)
        with self.assertRaises(ValueError):
            self.view.preview("material", "unknown")
        with self.assertRaises(ValueError):
            self.view.preview("material", None)

    def test_goal_quantity_accepts_only_explicit_positive_integers(self):
        for goal in (1, "1", "9999999", 9_999_999, None, ""):
            with self.subTest(goal=goal):
                expected = None if goal is None or goal == "" else int(goal)
                self.assertEqual(
                    expected,
                    self.view.preview("material", "ff-mech-core", goal)["desired_total"],
                )
        for goal in (0, -1, "0", "1.2", "1/2", " 2", "+2", "１", "10000000",
                     10_000_000, 1.0, True, False, {}, []):
            with self.subTest(goal=goal), self.assertRaises(ValueError):
                self.view.preview("material", "ff-mech-core", goal)

    def test_even_verified_catalog_does_not_claim_live_authority(self):
        catalog = FarmingCatalog(
            targets=(
                FarmingTarget(TargetKind.MATERIAL, "mat", "Synthetic"),
                FarmingTarget(TargetKind.MOB, "mob", "Synthetic Enemy"),
            ),
            drops=(ObservedMobDrop("mat", "mob", "fake-observation"),),
            routes=(CandidateRoute("mob", "route", "fake-route"),),
            documented_drops=(
                DocumentedMobDrop("mat", "mob", "https://example.org/test"),
            ),
        )
        view = FarmingAssistantView(catalog)
        result = view.preview("material", "mat", 4)
        self.assertEqual("SOURCE_DOCUMENTED", result["readiness"])
        self.assertFalse(result["can_start"])
        self.assertEqual([], result["verified_mob_ids"])
        self.assertEqual([], result["qualified_route_ids"])


if __name__ == "__main__":
    unittest.main()
