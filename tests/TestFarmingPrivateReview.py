"""Offline private-capture -> review-manifest integration; no game runtime."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from src.automation.farming_live_handoff import build_observation_handoff
from src.automation.farming_private_capture import PrivateReadOnlyCapture
from src.automation.farming_private_review import (
    PrivateReviewBlocked, review_private_captures,
)
from src.automation.farming_runtime_capture import ReadOnlyFrameSnapshot
from src.automation.farming_capture_retention import RetainedReadOnlySnapshot
from src.overworld.qualification import REQUIRED_SOURCES


NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
PNG = b"\x5cx89PNG\x5cr\x5cn\x5cx1a\x5cn"


class TestFarmingPrivateReview(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.sources = root / "checkout"
        self.evidence = root / "review-private"
        self.sources.mkdir()
        self.evidence.mkdir()
        self.source_hashes = {
            name: self.write(self.sources, name, ("source:" + name).encode())
            for name in REQUIRED_SOURCES
        }
        self.binding_files = {
            "profile": "bindings/profile.json",
            "reference": "bindings/reference.png",
            "database": "bindings/database.json",
        }
        self.binding_hashes = {
            name: self.write(self.evidence, relative, ("binding:" + name).encode())
            for name, relative in self.binding_files.items()
        }
        self.captures = {}
        for frame_id, seconds_ago in (("before", 40), ("after", 20)):
            data = PNG + frame_id.encode() + b"-synthetic"
            digest = sha256(data).hexdigest()
            when = (NOW - timedelta(seconds=seconds_ago)).isoformat()
            snapshot = ReadOnlyFrameSnapshot(
                when, "3.0.4", 1280, 720, digest, data,
            )
            path = f"farm-frame-{frame_id}.png"
            self.write(self.evidence, path, data)
            retained = RetainedReadOnlySnapshot(path, when, digest, len(data))
            self.captures[frame_id] = PrivateReadOnlyCapture(snapshot, retained)
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
            "frame_ids": list(self.captures),
            "frame_sha256": {
                name: value.snapshot.frame_sha256
                for name, value in self.captures.items()
            },
            "bindings_sha256": self.binding_hashes,
            "source_sha256": self.source_hashes,
            "inventory_before": 4,
            "inventory_after": 5,
        }, now=NOW)

    @staticmethod
    def write(root, relative, data):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return sha256(data).hexdigest()

    def review(self, **overrides):
        return review_private_captures(
            overrides.get("packet", self.packet),
            overrides.get("captures", self.captures),
            source_root=overrides.get("source_root", self.sources),
            evidence_root=overrides.get("evidence_root", self.evidence),
            binding_files=overrides.get("binding_files", self.binding_files),
            now=overrides.get("now", NOW),
        )

    def test_original_bytes_correlate_without_execution_approval(self):
        outcome = self.review().public_summary()
        self.assertEqual("LOCAL_REVIEW_MANIFEST_ONLY", outcome["status"])
        self.assertTrue(outcome["local_bytes_match_claim"])
        self.assertEqual(2, outcome["frame_count"])
        for key in ("can_start", "game_origin_authenticated",
                    "game_version_authenticated", "inventory_receipt_verified",
                    "route_qualified", "independent_review_complete"):
            self.assertIs(outcome[key], False)
        self.assertNotIn(str(self.evidence), repr(outcome))
        self.assertNotIn("synthetic-session", repr(outcome))
        self.assertNotIn("farm-frame-", repr(outcome))

    def test_original_review_manifest_is_deterministic(self):
        self.assertEqual(self.review().manifest_sha256, self.review().manifest_sha256)

    def test_missing_or_extra_frame_fails_closed(self):
        for captures in (
            {"before": self.captures["before"]},
            {**self.captures, "unknown": self.captures["before"]},
        ):
            with self.assertRaisesRegex(PrivateReviewBlocked, "CAPTURE_FRAME_IDS_MISMATCH"):
                self.review(captures=captures)

    def test_direct_unverified_frame_object_is_rejected(self):
        with self.assertRaisesRegex(PrivateReviewBlocked, "PRIVATE_CAPTURE_INVALID"):
            self.review(captures={**self.captures, "after": object()})

    def test_same_capture_cannot_be_reused_for_both_frames(self):
        with self.assertRaisesRegex(PrivateReviewBlocked, "DUPLICATE_PRIVATE_CAPTURE"):
            self.review(captures={"before": self.captures["before"],
                                  "after": self.captures["before"]})

    def test_modified_memory_frame_fails(self):
        changed = replace(self.captures["after"].snapshot, frame_png=PNG + b"changed")
        altered = replace(self.captures["after"], snapshot=changed)
        with self.assertRaisesRegex(PrivateReviewBlocked, "PRIVATE_REVIEW_NOT_QUALIFIED"):
            self.review(captures={**self.captures, "after": altered})

    def test_modified_retention_receipt_fails(self):
        altered = replace(self.captures["after"].retained, frame_sha256="0" * 64)
        capture = replace(self.captures["after"], retained=altered)
        with self.assertRaisesRegex(PrivateReviewBlocked, "PRIVATE_REVIEW_NOT_QUALIFIED"):
            self.review(captures={**self.captures, "after": capture})

    def test_original_private_frame_modified_on_disk_fails(self):
        path = self.captures["after"].retained.relative_path
        (self.evidence / path).write_bytes(PNG + b"tampered")
        with self.assertRaisesRegex(PrivateReviewBlocked, "PRIVATE_REVIEW_NOT_QUALIFIED"):
            self.review()

    def test_source_file_modified_on_disk_fails(self):
        name = next(iter(REQUIRED_SOURCES))
        (self.sources / name).write_bytes(b"modified")
        with self.assertRaisesRegex(PrivateReviewBlocked, "PRIVATE_REVIEW_NOT_QUALIFIED"):
            self.review()

    def test_stale_handoff_fails_without_reusing_old_manifest(self):
        with self.assertRaisesRegex(PrivateReviewBlocked, "PRIVATE_REVIEW_NOT_QUALIFIED"):
            self.review(now=NOW + timedelta(minutes=20))

    def test_unsafe_binding_path_fails_closed(self):
        altered = {**self.binding_files, "profile": "../escape.json"}
        with self.assertRaisesRegex(PrivateReviewBlocked, "PRIVATE_REVIEW_NOT_QUALIFIED"):
            self.review(binding_files=altered)

    def test_wrong_packet_type_fails_before_any_review(self):
        with self.assertRaisesRegex(PrivateReviewBlocked, "HANDOFF_INVALID"):
            self.review(packet=None)


if __name__ == "__main__":
    unittest.main()
