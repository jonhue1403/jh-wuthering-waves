"""Custom-task entry point for a stationary/map calibration pair.

Load this file through the project's custom task editor. It never walks,
teleports, starts combat, or enables a hunt profile.
"""

from datetime import datetime, timezone
import json

import cv2
from ok import BaseTask

from src.overworld.calibration_capture import CAPTURE_ROOT, capture_stationary, check_output
from src.overworld.input_access import require_game_input_access
from src.task.BaseWWTask import BaseWWTask


class HuntCalibrationCapture(BaseWWTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Hunt Calibration Capture"
        self.description = "Capture a stationary sample set, then open and capture the map. No movement."

    def sleep(self, seconds):
        return BaseTask.sleep(self, seconds)

    def run(self):
        if any(task.enabled for task in self.executor.trigger_tasks):
            raise ValueError("Disable background tasks before calibration")
        require_game_input_access(self.executor.device_manager.hwnd_window.hwnd)
        self.next_frame()
        if not self.in_team_and_world():
            raise ValueError("Start calibration with the stationary character visible in the world")
        label = "live-pair-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output = CAPTURE_ROOT / label
        check_output(output)
        report = capture_stationary(
            output, label, self.next_frame, self.sleep,
            lambda: f"{type(self.executor.method).__module__}.{type(self.executor.method).__name__}",
        )
        self.send_key("m", down_time=0.1)
        self.sleep(1.5)
        frame = self.next_frame()
        success, encoded = cv2.imencode(".png", frame)
        if not success:
            raise RuntimeError("Full-map PNG encoding failed")
        with (output / "full_map_position.png").open("xb") as handle:
            handle.write(encoded.tobytes())
        evidence = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "stationary_samples": report["frame_count"],
            "map_input_sent": True,
            "team_ui_still_visible": bool(self.in_team_and_world()),
            "requires_visual_map_review": True,
            "movement_started": False,
        }
        (output / "map_capture.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        self.info_set("Capture Directory", str(output))
        self.log_info(f"Calibration pair saved: {output}")
        if evidence["team_ui_still_visible"]:
            raise RuntimeError("Map input did not remove the world UI; inspect the captured frame")
