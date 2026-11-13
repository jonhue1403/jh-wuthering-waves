"""Synthetic end-to-end local review manifest tests; no live game input."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from src.automation.farming_live_handoff import build_observation_handoff
from src.automation.farming_review_manifest import (
    ReviewManifestBlocked, prepare_readonly_review_manifest,
)
from src.automation.farming_runtime_capture import ReadOnlyFrameSnapshot
from src.automation.farming_capture_retention import RetainedReadOnlySnapshot
from src.overworld.qualification import REQUIRED_SOURCES


NOW = datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc)
PNG = b"\x89PNG\r\n\x1a\n"


class TestFarmingReviewManifest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.sources = root / "checkout"
        self.evidence = root / "private-evidence"
        self.sources.mkdir()
        self.evidence.mkdir()
        self.source_sha = {
            name: self.write(self.sources, name, ("synthetic:" + name).encode())
            for name in REQUIRED_SOURCES
        }
        self.binding_files = {
            "profile": "bindings/profile.json",
            "reference": "bindings/reference.png",
            "database": "bindings/database.json",
        }
        self.binding_sha = {
            name: self.write(self.evidence, path, ("synthetic:" + name).encode())
            for name, path in self.binding_files.items()
        }
        self.snapshots = {}
        self.retained = {}
        for frame_id, age in (("before", 40), ("after", 20)):
            data = PNG + ("synthetic-" + frame_id).encode()
            digest = sha256(data).hexdigest()
            when = (NOW - timedelta(seconds=age)).isoformat()
            self.snapshots[frame_id] = ReadOnlyFrameSnapshot(
                when, "3.0.4", 1280, 720, digest, data,
            )
            filename = f"farm-frame-{frame_id}.png"
            self.write(self.evidence, filename, data)
            self.retained[frame_id] = RetainedReadOnlySnapshot(
                filename, when, digest, len(data),
            )
        self.packet = build_observation_handoff({
            "schema_version": 1,
            "purpose": "SOURCE_DROP",
            "target_kind": "material",
            "target_id": "ff-mech-core",
            "game_mob_id": "000123",
            "game_version": "synthetic-1",
            "ok_script_version": "3.0.4",
            "session_id": "synthetic-session",
            "observed_at": (NOW - timedelta(seconds=10)).isoformat(),
            "stage": "SINGLE_CAMP",
            "route_id": "",
            "state_id": "map-a",
            "floor_id": "0",
            "frame_ids": list(self.snapshots),
            "frame_sha256": {
                name: value.frame_sha256 for name, value in self.snapshots.items()
            },
            "bindings_sha256": self.binding_sha,
            "source_sha256": self.source_sha,
            "inventory_before": 4,
            "inventory_after": 5,
        }, now=NOW)

    @staticmethod
    def write(root, relative, data):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return sha256(data).hexdigest()

    def prepare(self, **changes):
        return prepare_readonly_review_manifest(
            changes.get("packet", self.packet),
            changes.get("snapshots", self.snapshots),
            changes.get("retained", self.retained),
            source_root=changes.get("source_root", self.sources),
            evidence_root=changes.get("evidence_root", self.evidence),
            binding_files=changes.get("binding_files", self.binding_files),
            now=changes.get("now", NOW),
        )

    def test_actual_synthetic_bytes_are_correlated_not_approved(self):
        result = self.prepare()
        summary = result.public_summary()
        self.assertEqual("LOCAL_REVIEW_MANIFEST_ONLY", summary["status"])
        self.assertEqual(self.packet.record_sha256, result.packet_sha256)
        self.assertEqual(64, len(result.manifest_sha256))
        self.assertEqual(2, result.frame_count)
        self.assertEqual(
            len(self.source_sha) + len(self.binding_sha) + 2,
            result.checked_artifact_count,
        )
        self.assertTrue(summary["local_bytes_match_claim"])
        for flag in ("can_start", "game_origin_authenticated",
                     "game_version_authenticated", "inventory_receipt_verified",
                     "independent_review_complete", "route_qualified"):
            self.assertIs(summary[flag], False)
        self.assertNotIn(str(self.evidence), repr(summary))
        self.assertNotIn("synthetic-session", repr(summary))
        self.assertNotIn("farm-frame-", repr(summary))
        self.assertNotIn("inventory_before", repr(summary))

    def test_deterministic_manifest_with_same_originals(self):
        self.assertEqual(
            self.prepare().manifest_sha256, self.prepare().manifest_sha256,
        )

    def test_changed_memory_bytes_fail_before_file_audit(self):
        changed = dict(self.snapshots)
        changed["after"] = replace(changed["after"], frame_png=PNG + b"changed")
        with self.assertRaisesRegex(ReviewManifestBlocked, "SESSION_INCOHERENT"):
            self.prepare(snapshots=changed)

    def test_disk_frame_tampering_rejected(self):
        (self.evidence / self.retained["after"].relative_path).write_bytes(
            PNG + b"modified-after-retention"
        )
        with self.assertRaisesRegex(ReviewManifestBlocked, "ORIGINAL_FILES_NOT_VERIFIED"):
            self.prepare()

    def test_disk_source_tampering_rejected(self):
        source_name = next(iter(REQUIRED_SOURCES))
        (self.sources / source_name).write_bytes(b"changed")
        with self.assertRaisesRegex(ReviewManifestBlocked, "ORIGINAL_FILES_NOT_VERIFIED"):
            self.prepare()

    def test_disk_binding_tampering_rejected(self):
        (self.evidence / self.binding_files["profile"]).write_bytes(b"changed")
        with self.assertRaisesRegex(ReviewManifestBlocked, "ORIGINAL_FILES_NOT_VERIFIED"):
            self.prepare()

    def test_missing_private_frame_rejected(self):
        (self.evidence / self.retained["before"].relative_path).unlink()
        with self.assertRaisesRegex(ReviewManifestBlocked, "ORIGINAL_FILES_NOT_VERIFIED"):
            self.prepare()

    def test_forged_immutable_packet_rejected(self):
        forged = replace(self.packet, record_sha256="f" * 64)
        with self.assertRaisesRegex(ReviewManifestBlocked, "HANDOFF_INTEGRITY_INVALID"):
            self.prepare(packet=forged)

    def test_missing_or_ambiguous_frame_references_rejected(self):
        with self.assertRaisesRegex(ReviewManifestBlocked, "SESSION_INCOHERENT"):
            self.prepare(retained={"before": self.retained["before"]})
        altered = dict(self.retained)
        altered["after"] = replace(altered["after"], relative_path="farm-frame-before.png")
        with self.assertRaisesRegex(ReviewManifestBlocked, "SESSION_INCOHERENT"):
            self.prepare(retained=altered)

    def test_private_binding_path_cannot_escape_root(self):
        altered = dict(self.binding_files)
        altered["profile"] = "../outside.json"
        with self.assertRaisesRegex(ReviewManifestBlocked, "ORIGINAL_FILES_NOT_VERIFIED"):
            self.prepare(binding_files=altered)

    def test_expired_handoff_fails_closed(self):
        with self.assertRaisesRegex(ReviewManifestBlocked, "HANDOFF_INTEGRITY_INVALID"):
            self.prepare(now=NOW + timedelta(minutes=20))

    def test_naive_clock_rejected(self):
        with self.assertRaisesRegex(ReviewManifestBlocked, "CLOCK_INVALID"):
            self.prepare(now=NOW.replace(tzinfo=None))

    def test_other_observation_without_drop_receipt_is_not_promoted(self):
        # A nominal receipt packet remains a claim even with matching local bytes.
        summary = self.prepare().public_summary()
        self.assertFalse(summary["inventory_receipt_verified"])
        self.assertFalse(summary["can_start"])


if __name__ == "__main__":
    unittest.main()
