"""Community source references are discovery-only, not live farming permits."""
import unittest

from src.automation.farming_acquisition_reference import (
    AcquisitionReference, SourceKind, documented_acquisition,
)
from src.automation.farming_selection import SCREENSHOT_MATERIALS
from src.automation.farming_view import FarmingAssistantView


class TestFarmingAcquisitionReference(unittest.TestCase):
    def test_every_screenshot_material_has_reference_only_methods(self):
        self.assertEqual(27, len(SCREENSHOT_MATERIALS))
        for slug, _name in SCREENSHOT_MATERIALS:
            with self.subTest(material=slug):
                record = documented_acquisition(slug)
                self.assertEqual("REFERENCE_ONLY", record["status"])
                self.assertFalse(record["can_start"])
                self.assertTrue(record["requires_game_verification"])
                self.assertEqual([], record["executable_source_ids"])
                self.assertGreaterEqual(len(record["methods"]), 1)
                for method in record["methods"]:
                    self.assertIn(method["kind"], {kind.value for kind in SourceKind})
                    self.assertEqual("NOT_OBSERVED_CURRENT_GAME",
                                     method["qualification"])
                    self.assertTrue(method["reference_url"].startswith("https://"))
                    self.assertNotIn("profile.json", repr(method))

    def test_mob_sources_are_not_assumed_for_every_material(self):
        for slug in (
            "mysterious-code", "premium-tuner", "premium-sealed-tube",
            "presto-helix", "premium-resonance-potion", "transducer",
        ):
            with self.subTest(slug=slug):
                self.assertFalse(documented_acquisition(slug)["possible_mob_source"])
        for slug in ("ff-mech-core", "ff-whisperin-core", "ff-autopuppet-kernel"):
            with self.subTest(slug=slug):
                self.assertTrue(documented_acquisition(slug)["possible_mob_source"])

    def test_quest_only_item_remains_non_executable(self):
        record = documented_acquisition("mysterious-code")
        self.assertEqual(
            [SourceKind.EXPLORATION.value],
            [method["kind"] for method in record["methods"]],
        )
        view = FarmingAssistantView()
        preview = view.preview("material", "mysterious-code", "2")
        self.assertEqual("SOURCE_UNRESOLVED", preview["readiness"])
        self.assertFalse(preview["can_start"])
        self.assertEqual([], preview["qualified_route_ids"])

    def test_invalid_references_fail_closed(self):
        with self.assertRaises(ValueError):
            documented_acquisition("not-a-screenshot-item")
        for url in ("http://example.org", "https://", "https://u:p@example.org/a",
                    "https://example.org/has space"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                AcquisitionReference("test-item", SourceKind.MOB_DROP, "Test", url)
        with self.assertRaises(ValueError):
            AcquisitionReference("test-item", "MOB_DROP", "Test",
                                 "https://example.org")

    def test_27_view_previews_remain_blocked_despite_references(self):
        view = FarmingAssistantView()
        for slug, _ in SCREENSHOT_MATERIALS:
            with self.subTest(material=slug):
                preview = view.preview("material", slug)
                acquisition = preview["acquisition_reference"]
                self.assertEqual("REFERENCE_ONLY", acquisition["status"])
                self.assertFalse(acquisition["can_start"])
                self.assertFalse(preview["can_start"])
                self.assertFalse(preview["can_pause"])
                self.assertFalse(preview["can_stop"])
                self.assertIsNone(preview["owned_quantity"])
                self.assertFalse(preview["stop_criterion"]["enforced"])

    def test_mob_view_does_not_inherit_material_acquisition_claims(self):
        preview = FarmingAssistantView().preview("mob", "geospider-s4")
        guidance = preview["acquisition_reference"]
        self.assertEqual("NOT_APPLICABLE_TO_MOB", guidance["status"])
        self.assertEqual([], guidance["methods"])
        self.assertFalse(guidance["can_start"])


if __name__ == "__main__":
    unittest.main()
