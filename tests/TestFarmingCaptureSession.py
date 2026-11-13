"""Synthetic read-only capture-to-handoff continuity tests; never controls game."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from src.automation.farming_capture_session import (
    CaptureSessionBlocked, inspect_readonly_capture_session,
)
from src.automation.farming_capture_retention import RetainedReadOnlySnapshot
from src.automation.farming_runtime_capture import ReadOnlyFrameSnapshot
from src.automation.farming_live_handoff import build_observation_handoff
from src.overworld.qualification import REQUIRED_SOURCES

NOW = datetime(2026, 11, 13, 6, 0, tzinfo=timezone.utc)
PNG = b"\x89PNG\r\n\x1a\n"


class TestFarmingCaptureSession(unittest.TestCase):
    def setUp(self):
        self.snapshots = {}
        self.retained = {}
        for index, frame_id in enumerate(("before", "after")):
            when = (NOW - timedelta(seconds=30 - 20 * index)).isoformat()
            data = PNG + ("synthetic-" + frame_id).encode("ascii")
            digest = sha256(data).hexdigest()
            self.snapshots[frame_id] = ReadOnlyFrameSnapshot(
                when, "3.0.4", 1280, 720, digest, data,
            )
            self.retained[frame_id] = RetainedReadOnlySnapshot(
                f"farm-frame-{frame_id}.png", when, digest, len(data),
            )
        hashes = {name: "a" * 64 for name in REQUIRED_SOURCES}
        self.packet = build_observation_handoff({
            "schema_version": 1, "purpose": "SOURCE_DROP",
            "target_kind": "material", "target_id": "ff-mech-core",
            "game_mob_id": "000123", "game_version": "synthetic-1",
            "ok_script_version": "3.0.4", "session_id": "synthetic-session",
            "observed_at": (NOW - timedelta(seconds=5)).isoformat(),
            "stage": "SINGLE_CAMP", "route_id": "", "state_id": "map-a",
            "floor_id": "0", "frame_ids": list(self.snapshots),
            "frame_sha256": {key: value.frame_sha256 for key, value in self.snapshots.items()},
            "bindings_sha256": {key: "b" * 64 for key in ("profile", "reference", "database")},
            "source_sha256": hashes,
            "inventory_before": 4, "inventory_after": 5,
        }, now=NOW)

    def inspect(self, snapshots=None, retained=None, now=NOW):
        return inspect_readonly_capture_session(
            self.packet, self.snapshots if snapshots is None else snapshots,
            self.retained if retained is None else retained, now=now,
        )

    def test_exact_local_continuity_never_authorizes_execution(self):
        result = self.inspect()
        summary = result.public_summary()
        self.assertEqual("LOCAL_SESSION_COHERENT_ONLY", summary["status"])
        self.assertEqual(2, summary["frame_count"])
        for key in ("can_start", "actual_frame_freshness_verified",
                    "game_origin_authenticated", "game_version_authenticated",
                    "original_files_verified", "inventory_receipt_verified",
                    "independent_review_complete", "route_qualified"):
            self.assertIs(summary[key], False)
        self.assertNotIn("farm-frame", repr(summary))
        self.assertNotIn("synthetic-session", repr(summary))

    def test_runtime_version_mismatch_rejected(self):
        changed = dict(self.snapshots)
        changed["after"] = replace(changed["after"], runtime_version="3.0.5")
        with self.assertRaisesRegex(CaptureSessionBlocked, "RUNTIME_VERSION_MISMATCH"):
            self.inspect(snapshots=changed)

    def test_tampered_memory_bytes_rejected(self):
        changed = dict(self.snapshots)
        changed["after"] = replace(changed["after"], frame_png=PNG + b"tampered")
        with self.assertRaisesRegex(CaptureSessionBlocked, "SNAPSHOT_DIGEST_MISMATCH"):
            self.inspect(snapshots=changed)

    def test_fake_digest_and_size_rejected(self):
        changed = dict(self.snapshots)
        changed["after"] = replace(changed["after"], frame_sha256="f" * 64)
        with self.assertRaisesRegex(CaptureSessionBlocked, "SNAPSHOT_DIGEST_MISMATCH"):
            self.inspect(snapshots=changed)
        records = dict(self.retained)
        records["after"] = replace(records["after"], size_bytes=records["after"].size_bytes + 1)
        with self.assertRaisesRegex(CaptureSessionBlocked, "SNAPSHOT_DIGEST_MISMATCH"):
            self.inspect(retained=records)

    def test_capture_timestamp_disagreement_rejected(self):
        changed = dict(self.snapshots)
        changed["after"] = replace(changed["after"], captured_at_utc=NOW.isoformat())
        with self.assertRaisesRegex(CaptureSessionBlocked, "CAPTURE_TIMESTAMP_MISMATCH"):
            self.inspect(snapshots=changed)

    def test_resolution_change_or_invalid_dimensions_rejected(self):
        changed = dict(self.snapshots)
        changed["after"] = replace(changed["after"], width=1920)
        with self.assertRaisesRegex(CaptureSessionBlocked, "RESOLUTION_CHANGED"):
            self.inspect(snapshots=changed)
        changed["after"] = replace(changed["after"], width=True)
        with self.assertRaisesRegex(CaptureSessionBlocked, "SNAPSHOT_DIMENSIONS_INVALID"):
            self.inspect(snapshots=changed)

    def test_invalid_png_and_frame_type_rejected(self):
        changed = dict(self.snapshots)
        changed["after"] = replace(changed["after"], frame_png=b"not-a-png")
        with self.assertRaisesRegex(CaptureSessionBlocked, "SNAPSHOT_BYTES_INVALID"):
            self.inspect(snapshots=changed)
        changed["after"] = None
        with self.assertRaisesRegex(CaptureSessionBlocked, "SNAPSHOT_INVALID"):
            self.inspect(snapshots=changed)

    def test_missing_or_extra_snapshot_rejected(self):
        for frames in ({}, {"before": self.snapshots["before"]},
                       {**self.snapshots, "extra": self.snapshots["after"]}):
            with self.subTest(frames=frames), self.assertRaisesRegex(
                CaptureSessionBlocked, "SNAPSHOT_IDS_MISMATCH"
            ):
                self.inspect(snapshots=frames)

    def test_reversed_retention_or_path_injection_rejected(self):
        for record in (
            replace(self.retained["after"], captured_at_utc=self.retained["before"].captured_at_utc),
            replace(self.retained["after"], relative_path="../private.png"),
        ):
            records = {**self.retained, "after": record}
            with self.subTest(record=record), self.assertRaisesRegex(
                CaptureSessionBlocked, "RETAINED_BINDING_INVALID"
            ):
                self.inspect(retained=records)

    def test_expired_session_and_naive_clock_rejected(self):
        with self.assertRaisesRegex(CaptureSessionBlocked, "RETAINED_BINDING_INVALID"):
            self.inspect(now=NOW + timedelta(minutes=20))
        with self.assertRaisesRegex(CaptureSessionBlocked, "RETAINED_BINDING_INVALID"):
            self.inspect(now=NOW.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
