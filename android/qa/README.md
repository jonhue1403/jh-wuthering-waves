# MobileRun QA Automation Suite for Infinix GT 30 Pro

This directory contains repeatable, physical-device automation scripts for testing the JH WuWa Android prototype (`com.jh.wuwa.mobile`) on the **Infinix GT 30 Pro** via MobileRun and ADB.

---

## Prerequisites

1. **Host PC:** Windows 11 with Python 3.12/3.13 and `uv`.
2. **Android Platform-Tools (ADB):** In PATH or at `%LOCALAPPDATA%\Android\platform-tools\adb.exe`.
3. **MobileRun CLI:** Installed via `uv tool install --python 3.12 mobilerun`.
4. **Physical Device:** Infinix GT 30 Pro connected over USB with USB debugging authorized (discovered dynamically or configured via `$env:ANDROID_SERIAL`).
5. **App APK:** `com.jh.wuwa.mobile` installed on device.

---

## Structure

- `harness.py`: Core QA device controller, MobileRun wrapper, UI inspector, screenshot/evidence collector, OpenVINO OCR canvas reader, and metric logger.
- `run_critical_chain.py`: Dedicated 3-consecutive-run runner verifying the critical physical chain (accessibility -> capture -> advancing frames -> tap -> swipe -> dual-pointer -> 3 visual taps -> stop -> capture recovery) with strict OCR counter assertions.
- `validate_assertions.py`: Machine-readable consistency and integrity auditor generating `assertion_consistency_report.json`.
- `generate_reconciled_results.py`: Results synthesizer generating non-contradictory `qa_results.json`.
- `test_group_a_installation_ui.py`: Group A tests (A01 - A08) for installation, viewport, layout adaptation, scrolling, and restart stability.
- `test_group_b_permissions_capture.py`: Group B tests (B01 - B08) for AccessibilityService binding, MediaProjection capture, orientation changes, and security guards.
- `test_group_c_touch_lab.py`: Group C tests (C01 - C10) for native TouchLabView interactions, taps, swipes, dual-finger multi-touch, 3 visual taps, and lifecycle cancels.
- `test_group_d_vision.py`: Group D tests (D01 - D10) for image acquisition, template extraction, contrast rejection, tap limits, and staleness timeouts.
- `test_group_e_lifecycle.py`: Group E tests (E01 - E10) for Home backgrounding, keyguard lock suppression, force-stop recovery, and JSON report privacy audits.
- `test_group_f_stability.py`: Group F benchmark (F01) measuring memory PSS, battery temperature, power draw, crashes, and ANRs across sustained capture.
- `test_phase8_game.py`: Group G tests (G01 - G02) verifying game package detection (`com.kurogame.wutheringwaves.global`) and target alignment.
- `run_qa_suite.py`: Master runner executing all groups and producing `qa_results.json`.
- `evidence/`: Captured screenshots and visual assertion evidence.

---

## Running the Suite

Run all tests from the repository root:

```powershell
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
.\.venv\Scripts\python.exe android/qa/run_qa_suite.py
```

To run individual test groups:

```powershell
.\.venv\Scripts\python.exe -c "
import sys; sys.path.insert(0, 'android/qa')
from harness import DeviceHarness
from test_group_c_touch_lab import run_group_c
h = DeviceHarness()
run_group_c(h)
"
```
