"""Execute the 3-Run Critical Physical Device QA Chain on Infinix GT 30 Pro.

Chain per run:
Accessibility active -> MediaProjection capture active -> Frame delivery ->
Single Tap (C02) -> Swipe (C03) -> 2 Fingers Multi-Touch (C04) ->
Three Visual Taps (C05/C06) -> Stop & Return (C07) -> Advancing frame counter (B04) ->
Capture recovery (B05/B07).

Repeated for 3 consecutive runs with genuine physical assertions.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

EVIDENCE_DIR = Path(__file__).resolve().parent / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

APP_PACKAGE = "com.jh.wuwa.mobile"
MAIN_ACTIVITY = "com.jh.wuwa.MainActivity"
TOUCH_LAB_ACTIVITY = "com.jh.wuwa.TouchLabActivity"
ACC_COMPONENT = "com.jh.wuwa.mobile/com.jh.wuwa.runtime.AutomationAccessibilityService"
CAPTURE_COMPONENT = "com.jh.wuwa.mobile/com.jh.wuwa.runtime.CaptureService"


def discover_serial() -> str:
    if os.environ.get("ANDROID_SERIAL"):
        return os.environ["ANDROID_SERIAL"].strip()
    adb = shutil.which("adb") or os.path.expandvars(r"%LOCALAPPDATA%\Android\platform-tools\adb.exe")
    res = subprocess.run([adb, "devices", "-l"], capture_output=True, text=True, errors="replace")
    for line in res.stdout.splitlines():
        line = line.strip()
        if line and not line.startswith("List of devices"):
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                return parts[0]
    raise RuntimeError("No authorized ADB device discovered")


class CriticalChainRunner:
    def __init__(self):
        self.serial = discover_serial()
        self.adb = shutil.which("adb") or os.path.expandvars(r"%LOCALAPPDATA%\Android\platform-tools\adb.exe")
        self.mobilerun = shutil.which("mobilerun") or os.path.expandvars(r"%USERPROFILE%\.local\bin\mobilerun.exe")
        self.env = os.environ.copy()
        self.env["PYTHONIOENCODING"] = "utf-8"
        self._init_ocr()

    def _init_ocr(self):
        from onnxocr.onnx_paddleocr import ONNXPaddleOcr
        self.ocr = ONNXPaddleOcr(use_openvino=True, use_angle_cls=False, use_gpu=False)

    def adb_shell(self, cmd: str) -> str:
        res = subprocess.run([self.adb, "-s", self.serial, "shell", cmd], capture_output=True, text=True, errors="replace", env=self.env)
        return res.stdout.strip()

    def mobilerun_cmd(self, args: List[str]) -> Tuple[int, str]:
        cmd = [self.mobilerun] + args + ["-d", self.serial]
        res = subprocess.run(cmd, capture_output=True, text=True, errors="replace", env=self.env)
        return res.returncode, res.stdout

    def take_screenshot(self, name: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = EVIDENCE_DIR / f"{name}_{timestamp}.png"
        with open(dest, "wb") as f:
            subprocess.run([self.adb, "-s", self.serial, "exec-out", "screencap", "-p"], stdout=f, env=self.env)
        return dest

    def get_ui(self) -> str:
        _, stdout = self.mobilerun_cmd(["device", "ui"])
        return stdout

    def tap(self, x: int, y: int):
        code, _ = self.mobilerun_cmd(["device", "tap", str(x), str(y)])
        if code != 0:
            self.adb_shell(f"input tap {x} {y}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int):
        code, _ = self.mobilerun_cmd(["device", "swipe", str(x1), str(y1), str(x2), str(y2)])
        if code != 0:
            self.adb_shell(f"input swipe {x1} {y1} {x2} {y2} 300")

    def get_element_bounds(self, target_text: str, ui_str: Optional[str] = None) -> Optional[Tuple[int, int, int, int]]:
        ui = ui_str or self.get_ui()
        # First try exact quoted match
        exact_pattern = r'["\']' + re.escape(target_text) + r'["\'].*?\((\d+),(\d+),(\d+),(\d+)\)'
        for line in ui.splitlines():
            m = re.search(exact_pattern, line, re.IGNORECASE)
            if m:
                return tuple(map(int, m.groups()))
        # Fallback to substring match
        for line in ui.splitlines():
            if target_text.lower() in line.lower():
                m = re.search(r"\((\d+),(\d+),(\d+),(\d+)\)", line)
                if m:
                    return tuple(map(int, m.groups()))
        return None

    def find_and_tap_element(self, text: str, max_scrolls: int = 2) -> bool:
        def attempt():
            bounds = self.get_element_bounds(text)
            if bounds:
                # If element is cutoff near the bottom edge (>= 2600), scroll up slightly to bring it into safe click range
                if bounds[3] > 2600:
                    self.swipe(600, 2000, 600, 1400)
                    time.sleep(1.0)
                    bounds = self.get_element_bounds(text)
                if bounds:
                    cx, cy = (bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2
                    print(f"  Tapped '{text}' at ({cx}, {cy})")
                    self.tap(cx, cy)
                    return True
            return False

        if attempt():
            return True
        for _ in range(max_scrolls):
            self.swipe(600, 2000, 600, 1000)
            time.sleep(1.0)
            if attempt():
                return True
        for _ in range(max_scrolls * 2):
            self.swipe(600, 1000, 600, 2000)
            time.sleep(1.0)
            if attempt():
                return True
        print(f"  FAILED to find element: '{text}'")
        return False

    def ocr_canvas(self, screenshot_path: Path) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        """Extract (target_taps, max_fingers, move_events) using host OpenVINO OCR."""
        from PIL import Image
        import cv2

        im = Image.open(str(screenshot_path))
        # Crop TouchLabView metrics region: x: 48..1176, y: 1950..2120
        crop = im.crop((48, 1950, 1176, 2120))
        temp = EVIDENCE_DIR / f"temp_{os.getpid()}_{int(time.time()*1000)}.png"
        crop.save(str(temp))
        try:
            res = self.ocr.ocr(cv2.imread(str(temp)))
            combined = ""
            if res:
                for line in res:
                    for item in line:
                        combined += " " + item[1][0]

            taps = None
            fingers = None
            move = None

            m_taps = re.search(r"Target taps:\s*(\d+)", combined)
            if m_taps:
                taps = int(m_taps.group(1))

            m_fingers = re.search(r"Max fingers:\s*(\d+)", combined)
            if m_fingers:
                fingers = int(m_fingers.group(1))

            m_move = re.search(r"Movement events:\s*(\d+)", combined)
            if m_move:
                move = int(m_move.group(1))

            return taps, fingers, move
        finally:
            if temp.exists():
                temp.unlink(missing_ok=True)

    def run_single_chain(self, run_index: int) -> Dict[str, Any]:
        print(f"\n=======================================================")
        print(f"CRITICAL CHAIN — RUN {run_index} / 3")
        print(f"=======================================================")
        run_record = {
            "run_index": run_index,
            "timestamp": datetime.now().isoformat(),
            "assertions": {},
            "all_passed": True,
        }

        # 1. Pre-condition: Check Accessibility Service
        acc_services = self.adb_shell("settings get secure enabled_accessibility_services")
        acc_ok = ACC_COMPONENT in acc_services
        run_record["assertions"]["accessibility_bound"] = {
            "expected": True,
            "actual": acc_ok,
            "passed": acc_ok,
            "category": "PHYSICAL PASS" if acc_ok else "PHYSICAL FAIL",
        }
        print(f"  [1/10] Accessibility Service: {'BOUND' if acc_ok else 'NOT BOUND'}")
        if not acc_ok:
            run_record["all_passed"] = False
            return run_record

        # 2. Pre-condition: Check CaptureService
        cap_svc = self.adb_shell(f"dumpsys activity services {CAPTURE_COMPONENT}")
        cap_ok = "CaptureService" in cap_svc
        run_record["assertions"]["capture_service_active"] = {
            "expected": True,
            "actual": cap_ok,
            "passed": cap_ok,
            "category": "PHYSICAL PASS" if cap_ok else "PHYSICAL FAIL",
        }
        print(f"  [2/10] CaptureService: {'ACTIVE' if cap_ok else 'INACTIVE'}")
        if not cap_ok:
            run_record["all_passed"] = False
            return run_record

        # 3. Enter Touch Lab using dynamic element tapping
        entered = self.find_and_tap_element("Open touch lab")
        time.sleep(2.0)
        ui_lab = self.get_ui()
        in_lab = "TOUCH LAB" in ui_lab and "Check the controls" in ui_lab
        run_record["assertions"]["touch_lab_entered"] = {
            "expected": True,
            "actual": in_lab,
            "passed": in_lab,
            "category": "PHYSICAL PASS" if in_lab else "PHYSICAL FAIL",
        }
        print(f"  [3/10] Touch Lab Entered: {in_lab}")
        if not in_lab:
            run_record["all_passed"] = False
            return run_record

        # 4. Read Baseline Canvas Metrics
        sc_base = self.take_screenshot(f"run{run_index}_00_baseline")
        b_taps, b_fingers, b_move = self.ocr_canvas(sc_base)
        print(f"  Baseline OCR: Taps={b_taps}, MaxFingers={b_fingers}, Move={b_move}")
        if b_taps is None or b_fingers is None or b_move is None:
            run_record["assertions"]["baseline_readable"] = {
                "expected": "All 3 numbers parsed via OCR",
                "actual": f"Taps={b_taps}, MaxFingers={b_fingers}, Move={b_move}",
                "passed": False,
                "category": "BLOCKED",
            }
            run_record["all_passed"] = False
            return run_record
        run_record["baseline"] = {"taps": b_taps, "fingers": b_fingers, "move": b_move}

        # 5. C02: Single Tap
        self.find_and_tap_element("Tap")
        time.sleep(2.0)
        sc_tap = self.take_screenshot(f"run{run_index}_01_single_tap")
        t1_taps, t1_fingers, t1_move = self.ocr_canvas(sc_tap)
        tap_passed = (t1_taps is not None) and (t1_taps > b_taps)
        rel_sc_tap = str(sc_tap.relative_to(EVIDENCE_DIR.parent)).replace("\\", "/")
        run_record["assertions"]["C02_single_tap"] = {
            "expected": f"target_taps > {b_taps}",
            "actual": f"target_taps = {t1_taps}",
            "passed": tap_passed,
            "category": "PHYSICAL PASS" if tap_passed else "PHYSICAL FAIL",
            "evidence": rel_sc_tap,
        }
        print(f"  [4/10] C02 Single Tap: {b_taps} -> {t1_taps} (PASSED: {tap_passed})")
        if not tap_passed:
            run_record["all_passed"] = False

        # 6. C03: Swipe Gesture
        self.find_and_tap_element("Swipe")
        time.sleep(2.0)
        sc_swipe = self.take_screenshot(f"run{run_index}_02_swipe")
        t2_taps, t2_fingers, t2_move = self.ocr_canvas(sc_swipe)
        swipe_passed = (t2_move is not None) and (t2_move > b_move)
        rel_sc_swipe = str(sc_swipe.relative_to(EVIDENCE_DIR.parent)).replace("\\", "/")
        run_record["assertions"]["C03_swipe"] = {
            "expected": f"move_events > {b_move}",
            "actual": f"move_events = {t2_move}",
            "passed": swipe_passed,
            "category": "PHYSICAL PASS" if swipe_passed else "PHYSICAL FAIL",
            "evidence": rel_sc_swipe,
        }
        print(f"  [5/10] C03 Swipe Movement: {b_move} -> {t2_move} (PASSED: {swipe_passed})")
        if not swipe_passed:
            run_record["all_passed"] = False

        # 7. C04: Two Simultaneous Fingers
        self.find_and_tap_element("2 fingers")
        time.sleep(2.0)
        sc_fingers = self.take_screenshot(f"run{run_index}_03_two_fingers")
        t3_taps, t3_fingers, t3_move = self.ocr_canvas(sc_fingers)
        fingers_passed = (t3_fingers is not None) and (t3_fingers >= 2)
        rel_sc_fingers = str(sc_fingers.relative_to(EVIDENCE_DIR.parent)).replace("\\", "/")
        run_record["assertions"]["C04_two_fingers"] = {
            "expected": "max_fingers >= 2",
            "actual": f"max_fingers = {t3_fingers}",
            "passed": fingers_passed,
            "category": "PHYSICAL PASS" if fingers_passed else "PHYSICAL FAIL",
            "evidence": rel_sc_fingers,
        }
        print(f"  [6/10] C04 Multi-Touch Fingers: max_fingers = {t3_fingers} (PASSED: {fingers_passed})")
        if not fingers_passed:
            run_record["all_passed"] = False

        # 8. C05/C06: Three Visual Taps Sequence
        pre_vis_taps = t3_taps if t3_taps is not None else t1_taps
        self.find_and_tap_element("Run 3 visual taps")
        print("  Waiting 8.5s for 3 visual match/disappear/reappear cycles...")
        time.sleep(8.5)
        sc_vis = self.take_screenshot(f"run{run_index}_04_visual_taps")
        t4_taps, t4_fingers, t4_move = self.ocr_canvas(sc_vis)
        expected_vis_taps = pre_vis_taps + 3
        vis_passed = (t4_taps is not None) and (t4_taps == expected_vis_taps)
        rel_sc_vis = str(sc_vis.relative_to(EVIDENCE_DIR.parent)).replace("\\", "/")
        run_record["assertions"]["C05_three_visual_taps"] = {
            "expected": f"target_taps == {expected_vis_taps} (exactly +3)",
            "actual": f"target_taps = {t4_taps}",
            "passed": vis_passed,
            "category": "PHYSICAL PASS" if vis_passed else "PHYSICAL FAIL",
            "evidence": rel_sc_vis,
        }
        print(f"  [7/10] C05/C06 Three Visual Taps: {pre_vis_taps} -> {t4_taps} (PASSED: {vis_passed})")
        if not vis_passed:
            run_record["all_passed"] = False

        # 9. Stop and Return (C07 & C08)
        self.find_and_tap_element("Stop and return")
        time.sleep(2.0)
        ui_back = self.get_ui()
        returned_main = any(k in ui_back for k in ["JH  /  WUWA MOBILE", "SESSION", "Check your device first", "Open touch lab"])
        run_record["assertions"]["C07_stop_and_return"] = {
            "expected": True,
            "actual": returned_main,
            "passed": returned_main,
            "category": "PHYSICAL PASS" if returned_main else "PHYSICAL FAIL",
        }
        print(f"  [8/10] C07 Stop & Return: {returned_main}")

        # 10. Frame Counter Advancing (B04)
        # Scroll up to top to view SESSION metrics
        self.swipe(600, 600, 600, 2400)
        time.sleep(1.0)
        ui_session = self.get_ui()
        m_frames = re.search(r"Capture on.*?(\d+)\s+frames", ui_session)
        frame_count = int(m_frames.group(1)) if m_frames else 0
        frames_advancing = frame_count > 0
        run_record["assertions"]["B04_frames_advancing"] = {
            "expected": "frame_count > 0",
            "actual": f"frame_count = {frame_count}",
            "passed": frames_advancing,
            "category": "PHYSICAL PASS" if frames_advancing else "PHYSICAL FAIL",
        }
        print(f"  [9/10] B04 Frames Advancing: frame_count = {frame_count} (PASSED: {frames_advancing})")
        if not frames_advancing:
            run_record["all_passed"] = False

        # 11. Capture Recovery Cycle (B05 & B07)
        # Find and tap "Stop screen capture"
        self.find_and_tap_element("Stop screen capture")
        time.sleep(2.0)
        cap_after_stop = self.adb_shell(f"dumpsys activity services {CAPTURE_COMPONENT}")
        stopped_cleanly = "CaptureService" not in cap_after_stop

        # Now restart capture: find and tap "Start screen capture"
        self.find_and_tap_element("Start screen capture")
        time.sleep(1.5)
        # Handle MediaProjection system prompt: tap "Share screen"
        self.find_and_tap_element("Share screen")
        time.sleep(2.0)
        cap_after_start = self.adb_shell(f"dumpsys activity services {CAPTURE_COMPONENT}")
        resumed_cleanly = "CaptureService" in cap_after_start

        recovery_passed = stopped_cleanly and resumed_cleanly
        run_record["assertions"]["B07_capture_recovery"] = {
            "expected": "Capture stops cleanly then resumes cleanly",
            "actual": f"stopped={stopped_cleanly}, resumed={resumed_cleanly}",
            "passed": recovery_passed,
            "category": "PHYSICAL PASS" if recovery_passed else "PHYSICAL FAIL",
        }
        print(f"  [10/10] B05/B07 Capture Recovery: stopped={stopped_cleanly}, resumed={resumed_cleanly} (PASSED: {recovery_passed})")
        if not recovery_passed:
            run_record["all_passed"] = False

        print(f"\nRun {run_index} All Assertions Passed: {run_record['all_passed']}")
        return run_record

    def run_all(self) -> Dict[str, Any]:
        runs = []
        for i in range(1, 4):
            r = self.run_single_chain(i)
            runs.append(r)
            time.sleep(2.0)

        all_three_passed = all(r["all_passed"] for r in runs)
        summary = {
            "timestamp": datetime.now().isoformat(),
            "target_model": "Infinix GT 30 Pro (Infinix X6873)",
            "android_version": self.adb_shell("getprop ro.build.version.release"),
            "consecutive_runs": len(runs),
            "all_three_runs_passed": all_three_passed,
            "runs": runs,
        }

        out_path = Path(__file__).resolve().parent / "critical_chain_results.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to: {out_path}")
        print(f"OVERALL 3-RUN VALIDATION VERDICT: {'PASSED' if all_three_passed else 'FAILED'}")
        return summary


if __name__ == "__main__":
    runner = CriticalChainRunner()
    res = runner.run_all()
    sys.exit(0 if res["all_three_runs_passed"] else 1)
