import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np
from ok import BaseTask, DoNothingInteraction

from src.overworld.calibration_capture import (
    CalibrationCaptureTask, CaptureOnlyInteraction, capture_config, capture_stationary, main,
)


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.waits = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += seconds


class TestCalibrationCapture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "capture"
        self.clock = FakeClock()
        self.frame = np.arange(113 * 207 * 3, dtype=np.uint8).reshape(113, 207, 3)

    def capture(self, supplier=None):
        return capture_stationary(self.output, "surface-test", supplier or (lambda: self.frame),
                                  self.clock.sleep, lambda: "test.WGC", clock=self.clock)

    def metadata(self):
        return json.loads((self.output / "metadata.json").read_text(encoding="utf-8"))

    def test_ten_sequential_lossless_full_frames_and_metadata(self):
        frames = [np.roll(self.frame, index, axis=0) for index in range(10)]
        supplier = Mock(side_effect=frames)
        report = self.capture(supplier)
        self.assertEqual(10, supplier.call_count)
        self.assertTrue(report["complete"])
        self.assertEqual(10, report["frame_count"])
        self.assertEqual(10, report["frames_requested"])
        self.assertEqual(500, report["interval_requested_ms"])
        self.assertEqual({"width": 207, "height": 113}, report["frame_dimensions"])
        self.assertEqual("surface-test", report["calibration_profile"])
        self.assertEqual("test.WGC", report["capture_backend"])
        self.assertEqual([0.5] * 9, self.clock.waits)
        self.assertEqual(report, self.metadata())
        for index, (entry, original) in enumerate(zip(report["frames"], frames), 1):
            self.assertEqual(f"stationary_{index:03d}.png", entry["filename"])
            self.assertTrue(entry["capture_timestamp"].endswith("+00:00"))
            self.assertEqual((index - 1) * 0.5, entry["elapsed_seconds"])
            decoded = cv2.imdecode(np.frombuffer((self.output / entry["filename"]).read_bytes(),
                                                dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            np.testing.assert_array_equal(original, decoded)

    def test_capture_and_encoding_cost_do_not_add_half_second_drift(self):
        starts = []

        def supplier():
            starts.append(self.clock())
            self.clock.now += 0.1
            return self.frame

        encode = cv2.imencode

        def slow_encode(*args):
            self.clock.now += 0.15
            return encode(*args)

        with patch("src.overworld.calibration_capture.cv2.imencode", side_effect=slow_encode):
            self.capture(supplier)
        np.testing.assert_allclose(np.arange(10) * 0.5, starts)

    def test_missing_frame_stops_and_records_partial_count_without_reusing_cache(self):
        supplier = Mock(side_effect=[self.frame, None])
        with self.assertRaisesRegex(RuntimeError, "sample 2"):
            self.capture(supplier)
        self.assertEqual(2, supplier.call_count)
        self.assertEqual(1, self.metadata()["frame_count"])
        self.assertFalse(self.metadata()["complete"])
        self.assertFalse((self.output / "stationary_002.png").exists())

    def test_resolution_change_is_not_resized_to_fit(self):
        with self.assertRaisesRegex(RuntimeError, "resolution changed"):
            self.capture(Mock(side_effect=[self.frame, self.frame[:50]]))
        self.assertEqual(1, self.metadata()["frame_count"])

    def test_cancel_preserves_partial_metadata(self):
        with self.assertRaises(KeyboardInterrupt):
            self.capture(Mock(side_effect=[self.frame, KeyboardInterrupt()]))
        self.assertEqual(1, self.metadata()["frame_count"])
        self.assertIn("KeyboardInterrupt", self.metadata()["error"])

    def test_no_overwrite_even_for_incomplete_capture(self):
        self.output.mkdir()
        original = self.output / "stationary_001.png"
        original.write_bytes(b"existing capture")
        supplier = Mock()
        with self.assertRaises(FileExistsError):
            self.capture(supplier)
        self.assertEqual(b"existing capture", original.read_bytes())
        supplier.assert_not_called()

    def test_png_encoding_failure_is_not_reported_as_success(self):
        with patch("src.overworld.calibration_capture.cv2.imencode", return_value=(False, None)):
            with self.assertRaisesRegex(RuntimeError, "PNG encoding failed"):
                self.capture()
        self.assertEqual(0, self.metadata()["frame_count"])
        self.assertFalse(self.metadata()["complete"])

    def test_alpha_is_preserved_without_channel_conversion(self):
        self.frame = np.dstack((self.frame, np.full(self.frame.shape[:2], 187, dtype=np.uint8)))
        self.capture()
        decoded = cv2.imdecode(np.frombuffer((self.output / "stationary_001.png").read_bytes(),
                                            dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        np.testing.assert_array_equal(self.frame, decoded)

    def test_task_uses_only_framework_frame_and_sleep_calls(self):
        executor = Mock()
        executor.next_frame.return_value = self.frame
        task = CalibrationCaptureTask(executor=executor, app=Mock())
        task.output_directory, task.profile = self.output, "surface-test"
        self.assertEqual((BaseTask,), CalibrationCaptureTask.__bases__)
        task.run()
        self.assertTrue(task.report["complete"])
        self.assertEqual(10, executor.next_frame.call_count)
        executor.sleep.assert_any_call(5)
        executor.interaction.assert_not_called()
        self.assertTrue(all(call[0] in ("next_frame", "sleep") for call in executor.mock_calls))

    def test_config_isolates_tasks_inputs_startup_and_resolution_without_mutation(self):
        original = {"windows": {"exe": "game.exe", "interaction": "PostMessage",
                                "capture_method": ["WGC", "BitBlt_RenderFull"]},
                    "onetime_tasks": ["hunt"], "trigger_tasks": ["combat"],
                    "supported_resolution": {"resize_to": [(1280, 720)]},
                    "custom_tasks": True, "gui": {"type": "qt"}, "scene": "WWScene"}
        safe = capture_config(original)
        self.assertFalse(safe["windows"]["start_exe"])
        self.assertIs(CaptureOnlyInteraction, safe["windows"]["interaction"])
        self.assertIsInstance(CaptureOnlyInteraction(Mock(), Mock()), DoNothingInteraction)
        self.assertEqual([], safe["onetime_tasks"])
        self.assertEqual([], safe["trigger_tasks"])
        self.assertFalse(safe["custom_tasks"])
        self.assertFalse(safe["use_gui"])
        self.assertFalse(safe["check_mutex"])
        self.assertNotIn("supported_resolution", safe)
        self.assertNotIn("scene", safe)
        self.assertEqual("PostMessage", original["windows"]["interaction"])
        self.assertEqual(["hunt"], original["onetime_tasks"])

    def test_cli_does_not_attach_capture_for_help_or_invalid_profile(self):
        with patch("src.overworld.calibration_capture.OK") as app:
            for args in (["--help"], ["--profile", "../escape"]):
                with self.assertRaises(SystemExit):
                    main(args)
            app.assert_not_called()

    def test_command_runs_only_capture_task_and_closes_app_not_game(self):
        task = CalibrationCaptureTask(executor=Mock(), app=Mock())
        task.report = {"complete": True}
        with patch("src.overworld.calibration_capture.CAPTURE_ROOT", Path(self.temp.name)), \
                patch("src.overworld.calibration_capture.OK") as app_class:
            app = app_class.return_value
            app.get_task.return_value = (task, False)
            main(["--profile", "surface-test"])
            app.get_task.assert_called_once_with(CalibrationCaptureTask)
            app.run_task.assert_called_once_with(task, exit_after=False)
            app.quit.assert_called_once_with()
            self.assertEqual("surface-test", task.profile)
            self.assertEqual(Path(self.temp.name) / "surface-test", task.output_directory)

    def test_command_reports_executor_caught_error_as_failure(self):
        task = CalibrationCaptureTask(executor=Mock(), app=Mock())
        with patch("src.overworld.calibration_capture.CAPTURE_ROOT", Path(self.temp.name)), \
                patch("src.overworld.calibration_capture.OK") as app_class:
            app = app_class.return_value
            app.get_task.return_value = (task, False)
            with self.assertRaisesRegex(RuntimeError, "Capture incomplete"):
                main(["--profile", "surface-test"])
            app.quit.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
