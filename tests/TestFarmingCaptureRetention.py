"""Synthetic private retention contracts: no real OK Script or game access."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess
import unittest

from src.automation.farming_runtime_capture import ReadOnlyFrameSnapshot
from src.automation.farming_capture_retention import (
    SnapshotRetentionBlocked, retain_readonly_snapshot,
)


def _create_directory_redirect(link, target):
    try:
        os.symlink(target, link, target_is_directory=True)
        return "symlink"
    except (OSError, NotImplementedError):
        if os.name != "nt":
            raise
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise OSError(result.stderr or result.stdout or "junction creation failed")
    return "junction"


class TestFarmingCaptureRetention(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = datetime.now(timezone.utc)
        self.png = b"\x89PNG\r\n\x1a\n" + b"synthetic-only-not-a-game-frame"

    def snapshot(self, *, captured=None, png=None, digest=None):
        data = self.png if png is None else png
        return ReadOnlyFrameSnapshot(
            (captured or self.now).isoformat(), "3.0.4", 128, 72,
            digest or sha256(data).hexdigest(), data,
        )

    def save(self, snap=None, **kw):
        return retain_readonly_snapshot(
            snap or self.snapshot(), private_root=self.root,
            capture_token="session_001", opted_in=True, **({"now": self.now} | kw),
        )

    def test_private_roundtrip_and_public_summary(self):
        record = self.save()
        self.assertEqual((self.root / record.relative_path).read_bytes(), self.png)
        self.assertEqual(record.frame_sha256, sha256(self.png).hexdigest())
        self.assertFalse(record.public_summary()["can_start"])
        self.assertNotIn("relative_path", record.public_summary())
        self.assertNotIn(str(self.root), repr(record))

    def test_opt_in_required_and_does_not_write(self):
        with self.assertRaisesRegex(SnapshotRetentionBlocked, "EXPLICIT_OPT_IN"):
            retain_readonly_snapshot(self.snapshot(), private_root=self.root,
                                     capture_token="x")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_rejects_duplicate_without_overwrite(self):
        record = self.save()
        with self.assertRaisesRegex(SnapshotRetentionBlocked, "ALREADY_EXISTS"):
            self.save()
        self.assertEqual((self.root / record.relative_path).read_bytes(), self.png)

    def test_rejects_traversal_or_ambiguous_token(self):
        for token in ("../file", "foo/bar", "", ".", "x.png", "é", "x" * 49):
            with self.subTest(token=token), self.assertRaisesRegex(
                SnapshotRetentionBlocked, "CAPTURE_TOKEN_INVALID"
            ):
                retain_readonly_snapshot(self.snapshot(), private_root=self.root,
                                         capture_token=token, opted_in=True, now=self.now)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_stale_and_future_snapshots_blocked(self):
        for when in (self.now - timedelta(minutes=16), self.now + timedelta(minutes=3)):
            with self.assertRaisesRegex(SnapshotRetentionBlocked, "SNAPSHOT_STALE"):
                self.save(self.snapshot(captured=when))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_bad_digest_and_invalid_png_blocked(self):
        with self.assertRaisesRegex(SnapshotRetentionBlocked, "SNAPSHOT_BYTES_INVALID"):
            self.save(self.snapshot(digest="0" * 64))
        with self.assertRaisesRegex(SnapshotRetentionBlocked, "SNAPSHOT_BYTES_INVALID"):
            self.save(self.snapshot(png=b"fake png"))

    def test_root_must_exist_and_be_absolute(self):
        for root in ("relative/private", self.root / "missing"):
            with self.assertRaisesRegex(SnapshotRetentionBlocked, "PRIVATE_ROOT_INVALID"):
                retain_readonly_snapshot(self.snapshot(), private_root=root,
                                         capture_token="x", opted_in=True, now=self.now)

    def test_redirected_root_rejected(self):
        link = self.root / "link"
        try:
            _create_directory_redirect(link, self.root)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink/junction creation unavailable")
        with self.assertRaisesRegex(SnapshotRetentionBlocked, "PRIVATE_ROOT_UNSAFE"):
            retain_readonly_snapshot(self.snapshot(), private_root=link,
                                     capture_token="x", opted_in=True, now=self.now)

    def test_utc_clock_required(self):
        with self.assertRaisesRegex(SnapshotRetentionBlocked, "CLOCK_INVALID"):
            self.save(now=datetime.now())


if __name__ == "__main__":
    unittest.main()
