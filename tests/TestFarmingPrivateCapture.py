"""Synthetic read-only capture/retention integration. No game control."""

from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.automation.farming_runtime_capture import CaptureBlocked, ReadOnlyFrameSnapshot
from src.automation.farming_capture_retention import RetainedReadOnlySnapshot
from src.automation.farming_private_capture import (
    PrivateCaptureBlocked, capture_private_readonly_evidence,
)


PNG = b"\x89PNG\r\n\x1a\n" + b"synthetic-non-game-content"
NOW = datetime(2026, 11, 13, 11, 0, tzinfo=timezone.utc)


class TestFarmingPrivateCapture(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.private_root = Path(temp.name)
        self.snapshot = ReadOnlyFrameSnapshot(
            NOW.isoformat(), "3.0.4", 1280, 720, sha256(PNG).hexdigest(), PNG,
        )
        self.task = object()  # A real game/runtime must never be invoked.

    def call(self, **overrides):
        return capture_private_readonly_evidence(
            self.task,
            private_root=overrides.get("private_root", self.private_root),
            opted_in=overrides.get("opted_in", True),
            now=overrides.get("now", NOW),
        )

    def test_explicit_opt_in_before_any_capture(self):
        with patch("src.automation.farming_private_capture.capture_readonly_frame") as cap:
            with self.assertRaisesRegex(PrivateCaptureBlocked, "OPT_IN"):
                self.call(opted_in=False)
            cap.assert_not_called()
        self.assertEqual([], list(self.private_root.iterdir()))

    def test_real_private_retention_with_synthetic_frame(self):
        with patch("src.automation.farming_private_capture.capture_readonly_frame", return_value=self.snapshot) as cap:
            result = self.call()
        cap.assert_called_once_with(self.task, opted_in=True)
        self.assertEqual(PNG, (self.private_root / result.retained.relative_path).read_bytes())
        self.assertEqual(self.snapshot.frame_sha256, result.retained.frame_sha256)
        summary = result.public_summary()
        self.assertFalse(summary["can_start"])
        self.assertFalse(summary["inventory_receipt_verified"])
        self.assertFalse(summary["frame_freshness_verified"])
        for secret in (str(self.private_root), result.retained.relative_path, "synthetic-non-game-content"):
            self.assertNotIn(secret, repr(summary))
            self.assertNotIn(secret, repr(result))

    def test_repeated_internal_calls_never_overwrite(self):
        with patch("src.automation.farming_private_capture.capture_readonly_frame", return_value=self.snapshot):
            a, b = self.call(), self.call()
        self.assertNotEqual(a.retained.relative_path, b.retained.relative_path)
        self.assertEqual(2, len(list(self.private_root.iterdir())))

    def test_missing_private_directory_fails_closed(self):
        with patch("src.automation.farming_private_capture.capture_readonly_frame", return_value=self.snapshot):
            with self.assertRaisesRegex(PrivateCaptureBlocked, "PRIVATE_RETENTION_FAILED"):
                self.call(private_root=self.private_root / "not-created")
        self.assertEqual([], list(self.private_root.iterdir()))

    def test_capture_failure_does_not_attempt_disk_write(self):
        with patch("src.automation.farming_private_capture.capture_readonly_frame", side_effect=CaptureBlocked("GAME_NOT_FOREGROUND")):
            with patch("src.automation.farming_private_capture.retain_readonly_snapshot") as retained:
                with self.assertRaisesRegex(PrivateCaptureBlocked, "FOREGROUND_CAPTURE_FAILED"):
                    self.call()
                retained.assert_not_called()

    def test_invalid_capture_contract_does_not_store(self):
        with patch("src.automation.farming_private_capture.capture_readonly_frame", return_value=object()):
            with self.assertRaisesRegex(PrivateCaptureBlocked, "CAPTURE_CONTRACT_INVALID"):
                self.call()
        self.assertEqual([], list(self.private_root.iterdir()))

    def test_tampered_frame_cannot_be_retained(self):
        altered = replace(self.snapshot, frame_png=PNG + b"corrupt")
        with patch("src.automation.farming_private_capture.capture_readonly_frame", return_value=altered):
            with self.assertRaisesRegex(PrivateCaptureBlocked, "PRIVATE_RETENTION_FAILED"):
                self.call()
        self.assertEqual([], list(self.private_root.iterdir()))

    def test_broken_returned_receipt_never_promotes(self):
        wrong = RetainedReadOnlySnapshot("farm-frame-fake.png", NOW.isoformat(), "0" * 64, len(PNG))
        with patch("src.automation.farming_private_capture.capture_readonly_frame", return_value=self.snapshot):
            with patch("src.automation.farming_private_capture.retain_readonly_snapshot", return_value=wrong):
                with self.assertRaisesRegex(PrivateCaptureBlocked, "CONTRACT_MISMATCH"):
                    self.call()

    def test_naive_clock_rejected_without_capture(self):
        with patch("src.automation.farming_private_capture.capture_readonly_frame") as cap:
            with self.assertRaisesRegex(PrivateCaptureBlocked, "CLOCK_INVALID"):
                self.call(now=NOW.replace(tzinfo=None))
            cap.assert_not_called()

    def test_missing_opt_in_and_bad_type_rejected(self):
        with patch("src.automation.farming_private_capture.capture_readonly_frame") as cap:
            for value in (0, 1, "true", None):
                with self.assertRaisesRegex(PrivateCaptureBlocked, "OPT_IN"):
                    self.call(opted_in=value)
            cap.assert_not_called()


if __name__ == "__main__":
    unittest.main()
