"""Offline-only receipt/route association diagnostics; never a live permit."""

from copy import deepcopy
import unittest

from src.automation.farming_reconciliation import reconcile_candidate_audits
from src.automation.farming_selection import starting_catalog
from src.automation.farming_view import FarmingAssistantView


class StubAudit:
    def __init__(self, data):
        self.data = data

    def summary(self, material_id):
        return deepcopy(self.data)


class TestFarmingReconciliation(unittest.TestCase):
    def setUp(self):
        self.catalog = starting_catalog()

    @staticmethod
    def receipt(game="000123", mob="geospider-s4", version="synthetic-v1"):
        return {
            "catalog_mob_id": mob,
            "game_mob_id": game,
            "game_version": version,
            "inventory_delta": 2,
            "evidence_level": "local_hash_match_only",
        }

    @staticmethod
    def route(game="000123", route="synthetic-route"):
        return {
            "route_id": route,
            "game_mob_id": game,
            "camp_count": 1,
            "evidence_level": "local_static_hash_match_only",
        }

    def summaries(self, receipts=None, routes=None):
        receipts = [self.receipt()] if receipts is None else receipts
        routes = [self.route()] if routes is None else routes
        return (
            {
                "material_id": "ff-mech-core",
                "status": "LOCAL_CANDIDATES_ONLY" if receipts else "NO_LOCAL_RECEIPTS",
                "receipt_candidate_count": len(receipts),
                "rejected_manifest_count": 0,
                "sources": deepcopy(receipts),
                "can_start": False,
            },
            {
                "material_id": "ff-mech-core",
                "status": "LOCAL_ROUTE_CANDIDATES_ONLY" if routes else "NO_LOCAL_ROUTES",
                "route_candidate_count": len(routes),
                "rejected_manifest_count": 0,
                "routes": deepcopy(routes),
                "can_start": False,
            },
        )

    def compare(self, *summaries):
        return reconcile_candidate_audits(
            "ff-mech-core", *summaries, catalog=self.catalog,
        )

    def test_exact_numeric_id_overlap_remains_historical_only(self):
        result = self.compare(*self.summaries())
        self.assertEqual("LOCAL_ID_OVERLAP_ONLY", result["status"])
        self.assertEqual(1, result["candidate_match_count"])
        self.assertEqual("000123", result["matches"][0]["game_mob_id"])
        self.assertEqual("Geospider S4", result["matches"][0]["name"])
        self.assertEqual(1, result["matches"][0]["route_candidate_count"])
        self.assertEqual("local_numeric_id_overlap_only",
                         result["matches"][0]["evidence_level"])
        self.assertFalse(result["can_start"])
        self.assertNotIn("profile", repr(result).lower())
        self.assertNotIn(".json", repr(result))

    def test_exact_join_preserves_leading_zero_ids(self):
        receipt, route = self.summaries()
        route["routes"][0]["game_mob_id"] = "123"
        result = self.compare(receipt, route)
        self.assertEqual("NO_EXACT_ID_MATCH", result["status"])
        self.assertEqual(0, result["candidate_match_count"])
        self.assertEqual(1, result["unmatched_receipt_count"])
        self.assertEqual(1, result["unmatched_route_count"])
        self.assertFalse(result["can_start"])

    def test_numeric_enemy_id_mismatch_does_not_join_by_display_slug(self):
        receipts, routes = self.summaries()
        routes["routes"][0]["game_mob_id"] = "999999"
        self.assertEqual("NO_EXACT_ID_MATCH", self.compare(receipts, routes)["status"])

    def test_missing_one_side_or_no_candidates_blocks_matching(self):
        for receipt_rows, route_rows in (([], [self.route()]),
                                         ([self.receipt()], []), ([], [])):
            with self.subTest(receipts=receipt_rows, routes=route_rows):
                result = self.compare(*self.summaries(receipt_rows, route_rows))
                self.assertEqual("NO_SHARED_CANDIDATES", result["status"])
                self.assertFalse(result["can_start"])

    def test_material_scope_mismatch_is_rejected(self):
        receipt, route = self.summaries()
        route["material_id"] = "other-material"
        result = self.compare(receipt, route)
        self.assertEqual("TARGET_SCOPE_MISMATCH", result["status"])
        self.assertEqual([], result["matches"])

    def test_partial_or_rejected_audits_fail_closed(self):
        for field, value in (("receipt_status", "AUDIT_INCOMPLETE"),
                             ("route_status", "ROUTE_AUDIT_INCOMPLETE"),
                             ("receipt_rejected", 1), ("route_rejected", 1)):
            receipt, route = self.summaries()
            if field == "receipt_status":
                receipt["status"] = value
            elif field == "route_status":
                route["status"] = value
            elif field == "receipt_rejected":
                receipt["rejected_manifest_count"] = value
            else:
                route["rejected_manifest_count"] = value
            with self.subTest(field=field):
                result = self.compare(receipt, route)
                self.assertEqual("INCOMPLETE_AUDITS", result["status"])
                self.assertEqual([], result["matches"])
                self.assertFalse(result["can_start"])

    def test_conflicting_catalog_to_numeric_id_mapping_is_ambiguous(self):
        receipts = [
            self.receipt("000123", "geospider-s4"),
            self.receipt("000456", "geospider-s4"),
        ]
        result = self.compare(*self.summaries(receipts, [self.route("000123")]))
        self.assertEqual("AMBIGUOUS_RECEIPT_IDENTITIES", result["status"])
        self.assertFalse(result["can_start"])

    def test_conflicting_numeric_id_to_catalog_mapping_is_ambiguous(self):
        receipts = [
            self.receipt("000123", "geospider-s4"),
            self.receipt("000123", "sabercat-reaver"),
        ]
        result = self.compare(*self.summaries(receipts, [self.route("000123")]))
        self.assertEqual("AMBIGUOUS_RECEIPT_IDENTITIES", result["status"])
        self.assertEqual([], result["matches"])

    def test_conflicting_historical_game_versions_are_ambiguous(self):
        receipts = [self.receipt(version="synthetic-v1"),
                    self.receipt(version="synthetic-v2")]
        result = self.compare(*self.summaries(receipts, [self.route()]))
        self.assertEqual("AMBIGUOUS_RECEIPT_IDENTITIES", result["status"])

    def test_duplicate_consistent_receipts_do_not_inflate_pair_count(self):
        receipts = [self.receipt(), self.receipt()]
        routes = [self.route(route="route-one"), self.route(route="route-two")]
        result = self.compare(*self.summaries(receipts, routes))
        self.assertEqual(1, result["candidate_match_count"])
        self.assertEqual(2, result["matches"][0]["receipt_record_count"])
        self.assertEqual(2, result["matches"][0]["route_candidate_count"])

    def test_unknown_catalog_mob_is_not_associated_by_numeric_id(self):
        result = self.compare(*self.summaries(
            [self.receipt(mob="fabricated-mob")], [self.route()],
        ))
        self.assertEqual("UNRECOGNIZED_CATALOG_MOB", result["status"])
        self.assertEqual([], result["matches"])

    def test_forged_schema_or_unbounded_metadata_is_rejected(self):
        receipt, route = self.summaries()
        receipt["receipt_candidate_count"] = 99
        self.assertEqual("INVALID_AUDIT_SCHEMA",
                         self.compare(receipt, route)["status"])
        for key, value in (("game_mob_id", 123),
                           ("game_mob_id", "mob-name"),
                           ("inventory_delta", True),
                           ("evidence_level", "reviewed")):
            receipt, route = self.summaries()
            receipt["sources"][0][key] = value
            with self.subTest(key=key, value=value):
                result = self.compare(receipt, route)
                self.assertEqual("INVALID_AUDIT_SCHEMA", result["status"])
                self.assertFalse(result["can_start"])

    def test_status_contradicting_candidate_list_is_rejected(self):
        receipt, route = self.summaries()
        route["status"] = "NO_LOCAL_ROUTES"
        self.assertEqual("INVALID_AUDIT_SCHEMA",
                         self.compare(receipt, route)["status"])

    def test_preview_exposes_comparison_without_enabling_ui(self):
        receipt, route = self.summaries()
        view = FarmingAssistantView(
            evidence_audit=StubAudit(receipt),
            route_audit=StubAudit(route),
        )
        material = view.preview("material", "ff-mech-core", 5)
        self.assertEqual(1, material["reconciliation"]["candidate_match_count"])
        self.assertEqual("LOCAL_ID_OVERLAP_ONLY",
                         material["reconciliation"]["status"])
        self.assertEqual("PREVIEW_ONLY", material["run_state"])
        self.assertIsNone(material["owned_quantity"])
        self.assertFalse(material["can_start"])
        self.assertFalse(material["can_pause"])
        self.assertFalse(material["can_stop"])
        self.assertEqual([], material["qualified_route_ids"])
        self.assertEqual([], material["verified_mob_ids"])
        mob = view.preview("mob", "geospider-s4")
        self.assertEqual("NOT_APPLICABLE_MOB", mob["reconciliation"]["status"])
        self.assertFalse(mob["can_start"])

    def test_unknown_material_is_not_accepted(self):
        with self.assertRaises(ValueError):
            reconcile_candidate_audits(
                "not-a-real-item", *self.summaries(), catalog=self.catalog,
            )


if __name__ == "__main__":
    unittest.main()
