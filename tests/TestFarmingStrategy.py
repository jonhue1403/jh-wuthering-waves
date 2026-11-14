"""Source strategy regressions: a possible adapter is never a live permit."""
import unittest

from src.automation.farming_selection import (
    FarmingCatalog, FarmingTarget, SCREENSHOT_MATERIALS, TargetKind,
)
from src.automation.farming_strategy import (
    AcquisitionOption, SourceKind, Workflow,
    plan_material_acquisition, plan_mob_hunt,
)
from src.automation.farming_view import FarmingAssistantView


class TestFarmingStrategy(unittest.TestCase):
    def test_every_screenshot_material_has_preview_only_provider_options(self):
        for slug, _name in SCREENSHOT_MATERIALS:
            with self.subTest(material=slug):
                plan = plan_material_acquisition(slug)
                self.assertEqual("AWAITING_CURRENT_GAME_SOURCE_VALIDATION",
                                 plan["status"])
                self.assertEqual("material", plan["target_kind"])
                self.assertEqual(slug, plan["material_id"])
                self.assertEqual([], plan["qualified_provider_ids"])
                self.assertIsNone(plan["selected_provider"])
                self.assertFalse(plan["can_dispatch"])
                self.assertFalse(plan["can_start"])
                self.assertTrue(plan["possible_methods"])
                self.assertTrue(all(not option["can_execute"]
                                    for option in plan["possible_methods"]))
                self.assertTrue(all(
                    option["qualification"] == "CURRENT_GAME_EVIDENCE_REQUIRED"
                    for option in plan["possible_methods"]
                ))
                self.assertNotIn("profile.json", repr(plan))
                self.assertNotIn("Route Manifest", repr(plan))

    def test_domain_sources_are_separate_from_mob_routes(self):
        plans = (
            ("premium-tuner", "TACET_FIELD"),
            ("premium-resonance-potion", "SIMULATION_TRAINING"),
            ("presto-helix", "FORGERY_CHALLENGE"),
            ("ff-whisperin-core", "MOB_DROP"),
        )
        for slug, method in plans:
            with self.subTest(slug=slug):
                p = plan_material_acquisition(slug)
                options = [o for o in p["possible_methods"] if o["method"] == method]
                self.assertEqual(1, len(options))
                self.assertTrue(options[0]["automation_candidate_exists"])
                self.assertFalse(options[0]["can_execute"])
                self.assertIsNone(p["selected_provider"])

    def test_potential_resource_spending_is_not_silent(self):
        forgery = plan_material_acquisition("presto-helix")
        labels = {x["method"]: x["resource_policy"]
                  for x in forgery["possible_methods"]}
        self.assertEqual("POTENTIAL_WAVEPLATE_COST",
                         labels["FORGERY_CHALLENGE"])
        self.assertEqual("MATERIAL_CONSUMPTION_UNVERIFIED",
                         labels["SYNTHESIS"])

    def test_nonrepeatable_and_historical_references_have_no_automatic_task(self):
        for slug, expected in (("mysterious-code", "MANUAL_REWARD"),
                               ("transducer", "HISTORICAL_ONLY")):
            with self.subTest(slug=slug):
                plan = plan_material_acquisition(slug)
                self.assertEqual(0, plan["possible_automation_adapter_count"])
                self.assertEqual(expected, plan["possible_methods"][0]["workflow"])
                self.assertFalse(plan["possible_methods"][0]["automation_candidate_exists"])

    def test_ff_mech_core_has_possible_mob_but_no_executable_route(self):
        plan = plan_material_acquisition("ff-mech-core")
        mob = [m for m in plan["possible_methods"] if m["method"] == "MOB_DROP"]
        self.assertEqual(1, len(mob))
        self.assertEqual("BOUNDED_OVERWORLD", mob[0]["workflow"])
        self.assertIsNone(plan["selected_provider"])
        self.assertEqual([], plan["qualified_provider_ids"])
        self.assertFalse(plan["can_start"])

    def test_named_mob_cannot_be_executed_without_numeric_id_and_route(self):
        plan = plan_mob_hunt("geospider-s4")
        self.assertEqual("AWAITING_CURRENT_GAME_MOB_ROUTE", plan["status"])
        self.assertEqual("mob", plan["target_kind"])
        self.assertTrue(plan["possible_methods"][0]["automation_candidate_exists"])
        self.assertFalse(plan["possible_methods"][0]["can_execute"])
        self.assertFalse(plan["can_dispatch"])
        self.assertFalse(plan["can_start"])
        with self.assertRaises(ValueError):
            plan_mob_hunt("unrecognized-mob")

    def test_extended_catalog_has_safe_empty_provider_preview(self):
        catalog = FarmingCatalog(targets=(
            FarmingTarget(TargetKind.MATERIAL, "custom-item", "Custom Item"),
        ))
        result = FarmingAssistantView(catalog).preview(
            "material", "custom-item", "5"
        )
        self.assertEqual("NO_DOCUMENTED_PROVIDER",
                         result["acquisition_plan"]["status"])
        self.assertEqual([], result["acquisition_plan"]["possible_methods"])
        self.assertEqual("NO_RESEARCH_REFERENCE",
                         result["acquisition_reference"]["status"])
        self.assertFalse(result["can_start"])
        self.assertFalse(result["acquisition_plan"]["can_dispatch"])

    def test_invalid_source_and_unknown_kind_rejected(self):
        with self.assertRaises(ValueError):
            plan_material_acquisition("some-unknown-item")
        with self.assertRaises(ValueError):
            AcquisitionOption(
                kind="MOB_DROP", workflow=Workflow.BOUNDED_OVERWORLD,
                label="unverified", code_task_candidate="BoundedRouteTask",
                may_spend_waveplates=False, may_consume_inventory=False,
                source_url="https://example.org/item",
            ).public()

    def test_view_mob_does_not_require_material_acquisition_references(self):
        preview = FarmingAssistantView().preview("mob", "geospider-s4")
        plan = preview["acquisition_plan"]
        self.assertEqual("AWAITING_CURRENT_GAME_MOB_ROUTE", plan["status"])
        self.assertFalse(plan["can_dispatch"])
        self.assertEqual([], plan["qualified_provider_ids"])
        self.assertFalse(preview["can_start"])


if __name__ == "__main__":
    unittest.main()
