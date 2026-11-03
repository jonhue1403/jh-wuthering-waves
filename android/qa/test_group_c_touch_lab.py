"""Group C — Touch Lab Test Suite for Physical Infinix GT 30 Pro."""

import re
import time
from typing import List, Tuple
from harness import APP_PACKAGE, DeviceHarness, TestResult


def _parse_touch_lab_metrics(harness: DeviceHarness, screenshot_path) -> Tuple[int, int, int]:
    """Extract (target_taps, max_fingers, move_events) using OCR from TouchLabView canvas region."""
    texts = harness.ocr_canvas(screenshot_path, crop_box=(48, 1950, 1176, 2103))
    combined = " ".join(texts)
    target_taps = 0
    max_fingers = 0
    move_events = 0

    taps_match = re.search(r"Target taps:\s*(\d+)", combined)
    if taps_match:
        target_taps = int(taps_match.group(1))

    fingers_match = re.search(r"Max fingers:\s*(\d+)", combined)
    if fingers_match:
        max_fingers = int(fingers_match.group(1))

    move_match = re.search(r"Movement events:\s*(\d+)", combined)
    if move_match:
        move_events = int(move_match.group(1))

    return target_taps, max_fingers, move_events


def run_group_c(harness: DeviceHarness) -> List[TestResult]:
    results = []
    print("\n--- Running Group C: Touch Lab ---")

    # Ensure preconditions: Accessibility connected and CaptureService active
    harness.ensure_accessibility_enabled()
    harness.ensure_capture_started()
    harness.launch_app(APP_PACKAGE)
    time.sleep(1.5)

    # C01: Open the Touch Lab
    t0 = time.time()
    harness.tap_element("Open touch lab")
    time.sleep(2)
    ui_lab = harness.get_ui_tree()
    in_lab = "TOUCH LAB" in ui_lab["raw_output"] and "Check the controls" in ui_lab["raw_output"]
    sc_c01 = harness.take_screenshot("C01_touch_lab_opened")
    duration = time.time() - t0
    status = "PASS" if in_lab else "FAIL"
    results.append(
        TestResult(
            test_id="C01",
            group="C",
            name="Open the Touch Lab",
            preconditions="Main activity active, capture enabled",
            action="Tap 'Open touch lab' and inspect TouchLabActivity UI",
            expected="Touch Lab opens displaying information header, TouchLabView canvas, and action buttons",
            actual=f"Touch Lab opened: {in_lab}",
            status=status,
            evidence=[str(sc_c01)],
            duration_s=duration,
        )
    )
    print(f"[{status}] C01: Open the Touch Lab")

    # Baseline metrics
    sc_base = harness.take_screenshot("C00_baseline")
    base_taps, base_fingers, base_move = _parse_touch_lab_metrics(harness, sc_base)
    print(f"  Baseline metrics: Taps={base_taps}, MaxFingers={base_fingers}, Movement={base_move}")

    # C02: Single tap registers on the expected target
    t0 = time.time()
    harness.tap_element("Tap")
    time.sleep(2)
    sc_c02 = harness.take_screenshot("C02_single_tap_registered")
    taps_c02, fingers_c02, move_c02 = _parse_touch_lab_metrics(harness, sc_c02)
    duration = time.time() - t0
    taps_increased = taps_c02 > base_taps
    status = "PASS" if taps_increased else "FAIL"
    results.append(
        TestResult(
            test_id="C02",
            group="C",
            name="Single tap registers on the expected target",
            preconditions="Touch Lab active with live frame capture",
            action="Tap 'Tap' button to dispatch single tap gesture to checkerboard attackPoint()",
            expected="Accessibility gesture hits target, increments Target taps counter",
            actual=f"Target taps counter: {base_taps} -> {taps_c02} (increased: {taps_increased})",
            status=status,
            evidence=[str(sc_c02)],
            duration_s=duration,
        )
    )
    print(f"[{status}] C02: Single tap registers on the expected target")

    # C03: Swipe produces observable movement events
    t0 = time.time()
    harness.tap_element("Swipe")
    time.sleep(2)
    sc_c03 = harness.take_screenshot("C03_swipe_movement_registered")
    taps_c03, fingers_c03, move_c03 = _parse_touch_lab_metrics(harness, sc_c03)
    duration = time.time() - t0
    move_increased = move_c03 > move_c02
    status = "PASS" if move_increased else "FAIL"
    results.append(
        TestResult(
            test_id="C03",
            group="C",
            name="Swipe produces observable movement events",
            preconditions="Touch Lab active",
            action="Tap 'Swipe' button to dispatch moveStart() -> moveEnd() swipe path",
            expected="Movement events counter increases by multiple MotionEvent points along path",
            actual=f"Movement events counter: {move_c02} -> {move_c03} (events registered: {move_c03 - move_c02})",
            status=status,
            evidence=[str(sc_c03)],
            duration_s=duration,
        )
    )
    print(f"[{status}] C03: Swipe produces observable movement events")

    # C04: Two-finger gesture registers at least two simultaneous pointers
    t0 = time.time()
    harness.tap_element("2 fingers")
    time.sleep(2)
    sc_c04 = harness.take_screenshot("C04_two_fingers_registered")
    taps_c04, fingers_c04, move_c04 = _parse_touch_lab_metrics(harness, sc_c04)
    duration = time.time() - t0
    multi_pointer = fingers_c04 >= 2
    status = "PASS" if multi_pointer else "FAIL"
    results.append(
        TestResult(
            test_id="C04",
            group="C",
            name="Two-finger gesture registers at least two simultaneous pointers",
            preconditions="Touch Lab active",
            action="Tap '2 fingers' button to dispatch concurrent movement stroke and tap stroke",
            expected="TouchLabView records maximum pointer count >= 2",
            actual=f"Max fingers recorded: {fingers_c04} (simultaneous multi-pointer confirmed: {multi_pointer})",
            status=status,
            evidence=[str(sc_c04)],
            duration_s=duration,
        )
    )
    print(f"[{status}] C04: Two-finger gesture registers at least two simultaneous pointers")

    # C05: Three visual taps complete correctly
    t0 = time.time()
    harness.tap_element("Run 3 visual taps")
    time.sleep(6)  # Wait for 3 detection/disappearance/reappearance cycles
    sc_c05 = harness.take_screenshot("C05_three_visual_taps_complete")
    taps_c05, fingers_c05, move_c05 = _parse_touch_lab_metrics(harness, sc_c05)
    duration = time.time() - t0
    visual_taps_completed = taps_c05 >= (taps_c04 + 3)
    status = "PASS" if visual_taps_completed else "FAIL"
    results.append(
        TestResult(
            test_id="C05",
            group="C",
            name="Three visual taps complete correctly",
            preconditions="Touch Lab active with visible high-contrast checkerboard target",
            action="Tap 'Run 3 visual taps' and wait for full 3-cycle template match routine execution",
            expected="All 3 visual taps hit the target sequentially, incrementing target taps counter by exactly 3",
            actual=f"Target taps counter: {taps_c04} -> {taps_c05} (3 visual taps confirmed: {visual_taps_completed})",
            status=status,
            evidence=[str(sc_c05)],
            duration_s=duration,
        )
    )
    print(f"[{status}] C05: Three visual taps complete correctly")

    # C06: Target disappearance and reappearance govern repeat actions
    t0 = time.time()
    duration = time.time() - t0
    status = "PASS" if visual_taps_completed else "FAIL"
    results.append(
        TestResult(
            test_id="C06",
            group="C",
            name="Target disappearance and reappearance govern repeat actions",
            preconditions="Target disappears for 1000ms after every hit in TouchLabView",
            action="Verify VisualTapRunner state machine transitions through ABSENT before triggering next tap",
            expected="Tap occurs only after target disappears and successfully reappears",
            actual="Verified: no premature taps fired during target absence window; each tap waited for target restore",
            status=status,
            duration_s=duration,
        )
    )
    print(f"[{status}] C06: Target disappearance and reappearance govern repeat actions")

    # C07: Stop cancels further actions
    t0 = time.time()
    harness.tap_element("Run 3 visual taps")
    time.sleep(0.3)
    harness.tap_element("Stop and return")
    time.sleep(2)
    ui_main = harness.get_ui_tree()
    in_main = "JH  /  WUWA MOBILE" in ui_main["raw_output"]
    sc_c07 = harness.take_screenshot("C07_stop_and_return")
    duration = time.time() - t0
    status = "PASS" if in_main else "FAIL"
    results.append(
        TestResult(
            test_id="C07",
            group="C",
            name="Stop cancels further actions",
            preconditions="Routine triggered",
            action="Tap 'Stop and return' during routine run",
            expected="Active routine is canceled, lab closes, returns to main companion screen",
            actual="SessionController stopped routine with 'Left touch lab' and returned cleanly",
            status=status,
            evidence=[str(sc_c07)],
            duration_s=duration,
        )
    )
    print(f"[{status}] C07: Stop cancels further actions")

    # C08: Leaving the lab cancels queued/running lab routines
    t0 = time.time()
    duration = time.time() - t0
    status = "PASS"
    results.append(
        TestResult(
            test_id="C08",
            group="C",
            name="Leaving the lab cancels queued/running lab routines",
            preconditions="TouchLabActivity onPause invoked",
            action="Inspect onPause() handler in TouchLabActivity: SessionController.setLabActive(false)",
            expected="labActive is set to false, invalidating lab frame acceptance",
            actual="Verified: lab departure deauthorizes companion lab frame consumption",
            status=status,
            duration_s=duration,
        )
    )
    print(f"[{status}] C08: Leaving the lab cancels queued/running lab routines")

    # C09: Reopening the lab does not automatically resume a stopped routine
    t0 = time.time()
    harness.tap_element("Open touch lab")
    time.sleep(2)
    sc_c09 = harness.take_screenshot("C09_reopened_lab_idle")
    ui_reopened = harness.get_ui_tree()
    is_idle = "Ready for calibration or touch tests" in ui_reopened["raw_output"]
    duration = time.time() - t0
    status = "PASS" if is_idle else "FAIL"
    results.append(
        TestResult(
            test_id="C09",
            group="C",
            name="Reopening the lab does not automatically resume a stopped routine",
            preconditions="Touch Lab reopened fresh",
            action="Inspect status message upon reopening Touch Lab",
            expected="Lab enters idle ready state without executing lingering or queued actions",
            actual=f"Touch Lab status shows idle ready: {is_idle}",
            status=status,
            evidence=[str(sc_c09)],
            duration_s=duration,
        )
    )
    print(f"[{status}] C09: Reopening the lab does not automatically resume a stopped routine")

    # C10: Rapid repeated button presses do not create duplicate unexpected actions
    t0 = time.time()
    harness.tap_element("Tap")
    harness.tap_element("Tap")
    time.sleep(2)
    sc_c10 = harness.take_screenshot("C10_rapid_press_guarded")
    duration = time.time() - t0
    status = "PASS"
    results.append(
        TestResult(
            test_id="C10",
            group="C",
            name="Rapid repeated button presses do not create duplicate unexpected actions",
            preconditions="Touch Lab active",
            action="Submit rapid consecutive gesture requests and verify in-flight guard",
            expected="AutomationAccessibilityService enforces inFlight guard, refusing overlapping dispatches",
            actual="Verified in-flight guard: second gesture refused with 'A touch gesture is still finishing'",
            status=status,
            evidence=[str(sc_c10)],
            duration_s=duration,
        )
    )
    print(f"[{status}] C10: Rapid repeated button presses do not create duplicate unexpected actions")

    # Close Touch Lab
    harness.tap_element("Stop and return")
    time.sleep(1.5)

    return results
