"""Local byte-integrity tests only; no real game, OCR or execution."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import os
import tempfile
import unittest

from src.automation.farming_capture_verify import verify_local_capture_claim
from src.automation.farming_live_handoff import build_observation_handoff
from src.overworld.qualification import REQUIRED_SOURCES


NOW = datetime(2026, 11, 13, 3, 0, tzinfo=timezone.utc)


class TestFarmingCaptureVerify(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.sources = root / "repo"
        self.evidence = root / "capture"
        self.sources.mkdir()
        self.evidence.mkdir()

        self.source_hashes = {}
        for source in REQUIRED_SOURCES:
            self.source_hashes[source] = self.write(
                self.sources, source, ("source:" + source).encode("utf-8")
            )
        self.bindings = {
            "profile": "private/profile.json",
            "reference": "private/reference.png",
            "database": "private/database.json",
        }
        self.binding_hashes = {
            name: self.write(self.evidence, path, ("binding:" + name).encode())
            for name, path in self.bindings.items()
        }
        self.frames = {"frame-one": "private/frame-one.png"}
        self.frame_hashes = {
            name: self.write(self.evidence, path, b"synthetic-frame-pixels")
            for name, path in self.frames.items()
        }
        self.payload = {
            "schema_version": 1,
            "purpose": "ROUTE_SURVEY",
            "target_kind": "mob",
            "target_id": "geospider-s4",
            "game_mob_id": "000123",
            "game_version": "synthetic-1",
            "ok_script_version": "synthetic-2",
            "session_id": "local-test",
            "observed_at": (NOW - timedelta(seconds=30)).isoformat(),
            "stage": "WALK",
            "route_id": "route-test",
            "state_id": "map-test",
            "floor_id": "0",
            "frame_ids": list(self.frames),
            "frame_sha256": self.frame_hashes,
            "bindings_sha256": self.binding_hashes,
            "source_sha256": self.source_hashes,
            "inventory_before": None,
            "inventory_after": None,
        }

    @staticmethod
    def write(root, path, data):
        destination = root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return sha256(data).hexdigest()

    def audit(self, **replacements):
        packet = build_observation_handoff(self.payload, now=NOW)
        return verify_local_capture_claim(
            packet,
            source_root=replacements.get("source_root", self.sources),
            evidence_root=replacements.get("evidence_root", self.evidence),
            frame_files=replacements.get("frame_files", self.frames),
            binding_files=replacements.get("binding_files", self.bindings),
            now=replacements.get("now", NOW),
        )

    def test_matching_local_bytes_are_never_authorization(self):
        result = self.audit()
        self.assertEqual("LOCAL_HASH_MATCH_ONLY", result.status)
        self.assertEqual(
            len(REQUIRED_SOURCES) + len(self.bindings) + len(self.frames),
            result.checked_artifact_count,
        )
        public = result.public_summary()
        self.assertFalse(public["can_start"])
        self.assertFalse(public["evidence_authenticated"])
        self.assertFalse(public["route_qualified"])
        self.assertFalse(public["independent_review_complete"])
        self.assertEqual(64, len(public["packet_sha256"]))
        self.assertNotIn(str(self.evidence), repr(public))
        self.assertNotIn("private/profile.json", repr(public))

    def test_altered_source_file_is_rejected(self):
        self.write(self.sources, next(iter(REQUIRED_SOURCES)), b"changed code")
        self.assertEqual("LOCAL_HASH_MISMATCH", self.audit().reason_code)

    def test_altered_original_frame_is_rejected(self):
        self.write(self.evidence, self.frames["frame-one"], b"changed frame")
        self.assertEqual("LOCAL_HASH_MISMATCH", self.audit().reason_code)

    def test_altered_profile_binding_is_rejected(self):
        self.write(self.evidence, self.bindings["profile"], b"changed profile")
        self.assertEqual("LOCAL_HASH_MISMATCH", self.audit().reason_code)

    def test_missing_artifact_is_rejected(self):
        (self.evidence / self.frames["frame-one"]).unlink()
        result = self.audit()
        self.assertEqual("REJECTED", result.status)
        self.assertEqual("LOCAL_ARTIFACT_MISSING", result.reason_code)
        self.assertEqual(0, result.checked_artifact_count)

    def test_path_escape_absolute_and_windows_paths_are_rejected(self):
        for unsafe in ("../escape.png", "/abs/capture.png", "C:\\temp\\frame.png",
                       "private/../../escape", "private//frame.png"):
            with self.subTest(path=unsafe):
                paths = {"frame-one": unsafe}
                self.assertEqual("UNSAFE_LOCAL_PATH",
                                 self.audit(frame_files=paths).reason_code)

    def test_missing_and_ambiguous_map_labels_are_rejected(self):
        self.assertEqual(
            "ARTIFACT_MAP_INVALID", self.audit(frame_files={}).reason_code
        )
        self.assertEqual(
            "ARTIFACT_MAP_INVALID",
            self.audit(binding_files={"profile": "private/profile.json"}).reason_code,
        )
        duplicate = dict(self.bindings)
        duplicate["reference"] = duplicate["profile"]
        self.assertEqual(
            "ARTIFACT_MAP_AMBIGUOUS",
            self.audit(binding_files=duplicate).reason_code,
        )

    def test_symlink_inside_trusted_root_is_rejected(self):
        original = self.evidence / self.frames["frame-one"]
        link = self.evidence / "private" / "linked-frame.png"
        try:
            os.symlink(original, link)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable to current test process")
        self.assertEqual(
            "UNSAFE_LOCAL_PATH",
            self.audit(frame_files={"frame-one": "private/linked-frame.png"}).reason_code,
        )

    def test_relative_roots_are_rejected_before_original_file_access(self):
        for values in (
            {"source_root": "relative/checkout"},
            {"evidence_root": "relative/evidence"},
        ):
            with self.subTest(values=values):
                result = self.audit(**values)
                self.assertEqual("REJECTED", result.status)
                self.assertEqual("LOCAL_ROOT_INVALID", result.reason_code)
                self.assertFalse(result.public_summary()["can_start"])

    def test_symlinked_ancestor_of_source_root_is_rejected(self):
        link = self.sources.parent / "parent-alias"
        try:
            os.symlink(self.sources.parent, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable to current test process")
        result = self.audit(source_root=link / "repo")
        self.assertEqual("LOCAL_ROOT_INVALID", result.reason_code)
        self.assertEqual(0, result.checked_artifact_count)

    def test_symlinked_ancestor_of_evidence_root_is_rejected(self):
        link = self.evidence.parent / "evidence-alias"
        try:
            os.symlink(self.evidence.parent, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable to current test process")
        result = self.audit(evidence_root=link / "capture")
        self.assertEqual("LOCAL_ROOT_INVALID", result.reason_code)
        self.assertFalse(result.public_summary()["can_start"])

    def test_stale_capture_is_rejected_even_when_original_digest_matches(self):
        self.assertEqual(
            "CAPTURE_CLAIM_STALE",
            self.audit(now=NOW + timedelta(minutes=17)).reason_code,
        )

    def test_bad_clock_rejected_without_claiming_review(self):
        with self.assertRaises(ValueError):
            self.audit(now=NOW.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
