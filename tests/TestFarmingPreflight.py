"""Offline version/calibration preflight contracts. All outcomes deny execution."""

import unittest
from copy import deepcopy

from src.automation.farming_preflight import build_calibration_preflight
from src.automation.farming_view import FarmingAssistantView


class TestFarmingPreflight(unittest.TestCase):
    @staticmethod
    def summaries(*, overlap=True):
        receipts = {
            "material_id": "ff-mech-core",
            "status": "LOCAL_CANDIDATES_ONLY",
            "receipt_candidate_count": 1,
            "rejected_manifest_count": 0,
            "sources": [{
                "catalog_mob_id": "geospider-s4",
                "game_mob_id": "000123",
                "game_version": "synthetic-v1",
                "inventory_delta": 2,
                "evidence_level": "local_hash_match_only",
            }],
            "can_start": False,
        }
        routes = {
            "material_id": "ff-mech-core",
            "status": "LOCAL_ROUTE_CANDIDATES_ONLY",
            "route_candidate_count": 1,
            "rejected_manifest_count": 0,
            "routes": [{
                "route_id": "synthetic-route",
                "game_mob_id": "000123",
                "camp_count": 1,
                "evidence_level": "local_static_hash_match_only",
            }],
            "can_start": False,
        }
        comparison = {
            "status": "LOCAL_ID_OVERLAP_ONLY" if overlap else "NO_EXACT_ID_MATCH",
            "candidate_match_count": 1 if overlap else 0,
            "matches": [{"game_mob_id": "000123"}] if overlap else [],
            "can_start": False,
        }
        return receipts, routes, comparison

    def check(self, *summaries, hint=None):
        return build_calibration_preflight(
            "material", *summaries, game_version_hint=hint,
        )

    def test_matching_historical_version_is_not_live_permission(self):
        result = self.check(*self.summaries(), hint="synthetic-v1")
        self.assertEqual("CALIBRATION_REQUIRED", result["status"])
        self.assertEqual("HISTORICAL_ONLY", result["source_check"])
        self.assertEqual("STATIC_ONLY", result["route_check"])
        self.assertEqual("HISTORICAL_ID_OVERLAP_ONLY", result["identity_check"])
        self.assertEqual("HISTORICAL_EQUAL_UNVERIFIED", result["game_version_check"])
        self.assertEqual("NOT_CHECKED", result["runtime_qualification"])
        self.assertEqual("NOT_OBSERVED", result["fresh_inventory_check"])
        self.assertEqual("NOT_CHECKED", result["input_safety_check"])
        self.assertFalse(result["can_start"])
        self.assertIn("independently review", result["next_action"])
        self.assertNotIn("synthetic-route", repr(result))
        self.assertNotIn(".json", repr(result))

    def test_historical_version_mismatch_requests_reobservation(self):
        result = self.check(*self.summaries(), hint="synthetic-v2")
        self.assertEqual("HISTORICAL_VERSION_MISMATCH", result["game_version_check"])
        self.assertIn("current game version", result["next_action"])
        self.assertFalse(result["can_start"])

    def test_missing_runtime_hint_is_explicit_not_observed(self):
        result = self.check(*self.summaries())
        self.assertEqual("VERSION_NOT_OBSERVED", result["game_version_check"])
        self.assertFalse(result["can_start"])

    def test_no_matching_numeric_id_prevents_version_comparison(self):
        result = self.check(*self.summaries(overlap=False), hint="synthetic-v1")
        self.assertEqual("UNRESOLVED", result["identity_check"])
        self.assertEqual("VERSION_NOT_COMPARABLE", result["game_version_check"])
        self.assertIn("Reconcile exact numeric enemy IDs", result["next_action"])

    def test_missing_and_rejected_sources_prioritized(self):
        receipts, routes, match = self.summaries()
        receipts["receipt_candidate_count"] = 0
        receipts["sources"] = []
        receipts["status"] = "NO_LOCAL_RECEIPTS"
        result = self.check(receipts, routes, match)
        self.assertEqual("MISSING_OR_INVALID", result["source_check"])
        self.assertIn("inventory increase", result["next_action"])
        receipts["rejected_manifest_count"] = 1
        result = self.check(receipts, routes, match)
        self.assertIn("incomplete or rejected", result["next_action"])
        self.assertFalse(result["can_start"])

    def test_boolean_rejected_count_is_not_an_audit_clearance(self):
        receipts, routes, comparison = self.summaries()
        receipts["rejected_manifest_count"] = False
        result = self.check(receipts, routes, comparison)
        self.assertEqual("MISSING_OR_INVALID", result["source_check"])
        self.assertFalse(result["can_start"])
        routes["rejected_manifest_count"] = False
        receipts["rejected_manifest_count"] = 0
        result = self.check(receipts, routes, comparison)
        self.assertEqual("MISSING_OR_INVALID", result["route_check"])
        self.assertFalse(result["can_start"])

    def test_missing_route_prioritized_after_source(self):
        receipts, routes, comparison = self.summaries()
        routes["status"] = "NO_LOCAL_ROUTES"
        routes["route_candidate_count"] = 0
        routes["routes"] = []
        result = self.check(receipts, routes, comparison)
        self.assertEqual("MISSING_OR_INVALID", result["route_check"])
        self.assertIn("Calibrate a bounded route", result["next_action"])

    def test_conflicting_historical_versions_fail_closed(self):
        receipts, routes, comparison = self.summaries()
        receipts["sources"].append({
            **deepcopy(receipts["sources"][0]), "game_version": "synthetic-v2",
        })
        receipts["receipt_candidate_count"] = 2
        result = self.check(receipts, routes, comparison, hint="synthetic-v1")
        self.assertEqual("CONFLICTING_HISTORICAL_VERSIONS",
                         result["game_version_check"])
        self.assertFalse(result["can_start"])

    def test_unusable_version_hint_rejected(self):
        for hint in (True, 1, "", "x" * 33, "a b", "v1\\nroute", {},
                     "\\uFF11", "v1/path"):
            with self.subTest(hint=hint), self.assertRaises(ValueError):
                self.check(*self.summaries(), hint=hint)

    def test_diagnostic_input_never_echoed_in_output(self):
        result = self.check(*self.summaries(), hint="custom-version-hint")
        self.assertNotIn("custom-version-hint", repr(result))

    def test_non_mob_materials_show_source_specific_preflight(self):
        view = FarmingAssistantView()
        for material, family, source_state, phrase in (
            ("presto-helix", "DOMAIN_CHALLENGE_CANDIDATE",
             "DOMAIN_SOURCE_UNVERIFIED", "Forgery Challenge"),
            ("premium-resonance-potion", "DOMAIN_CHALLENGE_CANDIDATE",
             "DOMAIN_SOURCE_UNVERIFIED", "Simulation Training"),
            ("premium-tuner", "DOMAIN_CHALLENGE_CANDIDATE",
             "DOMAIN_SOURCE_UNVERIFIED", "Tacet Field"),
            ("mysterious-code", "MANUAL_REWARD_REFERENCE_ONLY",
             "NON_EXECUTABLE_REFERENCE", "quest"),
            ("transducer", "HISTORICAL_REFERENCE_ONLY",
             "NON_EXECUTABLE_REFERENCE", "historical"),
        ):
            with self.subTest(material=material):
                p = view.preview("material", material)
                preflight = p["preflight"]
                self.assertEqual(family, preflight["source_family"])
                self.assertEqual(source_state, preflight["source_check"])
                self.assertEqual("NOT_APPLICABLE", preflight["route_check"])
                self.assertEqual("NOT_APPLICABLE", preflight["identity_check"])
                self.assertIn(phrase.lower(), preflight["next_action"].lower())
                self.assertNotIn("enemy encounter", preflight["next_action"])
                self.assertNotIn("numeric enemy", preflight["next_action"])
                self.assertFalse(p["can_start"])
                self.assertFalse(p["can_stop"])
                self.assertEqual("PREVIEW_ONLY", p["run_state"])
                self.assertIn("no qualified current-game provider", p["reason"])

    def test_material_without_research_reference_never_gets_mob_assumption(self):
        from src.automation.farming_selection import (
            FarmingCatalog, FarmingTarget, TargetKind,
        )
        view = FarmingAssistantView(FarmingCatalog(targets=(
            FarmingTarget(TargetKind.MATERIAL, "local-test-item", "Local Test"),
        )))
        preview = view.preview("material", "local-test-item", "25")
        self.assertEqual("SOURCE_UNKNOWN",
                         preview["preflight"]["source_family"])
        self.assertEqual("SOURCE_UNRESOLVED",
                         preview["preflight"]["source_check"])
        self.assertEqual("NOT_APPLICABLE",
                         preview["preflight"]["route_check"])
        self.assertIsNone(preview["owned_quantity"])
        self.assertEqual(25, preview["desired_total"])
        self.assertIn("No documented acquisition method", preview["reason"])
        self.assertFalse(preview["can_start"])

    def test_non_mob_methods_skip_unrelated_enemy_and_route_audits(self):
        from unittest.mock import Mock
        receipts = Mock()
        routes = Mock()
        receipts.summary.side_effect = AssertionError("unrelated enemy receipt scanned")
        routes.summary.side_effect = AssertionError("unrelated surface route scanned")
        view = FarmingAssistantView(
            evidence_audit=receipts, route_audit=routes,
        )
        for material in ("presto-helix", "mysterious-code",
                         "premium-tuner", "transducer"):
            with self.subTest(material=material):
                preview = view.preview("material", material)
                self.assertEqual("NOT_APPLICABLE_TO_NON_MOB_MATERIAL",
                                 preview["calibration"]["status"])
                self.assertEqual("NOT_APPLICABLE_TO_NON_MOB_MATERIAL",
                                 preview["route_calibration"]["status"])
                self.assertEqual("NOT_APPLICABLE_TO_NON_MOB_MATERIAL",
                                 preview["reconciliation"]["status"])
                self.assertEqual([], preview["qualified_route_ids"])
                self.assertFalse(preview["can_start"])
        receipts.summary.assert_not_called()
        routes.summary.assert_not_called()

    def test_mixed_mob_and_domain_refs_never_authorize_or_autoselect(self):
        r = build_calibration_preflight(
            "material", *self.summaries(),
            acquisition_methods=["MOB_DROP", "FORGERY_CHALLENGE", "SYNTHESIS"],
        )
        self.assertEqual("MOB_DROP_CANDIDATE", r["source_family"])
        self.assertEqual("HISTORICAL_ONLY", r["source_check"])
        self.assertEqual("STATIC_ONLY", r["route_check"])
        self.assertFalse(r["can_start"])

    def test_unrecognized_duplicate_or_malformed_source_methods_rejected(self):
        for methods in (
            "MOB_DROP", [True], ["UNKNOWN"], ["MOB_DROP", "MOB_DROP"],
            ["MOB_DROP"] * 9, {"MOB_DROP"}, [None], [1],
        ):
            with self.subTest(methods=methods):
                with self.assertRaises(ValueError):
                    build_calibration_preflight(
                        "material", *self.summaries(),
                        acquisition_methods=methods,
                    )

    def test_mob_preview_has_distinct_blocking_checklist(self):
        result = build_calibration_preflight("mob", None, None, None)
        self.assertEqual("NO_VERIFIED_MOB_ROUTE", result["route_check"])
        self.assertEqual("VERSION_NOT_OBSERVED", result["game_version_check"])
        self.assertFalse(result["can_start"])

    def test_unknown_kind_refused(self):
        for kind in ("mob-hunt", "", [], False, None):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                build_calibration_preflight(kind, None, None, None)

    def test_view_integrates_path_free_preflight_for_both_kinds(self):
        view = FarmingAssistantView()
        for kind, target in (("material", "ff-mech-core"),
                             ("mob", "geospider-s4")):
            preview = view.preview(kind, target)
            check = preview["preflight"]
            self.assertEqual("CALIBRATION_REQUIRED", check["status"])
            self.assertFalse(check["can_start"])
            self.assertEqual(check["next_action"], preview["next_step"])
            self.assertFalse(preview["can_start"])
            for secret in ("Hunt Profile", "Route Manifest", "Runtime Qualification",
                           "C:\\\\", "Z:\\\\", "profile_path"):
                self.assertNotIn(secret, repr(check))


if __name__ == "__main__":
    unittest.main()
