"""MobileRun and ADB test harness for physical Android device QA."""

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

EVIDENCE_DIR = Path(__file__).resolve().parent / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SERIAL = "143382554J102386"
APP_PACKAGE = "com.jh.wuwa.mobile"
MAIN_ACTIVITY = "com.jh.wuwa.MainActivity"
TOUCH_LAB_ACTIVITY = "com.jh.wuwa.TouchLabActivity"
GAME_PACKAGE = "com.kurogame.wutheringwaves.global"
ACCESSIBILITY_SERVICE_COMPONENT = "com.jh.wuwa.mobile/com.jh.wuwa.runtime.AutomationAccessibilityService"
CAPTURE_SERVICE_COMPONENT = "com.jh.wuwa.mobile/com.jh.wuwa.runtime.CaptureService"


@dataclass
class TestResult:
    test_id: str
    group: str
    name: str
    preconditions: str
    action: str
    expected: str
    actual: str
    status: str  # PASS, FAIL, BLOCKED, NOT RUN
    evidence: List[str] = field(default_factory=list)
    failure_classification: Optional[str] = None
    duration_s: float = 0.0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DeviceHarness:
    def __init__(self, serial: str = DEFAULT_SERIAL):
        self.serial = serial
        self.adb_bin = self._find_adb()
        self.mobilerun_bin = self._find_mobilerun()
        self.env = os.environ.copy()
        self.env["PYTHONIOENCODING"] = "utf-8"
        if "platform-tools" not in self.env.get("Path", ""):
            adb_dir = str(Path(self.adb_bin).parent)
            self.env["Path"] = adb_dir + ";" + self.env.get("Path", "")

    def _find_adb(self) -> str:
        candidates = [
            shutil.which("adb"),
            os.path.expandvars(r"%LOCALAPPDATA%\Android\platform-tools\adb.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
            r"C:\platform-tools\adb.exe",
        ]
        for c in candidates:
            if c and os.path.exists(c):
                return c
        return "adb"

    def _find_mobilerun(self) -> str:
        candidates = [
            shutil.which("mobilerun"),
            os.path.expandvars(r"%USERPROFILE%\.local\bin\mobilerun.exe"),
            os.path.expandvars(r"%APPDATA%\uv\tools\mobilerun\Scripts\mobilerun.exe"),
        ]
        for c in candidates:
            if c and os.path.exists(c):
                return c
        return "mobilerun"

    def adb_cmd(self, args: List[str], timeout: float = 15.0) -> Tuple[int, str, str]:
        cmd = [self.adb_bin, "-s", self.serial] + args
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=self.env,
                timeout=timeout,
            )
            return res.returncode, res.stdout, res.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "ADB command timed out"

    def adb_shell(self, shell_cmd: str, timeout: float = 15.0) -> str:
        _, stdout, _ = self.adb_cmd(["shell", shell_cmd], timeout=timeout)
        return stdout.strip()

    def mobilerun_cmd(self, args: List[str], timeout: float = 20.0) -> Tuple[int, str, str]:
        cmd = [self.mobilerun_bin] + args + ["-d", self.serial]
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=self.env,
                timeout=timeout,
            )
            return res.returncode, res.stdout, res.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "MobileRun command timed out"

    def get_device_info(self) -> Dict[str, str]:
        manufacturer = self.adb_shell("getprop ro.product.manufacturer")
        model = self.adb_shell("getprop ro.product.model")
        release = self.adb_shell("getprop ro.build.version.release")
        sdk = self.adb_shell("getprop ro.build.version.sdk")
        display_id = self.adb_shell("getprop ro.build.display.id")
        wm_size = self.adb_shell("wm size")
        wm_density = self.adb_shell("wm density")
        return {
            "serial": self.serial,
            "manufacturer": manufacturer,
            "model": model,
            "android_version": release,
            "sdk_version": sdk,
            "build_id": display_id,
            "display_size": wm_size,
            "display_density": wm_density,
        }

    def get_ui_tree(self, timeout: float = 15.0) -> Dict[str, Any]:
        code, stdout, stderr = self.mobilerun_cmd(["device", "ui"], timeout=timeout)
        return {
            "exit_code": code,
            "raw_output": stdout,
            "error": stderr,
            "elements": [line.strip() for line in stdout.splitlines() if line.strip()],
        }

    def find_element_bounds(self, text: str) -> Optional[Tuple[int, int, int, int]]:
        ui = self.get_ui_tree()
        for line in ui.get("elements", []):
            if text.lower() in line.lower():
                m = re.search(r"\((\d+),(\d+),(\d+),(\d+)\)", line)
                if m:
                    return tuple(map(int, m.groups()))
        return None

    def tap_element(self, text: str, max_scrolls: int = 2, timeout: float = 1.5) -> bool:
        bounds = self.find_element_bounds(text)
        if bounds:
            x1, y1, x2, y2 = bounds
            self.tap((x1 + x2) // 2, (y1 + y2) // 2)
            time.sleep(timeout)
            return True
        # Try scroll down
        for _ in range(max_scrolls):
            self.swipe(600, 2000, 600, 800)
            time.sleep(1.0)
            bounds = self.find_element_bounds(text)
            if bounds:
                x1, y1, x2, y2 = bounds
                self.tap((x1 + x2) // 2, (y1 + y2) // 2)
                time.sleep(timeout)
                return True
        # Try scroll up
        for _ in range(max_scrolls * 2):
            self.swipe(600, 800, 600, 2000)
            time.sleep(1.0)
            bounds = self.find_element_bounds(text)
            if bounds:
                x1, y1, x2, y2 = bounds
                self.tap((x1 + x2) // 2, (y1 + y2) // 2)
                time.sleep(timeout)
                return True
        return False

    def take_screenshot(self, name_prefix: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        dest_path = EVIDENCE_DIR / f"{name_prefix}_{timestamp}.png"

        code, stdout, _ = self.mobilerun_cmd(["device", "screenshot"], timeout=15.0)
        if code == 0 and stdout.strip():
            for line in stdout.splitlines():
                line = line.strip()
                if line.endswith(".png") and os.path.exists(line):
                    shutil.copyfile(line, str(dest_path))
                    return dest_path

        with open(dest_path, "wb") as f:
            subprocess.run(
                [self.adb_bin, "-s", self.serial, "exec-out", "screencap", "-p"],
                stdout=f,
                env=self.env,
                timeout=10.0,
            )
        return dest_path

    def tap(self, x: int, y: int) -> bool:
        code, _, _ = self.mobilerun_cmd(["device", "tap", str(x), str(y)])
        if code != 0:
            self.adb_shell(f"input tap {x} {y}")
        return True

    def swipe(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        code, _, _ = self.mobilerun_cmd(["device", "swipe", str(x1), str(y1), str(x2), str(y2)])
        if code != 0:
            self.adb_shell(f"input swipe {x1} {y1} {x2} {y2} 300")
        return True

    def launch_app(self, package: str = APP_PACKAGE, activity: str = MAIN_ACTIVITY) -> None:
        self.adb_shell(f"am start -n {package}/{activity}")
        time.sleep(1.5)

    def force_stop(self, package: str = APP_PACKAGE) -> None:
        self.adb_shell(f"am force-stop {package}")
        time.sleep(0.5)

    def is_process_running(self, package: str = APP_PACKAGE) -> bool:
        pids = self.adb_shell(f"pidof {package}")
        return bool(pids and pids.strip())

    def is_capture_running(self) -> bool:
        out = self.adb_shell(f"dumpsys activity services {CAPTURE_SERVICE_COMPONENT}")
        return "CaptureService" in out

    def ensure_accessibility_enabled(self) -> bool:
        services = self.adb_shell("settings get secure enabled_accessibility_services")
        if ACCESSIBILITY_SERVICE_COMPONENT in services:
            return True
        self.adb_shell("am start -a android.settings.ACCESSIBILITY_SETTINGS")
        time.sleep(1.5)
        # Tap "JH WuWa touch control"
        self.tap_element("JH WuWa touch control")
        time.sleep(1.0)
        # Tap switch
        self.tap(1055, 446)
        time.sleep(1.0)
        # Tap Allow button on dialog if shown
        self.tap_element("Allow")
        time.sleep(1.0)
        services = self.adb_shell("settings get secure enabled_accessibility_services")
        return ACCESSIBILITY_SERVICE_COMPONENT in services

    def ensure_capture_started(self) -> bool:
        if self.is_capture_running():
            return True
        self.launch_app(APP_PACKAGE)
        time.sleep(1.0)
        # Scroll to top of MainActivity
        self.swipe(600, 600, 600, 2400)
        time.sleep(1.0)
        # Tap "Start screen capture"
        self.tap_element("Start screen capture")
        time.sleep(1.5)
        # If notification permission prompt appears
        self.tap_element("Allow")
        time.sleep(1.0)
        # If MediaProjection system prompt appears, tap "Share screen"
        self.tap_element("Share screen")
        time.sleep(2.0)
        return self.is_capture_running()

    def check_logcat_crashes(self, since_seconds: int = 10, package: str = APP_PACKAGE) -> List[str]:
        out = self.adb_shell(f"logcat -d -t {since_seconds}s *:E")
        crashes = []
        for line in out.splitlines():
            if package in line and ("FATAL EXCEPTION" in line or "AndroidRuntime" in line or "CRASH" in line):
                crashes.append(line)
        return crashes

    def ocr_canvas(self, screenshot_path: Path, crop_box: Optional[Tuple[int, int, int, int]] = None) -> List[str]:
        from PIL import Image
        import cv2

        im = Image.open(str(screenshot_path))
        if crop_box:
            im = im.crop(crop_box)
        temp_crop = EVIDENCE_DIR / f"temp_crop_{os.getpid()}.png"
        im.save(str(temp_crop))

        try:
            from onnxocr.onnx_paddleocr import ONNXPaddleOcr

            ocr = ONNXPaddleOcr(use_openvino=True, use_angle_cls=False, use_gpu=False)
            res = ocr.ocr(cv2.imread(str(temp_crop)))
            texts = []
            if res:
                for line in res:
                    for item in line:
                        texts.append(item[1][0])
            return texts
        except Exception as e:
            return [f"OCR_ERROR: {e}"]
        finally:
            if temp_crop.exists():
                temp_crop.unlink(missing_ok=True)

    def get_resource_metrics(self, package: str = APP_PACKAGE) -> Dict[str, Any]:
        mem_out = self.adb_shell(f"dumpsys meminfo {package}")
        pss_match = re.search(r"TOTAL PSS:\s+(\d+)", mem_out)
        total_pss_kb = int(pss_match.group(1)) if pss_match else None

        battery_out = self.adb_shell("dumpsys battery")
        level_match = re.search(r"level:\s+(\d+)", battery_out)
        temp_match = re.search(r"temperature:\s+(\d+)", battery_out)
        level = int(level_match.group(1)) if level_match else None
        temp_c = (int(temp_match.group(1)) / 10.0) if temp_match else None

        cpu_out = self.adb_shell(f"dumpsys cpuinfo | grep {package}")

        return {
            "pss_kb": total_pss_kb,
            "pss_mb": (round(total_pss_kb / 1024, 2) if total_pss_kb else None),
            "battery_level_pct": level,
            "battery_temp_c": temp_c,
            "cpu_snippet": cpu_out.strip(),
        }
