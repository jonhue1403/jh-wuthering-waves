"""Capture-only calibration command; never starts the hunt or an input task."""

import argparse
import copy
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from ok import BaseTask, DoNothingInteraction, OK


FRAME_COUNT = 10
INTERVAL_SECONDS = 0.5
CAPTURE_ROOT = Path(__file__).resolve().parents[2] / "assets/overworld/calibration"


def check_output(directory):
    """Never replace an earlier (including incomplete) calibration capture."""
    directory = Path(directory)
    if directory.exists() and (not directory.is_dir()
                               or any(directory.glob("stationary_*.png"))
                               or (directory / "metadata.json").exists()):
        raise FileExistsError(f"Capture already exists at {directory}; choose a new --profile label")


def capture_stationary(directory, profile, next_frame, sleep, backend, *, clock=time.monotonic):
    """Save exactly the fresh arrays supplied by OK-Script, without image transforms.

    Timestamps are host receipt times, not game/render timestamps. Identical
    stationary images are valid; missing frames are not replaced by cached ones.
    """
    directory = Path(directory)
    check_output(directory)
    directory.mkdir(parents=True, exist_ok=True)
    report = {
        "capture_timestamp": datetime.now(timezone.utc).isoformat(),
        "calibration_profile": profile,
        "interval_requested_ms": int(INTERVAL_SECONDS * 1000),
        "frames_requested": FRAME_COUNT,
        "frame_count": 0,
        "frame_dimensions": None,
        "capture_backend": None,
        "complete": False,
        "frames": [],
    }
    with (directory / "metadata.json").open("x", encoding="utf-8") as metadata:
        try:
            started = clock()
            next_due = started
            for index in range(1, FRAME_COUNT + 1):
                remaining = next_due - clock()
                if remaining > 0:
                    sleep(remaining)
                capture_started = clock()
                frame = next_frame()
                received = clock()
                timestamp = datetime.now(timezone.utc).isoformat()
                if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8
                        or frame.ndim != 3 or frame.shape[2] not in (3, 4)
                        or min(frame.shape[:2]) <= 0):
                    raise RuntimeError(f"No valid full game frame for sample {index}")
                dimensions = {"width": frame.shape[1], "height": frame.shape[0]}
                active_backend = backend()
                if index == 1:
                    report["frame_dimensions"] = dimensions
                    report["capture_backend"] = active_backend
                elif dimensions != report["frame_dimensions"]:
                    raise RuntimeError("Capture resolution changed; repeat with a new profile label")
                success, encoded = cv2.imencode(".png", frame.copy())
                if not success:
                    raise RuntimeError(f"PNG encoding failed for sample {index}")
                filename = f"stationary_{index:03d}.png"
                with (directory / filename).open("xb") as output:
                    output.write(encoded.tobytes())
                report["frames"].append({
                    "filename": filename,
                    "capture_timestamp": timestamp,
                    "elapsed_seconds": received - started,
                    "frame_dimensions": dimensions,
                    "capture_backend": active_backend,
                })
                report["frame_count"] = len(report["frames"])
                # Include encoding time in the interval, without burst catch-up.
                next_due = capture_started + INTERVAL_SECONDS
            report["complete"] = True
        except BaseException as error:
            report["error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            json.dump(report, metadata, indent=2, ensure_ascii=False)
            metadata.write("\n")
    return report


class CaptureOnlyInteraction(DoNothingInteraction):
    """Adapt OK-Script's no-input backend to its Windows constructor signature."""

    def __init__(self, capture, hwnd_window):
        super().__init__(capture)


class CalibrationCaptureTask(BaseTask):
    # Deliberately not WWOneTimeTask: its startup can send game inputs.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.output_directory = None
        self.profile = None
        self.report = None

    def run(self):
        if self.output_directory is None:
            raise ValueError("Use the calibration_capture debug command")
        self.log_info("Capture only: switch back to the game and stay still; sampling in 5 seconds")
        self.sleep(5)
        self.report = capture_stationary(
            self.output_directory, self.profile, self.next_frame, self.sleep,
            lambda: f"{type(self.executor.method).__module__}.{type(self.executor.method).__name__}",
        )
        self.log_info(f"Saved {self.report['frame_count']} full frames to {self.output_directory}")


def capture_config(app_config):
    """Allowlist capture settings only; no GUI, hunt, triggers, startup or resizing."""
    windows = copy.deepcopy(app_config["windows"])
    windows["start_exe"] = False
    windows["interaction"] = CaptureOnlyInteraction
    return {
        "windows": windows,
        "use_gui": False,
        "debug": False,
        # The standard mutex handler can terminate another OK-WW instance.
        "check_mutex": False,
        "config_folder": app_config.get("config_folder", "configs"),
        "custom_tasks": False,
        "onetime_tasks": [],
        "trigger_tasks": [],
        "log_file": "logs/calibration-capture.log",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=(
        "Capture 10 untouched full game PNGs, 500 ms apart. Close other OK-WW "
        "instances, launch the game yourself, and stand stationary. No game inputs are sent."
    ))
    parser.add_argument("--profile", required=True,
                        help="Capture-set/profile label, e.g. surface-test-01; no calibrated JSON required")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", args.profile):
        parser.error("--profile must be 1-80 letters/digits/underscores/hyphens, starting with a letter/digit")
    output = CAPTURE_ROOT / args.profile
    check_output(output)
    from config import config

    app = OK(capture_config(config))
    try:
        task, _ = app.get_task(CalibrationCaptureTask)
        task.output_directory = output
        task.profile = args.profile
        app.run_task(task, exit_after=False)
        # The executor catches task errors; do not print success for those cases.
        if not task.report or not task.report["complete"]:
            raise RuntimeError(f"Capture incomplete; inspect {output} and logs/calibration-capture.log")
        print(f"Saved 10 full game frames and metadata: {output}")
    finally:
        app.quit()


if __name__ == "__main__":
    main()
