"""Offline receipt-evidence intake tests: no live game observations claimed."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.automation.farming_evidence import FarmingEvidenceAudit
from src.automation.farming_view import FarmingAssistantView


class TestFarmingEvidence(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.clock_value = [0.0]
        self.audit = FarmingEvidenceAudit(
            self.folder, ttl_seconds=10, clock=lambda: self.clock_value[0],
        )

    def payload(self):
        before = b"synthetic-inventory-before"
        after = b"synthetic-inventory-after"
        (self.folder / "before.png").write_bytes(before)
        (self.folder / "after.png").write_bytes(after)
        return {
            "schema_version": 1,
            "status": "REVIEWED",
            "independent_review": True,
            "material_id": "ff-mech-core",
            "catalog_mob_id": "geospider-s4",
            "game_mob_id": "12345",
            "game_version": "synthetic-test",
            "session_id": "offline-unit-test-only",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "inventory_before": 3,
            "inventory_after": 4,
            "frame_before": "frame-a",
            "frame_after": "frame-b",
            "inventory_before_image": "before.png",
            "inventory_after_image": "after.png",
            "evidence_sha256": {
                "before.png": sha256(before).hexdigest(),
                "after.png": sha256(after).hexdigest(),
            },
        }

    def save(self, data):
        (self.folder / "synthetic.json").write_text(
            json.dumps(data), encoding="utf-8",
        )

    def test_empty_directory_never_claims_verified_material(self):
        summary = self.audit.summary("ff-mech-core")
        self.assertEqual("NO_LOCAL_RECEIPTS", summary["status"])
        self.assertEqual(0, summary["receipt_candidate_count"])
        self.assertFalse(summary["can_start"])

    def test_hash_matched_synthetic_receipt_remains_untrusted_candidate(self):
        self.save(self.payload())
        summary = self.audit.summary("ff-mech-core")
        self.assertEqual("LOCAL_CANDIDATES_ONLY", summary["status"])
        self.assertEqual(1, summary["receipt_candidate_count"])
        self.assertEqual(1, summary["sources"][0]["inventory_delta"])
        self.assertEqual("local_hash_match_only", summary["sources"][0]["evidence_level"])
        self.assertFalse(summary["can_start"])
        self.assertNotIn(self.temp.name, repr(summary))
        view = FarmingAssistantView(evidence_audit=self.audit)
        preview = view.preview("material", "ff-mech-core", 8)
        self.assertEqual(1, preview["calibration"]["receipt_candidate_count"])
        self.assertEqual([], preview["verified_mob_ids"])
        self.assertEqual([], preview["qualified_route_ids"])
        self.assertEqual("SOURCE_DOCUMENTED", preview["readiness"])
        self.assertFalse(preview["can_start"])

    def test_changed_image_rejects_receipt(self):
        self.save(self.payload())
        (self.folder / "after.png").write_bytes(b"changed evidence")
        summary = self.audit.summary("ff-mech-core")
        self.assertEqual(0, summary["receipt_candidate_count"])
        self.assertEqual(1, summary["rejected_manifest_count"])

    def test_old_and_future_timestamps_rejected(self):
        for when in (datetime.now(timezone.utc) - timedelta(days=31),
                     datetime.now(timezone.utc) + timedelta(hours=2)):
            with self.subTest(when=when):
                data = self.payload()
                data["observed_at"] = when.isoformat()
                self.save(data)
                self.clock_value[0] += 11
                self.assertEqual(1, self.audit.summary("ff-mech-core")[
                    "rejected_manifest_count"
                ])

    def test_ambiguous_identity_and_unobserved_gain_rejected(self):
        changes = (
            {"game_mob_id": "Geospider S4"},
            {"catalog_mob_id": "unknown/mob"},
            {"inventory_after": 3},
            {"inventory_after": -5},
            {"frame_after": "frame-a"},
            {"independent_review": False},
            {"status": "DRAFT"},
            {"game_version": ""},
        )
        for change in changes:
            with self.subTest(change=change):
                data = self.payload()
                data.update(change)
                self.save(data)
                self.clock_value[0] += 11
                self.assertEqual(0, self.audit.summary("ff-mech-core")[
                    "receipt_candidate_count"
                ])

    def test_screenshot_traversal_and_missing_hash_rejected(self):
        for change in (
            {"inventory_before_image": "../other.png"},
            {"inventory_before_image": "C:\\photo.png"},
            {"inventory_before_image": "after.png"},
            {"evidence_sha256": {"before.png": "x" * 64}},
        ):
            with self.subTest(change=change):
                data = self.payload()
                data.update(change)
                self.save(data)
                self.clock_value[0] += 11
                self.assertEqual(1, self.audit.summary("ff-mech-core")[
                    "rejected_manifest_count"
                ])

    def test_cache_expires_and_rejects_modified_evidence(self):
        self.save(self.payload())
        self.assertEqual(1, self.audit.summary("ff-mech-core")[
            "receipt_candidate_count"
        ])
        (self.folder / "after.png").write_bytes(b"altered")
        self.clock_value[0] += 5
        self.assertEqual(1, self.audit.summary("ff-mech-core")[
            "receipt_candidate_count"
        ])
        self.clock_value[0] += 6
        self.assertEqual(0, self.audit.summary("ff-mech-core")[
            "receipt_candidate_count"
        ])

    def test_bounded_scan_does_not_claim_complete_when_overflow(self):
        for index in range(25):
            (self.folder / f"invalid-{index:02}.json").write_text("{}")
        summary = self.audit.summary("ff-mech-core")
        self.assertEqual("AUDIT_INCOMPLETE", summary["status"])
        self.assertEqual(0, summary["receipt_candidate_count"])
        self.assertEqual(24, summary["rejected_manifest_count"])

    def test_invalid_material_id_rejected(self):
        for target in ("../../secret", "", "ff mech core", None):
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.audit.summary(target)

    def test_mob_view_does_not_infer_material_from_inventory_receipts(self):
        self.save(self.payload())
        view = FarmingAssistantView(evidence_audit=self.audit)
        preview = view.preview("mob", "geospider-s4")
        self.assertEqual("NO_MOB_ROUTE_QUALIFICATION", preview["calibration"]["status"])
        self.assertFalse(preview["can_start"])


if __name__ == "__main__":
    unittest.main()
