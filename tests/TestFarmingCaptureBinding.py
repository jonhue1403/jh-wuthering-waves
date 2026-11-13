"""Synthetic, read-only frame binding contracts. No game or OK Script startup."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.automation.farming_capture_binding import (
    FrameBindingBlocked, bind_retained_frame_files, verify_retained_capture_claim,
)
from src.automation.farming_capture_retention import RetainedReadOnlySnapshot
from src.automation.farming_live_handoff import build_observation_handoff
from src.overworld.qualification import REQUIRED_SOURCES

NOW = datetime(2026, 11, 13, 5, 0, tzinfo=timezone.utc)


class TestFarmingCaptureBinding(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.sources = root / "source"
        self.evidence = root / "private"
        self.sources.mkdir()
        self.evidence.mkdir()
        self.files = {
            "frame-before": "farm-frame-session_before.png",
            "frame-after": "farm-frame-session_after.png",
        }
        self.digests = {
            frame: self.write(self.evidence, relative, ("png:" + frame).encode())
            for frame, relative in self.files.items()
        }
        self.binding_files = {
            "profile": "profile.json", "reference": "reference.png",
            "database": "database.json",
        }
        self.binding_hashes = {
            name: self.write(self.evidence, relative, name.encode())
            for name, relative in self.binding_files.items()
        }
        self.source_hashes = {
            name: self.write(self.sources, name, name.encode())
            for name in REQUIRED_SOURCES
        }
        self.packet = build_observation_handoff({
            "schema_version": 1, "purpose": "SOURCE_DROP",
            "target_kind": "material", "target_id": "ff-mech-core",
            "game_mob_id": "000123", "game_version": "synthetic-1",
            "ok_script_version": "synthetic-2", "session_id": "private-session",
            "observed_at": (NOW - timedelta(seconds=5)).isoformat(),
            "stage": "SINGLE_CAMP", "route_id": "", "state_id": "test-map",
            "floor_id": "0", "frame_ids": list(self.files),
            "frame_sha256": self.digests,
            "bindings_sha256": self.binding_hashes,
            "source_sha256": self.source_hashes,
            "inventory_before": 2, "inventory_after": 4,
        }, now=NOW)
        self.retained = {
            frame: RetainedReadOnlySnapshot(
                self.files[frame],
                (NOW - timedelta(seconds=20 - index * 10)).isoformat(),
                self.digests[frame],
                len(("png:" + frame).encode()),
            )
            for index, frame in enumerate(self.files)
        }

    @staticmethod
    def write(root, relative, data):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return sha256(data).hexdigest()

    def bind(self, retained=None, **kwargs):
        return bind_retained_frame_files(
            self.packet, self.retained if retained is None else retained,
            now=kwargs.get("now", NOW),
        )

    def test_matching_retained_frame_claim_is_private_and_cannot_start(self):
        result = self.bind()
        self.assertEqual(self.packet.record_sha256, result.packet_sha256)
        self.assertEqual(self.files, result.internal_frame_files())
        summary = result.public_summary()
        self.assertFalse(summary["can_start"])
        self.assertFalse(summary["frame_bytes_verified"])
        self.assertFalse(summary["inventory_receipt_verified"])
        self.assertNotIn("private_frame_files", summary)
        for path in self.files.values():
            self.assertNotIn(path, repr(summary))

    def test_integrated_real_byte_hash_audit_is_still_not_authorization(self):
        result = verify_retained_capture_claim(
            self.packet, self.retained, source_root=self.sources,
            evidence_root=self.evidence, binding_files=self.binding_files, now=NOW,
        )
        self.assertEqual("LOCAL_HASH_MATCH_ONLY", result.status)
        self.assertFalse(result.public_summary()["can_start"])
        self.assertFalse(result.public_summary()["independent_review_complete"])

    def test_tampered_original_frame_rejected_by_integrated_byte_audit(self):
        (self.evidence / self.files["frame-after"]).write_bytes(b"tampered")
        result = verify_retained_capture_claim(
            self.packet, self.retained, source_root=self.sources,
            evidence_root=self.evidence, binding_files=self.binding_files, now=NOW,
        )
        self.assertEqual("LOCAL_HASH_MISMATCH", result.reason_code)
        self.assertFalse(result.public_summary()["can_start"])

    def test_missing_and_extra_frames_fail_closed(self):
        for frames in ({}, {"frame-before": self.retained["frame-before"]},
                       {**self.retained, "third": self.retained["frame-after"]}):
            with self.subTest(frames=frames), self.assertRaisesRegex(
                FrameBindingBlocked, "FRAME_IDS_MISMATCH"
            ):
                self.bind(frames)

    def test_rejects_digest_and_type_mismatch(self):
        for record in (
            replace(self.retained["frame-after"], frame_sha256="0" * 64),
            replace(self.retained["frame-after"], size_bytes=True),
            replace(self.retained["frame-after"], size_bytes=0),
            None,
        ):
            with self.subTest(record=record), self.assertRaises(FrameBindingBlocked):
                self.bind({**self.retained, "frame-after": record})

    def test_rejects_path_traversal_even_with_matching_hash(self):
        for path in ("../x.png", "folder/farm-frame-a.png", "C:\\x.png",
                     "farm-frame-a.png/other", "farm-frame-xx.txt", "farm-frame-..png"):
            with self.subTest(path=path), self.assertRaisesRegex(
                FrameBindingBlocked, "RETAINED_FRAME_MISMATCH"
            ):
                self.bind({**self.retained, "frame-after": replace(
                    self.retained["frame-after"], relative_path=path,
                )})

    def test_rejects_two_frame_ids_sharing_one_private_file(self):
        duplicated = replace(
            self.retained["frame-after"],
            relative_path=self.retained["frame-before"].relative_path,
        )
        with self.assertRaisesRegex(FrameBindingBlocked, "AMBIGUOUS_PRIVATE_FRAMES"):
            self.bind({**self.retained, "frame-after": duplicated})

    def test_rejects_swapped_or_identical_chronology(self):
        before = self.retained["frame-before"]
        after = self.retained["frame-after"]
        for timestamp in (before.captured_at_utc,
                          (NOW - timedelta(seconds=25)).isoformat()):
            with self.subTest(timestamp=timestamp), self.assertRaisesRegex(
                FrameBindingBlocked, "CAPTURE_ORDER_INVALID"
            ):
                self.bind({**self.retained, "frame-after": replace(
                    after, captured_at_utc=timestamp,
                )})

    def test_rejects_stale_future_naive_or_delayed_claims(self):
        after = self.retained["frame-after"]
        for timestamp in (
            (NOW - timedelta(minutes=16)).isoformat(),
            (NOW + timedelta(minutes=3)).isoformat(),
            NOW.replace(tzinfo=None).isoformat(),
            (NOW - timedelta(minutes=7)).isoformat(),
        ):
            with self.subTest(timestamp=timestamp), self.assertRaises(FrameBindingBlocked):
                self.bind({**self.retained, "frame-after": replace(
                    after, captured_at_utc=timestamp,
                )})
        with self.assertRaisesRegex(FrameBindingBlocked, "CLOCK_INVALID"):
            self.bind(now=NOW.replace(tzinfo=None))

    def test_expired_packet_rejected_even_when_retention_digests_match(self):
        with self.assertRaisesRegex(FrameBindingBlocked, "OBSERVATION_STALE"):
            self.bind(now=NOW + timedelta(minutes=17))


if __name__ == "__main__":
    unittest.main()
