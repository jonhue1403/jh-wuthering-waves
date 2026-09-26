"""Custom task for live validation of the checkout without restarting its UI.

Load only while the executor is idle. Uses HuntMobTask's normal config and
preflight gates. It can close an explicitly recognized map before validation.
"""

from dataclasses import asdict
from datetime import datetime, timezone
import importlib
import json
import re

import cv2
from ok import BaseTask

from src.overworld import calibration_capture
from src.overworld import controller
from src.overworld.input_access import require_game_input_access
from src.overworld.navigation import image_matcher
from src.overworld.navigation import arrow_heading
from src.overworld.navigation import ok_adapter
import src.overworld.navigation as navigation

importlib.reload(image_matcher)
importlib.reload(arrow_heading)
importlib.reload(controller)
importlib.reload(ok_adapter)
navigation.WWTaskNavigationBackend = ok_adapter.WWTaskNavigationBackend
_hunt = importlib.reload(importlib.import_module("src.task.HuntMobTask"))


class HuntLiveValidation(_hunt.HuntMobTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Hunt Live Validation"
        self.description = "Run the current checkout's guarded localization, short-walk, or one-camp validation."

    def run(self):
        if any(task.enabled for task in self.executor.trigger_tasks):
            raise ValueError("Disable background tasks before live validation")
        self.next_frame()
        if not self.in_team_and_world():
            if not self.ocr(0.7, 0.8, 1, 1, match=re.compile(r"Switch Map|切换地图|切換地圖")):
                raise ValueError("Start validation in the world or on the full map")
            require_game_input_access(self.executor.device_manager.hwnd_window.hwnd)
            self.send_key("m", down_time=.1)
            BaseTask.sleep(self, 1.5)
            self.next_frame()
            if not self.in_team_and_world():
                raise ValueError("Closing the map did not restore the world UI")
        output = calibration_capture.CAPTURE_ROOT / ("live-validation-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
        output.mkdir(parents=True)
        cv2.imwrite(str(output / "before.png"), self.frame)
        error = None
        try:
            return super().run()
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            # Do not take a new frame after cancellation; the last captured
            # frame and cleanup diagnostics remain available without new input.
            cv2.imwrite(str(output / "last.png"), self.frame)
            evidence = {"error": error, "localization": self.localization_report,
                        "walk": asdict(self.walk_result) if self.walk_result else None,
                        "hunt": asdict(self.hunt_run) if self.hunt_run else None}
            (output / "result.json").write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")
            self.info_set("Validation Evidence", str(output))
