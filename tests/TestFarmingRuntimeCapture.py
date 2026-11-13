"""Synthetic read-only frame/foreground contracts; NO game or OK Script runtime."""

from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import patch
import unittest

import numpy as np

from src.automation.farming_runtime_capture import CaptureBlocked, capture_readonly_frame


class FakeTask:
    def __init__(self):
        self.executor = SimpleNamespace(device_manager=SimpleNamespace(
            hwnd_window=SimpleNamespace(hwnd=1357)))
        self.frame = np.full((72, 128, 3), 49, dtype=np.uint8)
        self.reads = 0
        self.is_cancelled = False
        self.input_calls = 0

    def next_frame(self):
        self.reads += 1

    def cancelled(self):
        return self.is_cancelled

    def send_key(self, *args, **kwargs):
        self.input_calls += 1
        raise AssertionError("Capture must never send game input")

    click = send_key
    mouse_down = send_key
    run_task_by_class = send_key


class TestFarmingRuntimeCapture(unittest.TestCase):
    def setUp(self):
        self.task = FakeTask()
        self.version_patcher = patch(
            "src.automation.farming_runtime_capture.version", return_value="3.0.4")
        self.version_patcher.start()
        self.addCleanup(self.version_patcher.stop)
        self.focus_patcher = patch(
            "src.automation.farming_runtime_capture._system_foreground_hwnd",
            return_value=1357)
        self.focus_patcher.start()
        self.addCleanup(self.focus_patcher.stop)

    def capture(self, **kwargs):
        return capture_readonly_frame(self.task, opted_in=True, **kwargs)

    def test_reads_actual_frame_without_input_or_execution(self):
        snap = self.capture()
        self.assertEqual((snap.width, snap.height), (128, 72))
        self.assertEqual(snap.frame_sha256, sha256(snap.frame_png).hexdigest())
        self.assertTrue(snap.frame_png.startswith(b"\x89PNG"))
        self.assertEqual(self.task.reads, 1)
        self.assertEqual(self.task.input_calls, 0)
        self.assertFalse(snap.public_summary()["can_start"])
        self.assertFalse(snap.public_summary()["frame_freshness_verified"])
        self.assertFalse(snap.public_summary()["game_version_observed"])
        self.assertNotIn("frame_png", snap.public_summary())
        self.assertNotIn("hwnd", repr(snap))

    def test_absent_explicit_opt_in_rejects_before_acquisition(self):
        for value in (False, 1, "yes", None):
            with self.subTest(value=value), self.assertRaises(CaptureBlocked):
                capture_readonly_frame(self.task, opted_in=value)
        self.assertEqual(self.task.reads, 0)

    def test_foreground_mismatch_blocks_before_read(self):
        with patch("src.automation.farming_runtime_capture._system_foreground_hwnd", return_value=9999):
            with self.assertRaisesRegex(CaptureBlocked, "GAME_NOT_FOREGROUND"):
                self.capture()
        self.assertEqual(self.task.reads, 0)

    def test_foreground_change_after_frame_rejects(self):
        with patch("src.automation.farming_runtime_capture._system_foreground_hwnd",
                   side_effect=[1357, 9999]):
            with self.assertRaisesRegex(CaptureBlocked, "GAME_NOT_FOREGROUND"):
                self.capture()
        self.assertEqual(self.task.reads, 1)

    def test_foreground_change_during_encoding_rejects(self):
        with patch("src.automation.farming_runtime_capture._system_foreground_hwnd",
                   side_effect=[1357, 1357, 9999]):
            with self.assertRaisesRegex(CaptureBlocked, "GAME_NOT_FOREGROUND"):
                self.capture()

    def test_cancellation_before_and_during_read_rejects(self):
        self.task.is_cancelled = True
        with self.assertRaisesRegex(CaptureBlocked, "CAPTURE_CANCELLED"):
            self.capture()
        self.assertEqual(self.task.reads, 0)
        self.task.is_cancelled = False
        def cancel_on_read():
            self.task.reads += 1
            self.task.is_cancelled = True
        self.task.next_frame = cancel_on_read
        with self.assertRaisesRegex(CaptureBlocked, "CAPTURE_CANCELLED"):
            self.capture()

    def test_invalid_frame_buffer_fails_closed(self):
        for frame in (None, np.zeros((64, 64), np.uint8),
                      np.zeros((64, 64, 3), np.float32),
                      np.zeros((64, 64, 2), np.uint8),
                      np.zeros((64, 4097, 3), np.uint8)):
            with self.subTest(shape=getattr(frame, "shape", None)):
                self.task.frame = frame
                with self.assertRaisesRegex(CaptureBlocked, "INVALID_FRAME_BUFFER"):
                    self.capture()

    def test_missing_or_invalid_runtime_version_rejects(self):
        with patch("src.automation.farming_runtime_capture.version", return_value="unknown version"):
            with self.assertRaisesRegex(CaptureBlocked, "RUNTIME_VERSION_UNAVAILABLE"):
                self.capture()
        with patch("src.automation.farming_runtime_capture.version", side_effect=LookupError):
            with self.assertRaisesRegex(CaptureBlocked, "RUNTIME_VERSION_UNAVAILABLE"):
                self.capture()

    def test_missing_window_or_missing_cancel_hook_rejects(self):
        self.task.executor.device_manager.hwnd_window.hwnd = 0
        with self.assertRaisesRegex(CaptureBlocked, "OK_SCRIPT_RUNTIME_UNAVAILABLE"):
            self.capture()
        self.assertEqual(self.task.reads, 0)

    def test_foreground_checker_error_fails_closed(self):
        def fail():
            raise OSError("window API unavailable")
        with patch("src.automation.farming_runtime_capture._system_foreground_hwnd", side_effect=fail):
            with self.assertRaisesRegex(CaptureBlocked, "FOREGROUND_CHECK_UNAVAILABLE"):
                self.capture()
        self.assertEqual(self.task.reads, 0)


if __name__ == "__main__":
    unittest.main()
