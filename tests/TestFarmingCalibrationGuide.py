"""Synthetic tests for path-free, non-authorizing calibration guidance."""

import unittest

from src.automation.farming_calibration_guide import build_calibration_guide
from src.automation.farming_preflight import build_calibration_preflight
from src.automation.farming_view import FarmingAssistantView


class TestFarmingCalibrationGuide(unittest.TestCase):
    def material_preflight(self, *, source=False, route=False, overlap=False):
        receipts = {
            "status": "LOCAL_CANDIDATES_ONLY" if source else "NO_LOCAL_RECEIPTS",
            "receipt_candidate_count": 1 if source else 0,
            "rejected_manifest_count": 0,
            "sources": [],
            "can_start": False,
        }
        routes = {
            "status": "LOCAL_ROUTE_CANDIDATES_ONLY" if route else "NO_LOCAL_ROUTES",
            "route_candidate_count": 1 if route else 0,
            "rejected_manifest_count": 0,
            "routes": [],
            "can_start": False,
        }
        comparison = {
            "status": "LOCAL_ID_OVERLAP_ONLY" if overlap else "NO_SHARED_CANDIDATES",
            "candidate_match_count": 1 if overlap else 0,
            "matches": [],
            "can_start": False,
        }
        return build_calibration_preflight("material", receipts, routes, comparison)

    def test_fresh_material_guide_prioritizes_receipt_evidence(self):
        guide = build_calibration_guide("material", self.material_preflight())
        self.assertEqual("GUIDED_READ_ONLY", guide["mode"])
        self.assertEqual("observe-material-drop", guide["next_step_id"])
        self.assertEqual(7, len(guide["steps"]))
        self.assertEqual(0, guide["verified_step_count"])
        self.assertFalse(guide["can_start"])
        self.assertTrue(all(
            step["status"] == "NEEDS_LIVE_VERIFICATION"
            for step in guide["steps"]
        ))

    def test_historical_source_does_not_count_as_complete(self):
        guide = build_calibration_guide(
            "material", self.material_preflight(source=True)
        )
        self.assertEqual("calibrate-reviewed-route", guide["next_step_id"])
        self.assertEqual(
            "HISTORICAL_REFERENCE_ONLY", guide["steps"][0]["status"]
        )
        self.assertEqual(0, guide["verified_step_count"])

    def test_missing_route_prioritized_before_identity_cross_check(self):
        # ID matching is not meaningful until both local audits have candidates.
        guide = build_calibration_guide(
            "material", self.material_preflight(source=True, route=False, overlap=True)
        )
        self.assertEqual("calibrate-reviewed-route", guide["next_step_id"])
        self.assertFalse(guide["can_start"])

    def test_route_present_but_no_id_overlap_focuses_identity(self):
        guide = build_calibration_guide(
            "material", self.material_preflight(source=True, route=True)
        )
        self.assertEqual("identify-game-enemy", guide["next_step_id"])

    def test_static_evidence_never_authorizes_execution(self):
        guide = build_calibration_guide(
            "material", self.material_preflight(source=True, route=True, overlap=True)
        )
        self.assertEqual("observe-installed-version", guide["next_step_id"])
        self.assertEqual("HISTORICAL_REFERENCE_ONLY", guide["steps"][0]["status"])
        self.assertEqual("HISTORICAL_REFERENCE_ONLY", guide["steps"][1]["status"])
        self.assertEqual("HISTORICAL_REFERENCE_ONLY", guide["steps"][3]["status"])
        self.assertFalse(guide["can_start"])

    def test_mob_guide_requires_game_identity_without_material_receipts(self):
        preflight = build_calibration_preflight("mob", None, None, None)
        guide = build_calibration_guide("mob", preflight)
        self.assertEqual(6, len(guide["steps"]))
        self.assertEqual("identify-game-enemy", guide["next_step_id"])
        self.assertFalse(any(s["id"] == "observe-material-drop" for s in guide["steps"]))
        self.assertFalse(guide["can_start"])

    def test_invalid_preflight_can_never_trick_guide_into_ready(self):
        preflight = self.material_preflight()
        for value in (None, {}, {"status": "READY", "can_start": False},
                      {**preflight, "can_start": True},
                      {**preflight, "source_check": "LIVE_VERIFIED"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_calibration_guide("material", value)
        for kind in (False, "", "route", None, 0):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                build_calibration_guide(kind, preflight)

    def test_view_exposes_guide_for_both_kinds_but_never_paths_or_permission(self):
        view = FarmingAssistantView()
        for kind, target_id in (
            ("material", "ff-mech-core"),
            ("mob", "geospider-s4"),
        ):
            with self.subTest(kind=kind):
                preview = view.preview(kind, target_id)
                guide = preview["calibration_guide"]
                self.assertEqual("GUIDED_READ_ONLY", guide["mode"])
                self.assertIn(guide["next_step_id"], [s["id"] for s in guide["steps"]])
                self.assertEqual(0, guide["verified_step_count"])
                self.assertFalse(guide["can_start"])
                self.assertFalse(preview["can_start"])
                self.assertEqual("PREVIEW_ONLY", preview["run_state"])
                for blocked in (
                    "Hunt Profile", "Route Manifest", "Runtime Qualification",
                    "profile_path", ".json", "C:\\", "Z:\\",
                ):
                    self.assertNotIn(blocked, repr(guide))


if __name__ == "__main__":
    unittest.main()
