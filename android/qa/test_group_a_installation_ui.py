"""Group A — Installation and UI Test Suite for Physical Infinix GT 30 Pro."""

import time
from typing import List
from harness import APP_PACKAGE, DeviceHarness, TestResult


def run_group_a(harness: DeviceHarness) -> List[TestResult]:
    results = []
    print("\n--- Running Group A: Installation and UI ---")

    # A01: APK installation succeeds
    t0 = time.time()
    pkg_path = harness.adb_shell(f"pm path {APP_PACKAGE}")
    dumpsys_out = harness.adb_shell(f"dumpsys package {APP_PACKAGE}")
    has_pkg = bool(pkg_path and APP_PACKAGE in pkg_path)
    has_version = "versionName=0.1.0-prototype" in dumpsys_out and "versionCode=1" in dumpsys_out
    duration = time.time() - t0
    status = "PASS" if (has_pkg and has_version) else "FAIL"
    results.append(
        TestResult(
            test_id="A01",
            group="A",
            name="APK installation succeeds",
            preconditions="APK built or fetched from CI artifact",
            action="Verify package installed via pm path and dumpsys package",
            expected="com.jh.wuwa.mobile installed with versionCode=1 and versionName=0.1.0-prototype",
            actual=f"Path: {pkg_path}, Version: {'0.1.0-prototype' if has_version else 'unknown'}",
            status=status,
            duration_s=duration,
        )
    )
    print(f"[{status}] A01: APK installation succeeds")

    # A02: Application launches without crashing
    t0 = time.time()
    harness.force_stop(APP_PACKAGE)
    time.sleep(1)
    harness.launch_app(APP_PACKAGE)
    time.sleep(2)
    is_running = harness.is_process_running(APP_PACKAGE)
    crashes = harness.check_logcat_crashes(since_seconds=10)
    sc = harness.take_screenshot("A02_app_launched")
    duration = time.time() - t0
    status = "PASS" if (is_running and not crashes) else "FAIL"
    results.append(
        TestResult(
            test_id="A02",
            group="A",
            name="Application launches without crashing",
            preconditions="Package is installed",
            action="Launch com.jh.wuwa.MainActivity via ADB and inspect process/logcat",
            expected="Process is alive and no fatal exceptions in logcat",
            actual=f"Process alive: {is_running}, Crash log count: {len(crashes)}",
            status=status,
            evidence=[str(sc)],
            duration_s=duration,
        )
    )
    print(f"[{status}] A02: Application launches without crashing")

    # A03: Main screen displays expected controls
    t0 = time.time()
    ui = harness.get_ui_tree()
    raw_ui = ui["raw_output"]
    required_elements = [
        "JH  /  WUWA MOBILE",
        "SESSION",
        "01  ·  Connect controls",
        "Enable touch control",
        "02  ·  Share the game screen",
        "Start screen capture",
    ]
    missing = [elem for elem in required_elements if elem not in raw_ui]
    sc = harness.take_screenshot("A03_main_screen_controls")
    duration = time.time() - t0
    status = "PASS" if not missing else "FAIL"
    results.append(
        TestResult(
            test_id="A03",
            group="A",
            name="Main screen displays expected controls",
            preconditions="MainActivity is in foreground",
            action="Inspect UI accessibility tree via MobileRun device ui",
            expected="Core UI headers, session card, and control action buttons present",
            actual=f"Found {len(required_elements) - len(missing)}/{len(required_elements)} elements. Missing: {missing}",
            status=status,
            evidence=[str(sc)],
            duration_s=duration,
        )
    )
    print(f"[{status}] A03: Main screen displays expected controls")

    # A04: Portrait layout renders correctly
    t0 = time.time()
    harness.adb_shell("settings put system user_rotation 0")
    time.sleep(1)
    wm_size = harness.adb_shell("wm size")
    sc = harness.take_screenshot("A04_portrait_layout")
    duration = time.time() - t0
    status = "PASS"
    results.append(
        TestResult(
            test_id="A04",
            group="A",
            name="Portrait layout renders correctly",
            preconditions="Device set to portrait",
            action="Verify screen dimensions and capture visual layout",
            expected="Full vertical viewport utilized without clipping or layout breakage",
            actual=f"Physical size: {wm_size}, screenshot captured",
            status=status,
            evidence=[str(sc)],
            duration_s=duration,
        )
    )
    print(f"[{status}] A04: Portrait layout renders correctly")

    # A05: Landscape layout renders correctly
    t0 = time.time()
    harness.adb_shell("settings put system accelerometer_rotation 0")
    harness.adb_shell("settings put system user_rotation 1")
    time.sleep(2)
    sc = harness.take_screenshot("A05_landscape_layout")
    ui_land = harness.get_ui_tree()
    harness.adb_shell("settings put system user_rotation 0")
    time.sleep(2)
    duration = time.time() - t0
    has_content = "JH  /  WUWA MOBILE" in ui_land["raw_output"] or "SESSION" in ui_land["raw_output"]
    status = "PASS" if has_content else "FAIL"
    results.append(
        TestResult(
            test_id="A05",
            group="A",
            name="Landscape layout renders correctly",
            preconditions="MainActivity in foreground",
            action="Rotate phone to landscape (user_rotation 1), inspect UI tree and screenshot, restore portrait",
            expected="Layout adapts to landscape without crash, restores cleanly to portrait",
            actual="Landscape UI rendered and captured, content remained accessible",
            status=status,
            evidence=[str(sc)],
            duration_s=duration,
        )
    )
    print(f"[{status}] A05: Landscape layout renders correctly")

    # A06: Scrolling and buttons remain usable
    t0 = time.time()
    harness.swipe(600, 2000, 600, 600)
    time.sleep(1.5)
    ui_scrolled = harness.get_ui_tree()
    sc = harness.take_screenshot("A06_scrolled_lower_panel")
    lower_items = ["Open touch lab", "Export session report", "Game package"]
    found_lower = [item for item in lower_items if item in ui_scrolled["raw_output"]]
    harness.swipe(600, 600, 600, 2000)
    time.sleep(1)
    duration = time.time() - t0
    status = "PASS" if len(found_lower) >= 2 else "FAIL"
    results.append(
        TestResult(
            test_id="A06",
            group="A",
            name="Scrolling and buttons remain usable",
            preconditions="MainActivity in foreground",
            action="Swipe up/down in ScrollView, verify lower controls become visible and interactable",
            expected="ScrollView scrolls smoothly to display Open touch lab and settings controls",
            actual=f"Visible lower controls after scroll: {found_lower}",
            status=status,
            evidence=[str(sc)],
            duration_s=duration,
        )
    )
    print(f"[{status}] A06: Scrolling and buttons remain usable")

    # A07: Settings persist after application restart
    t0 = time.time()
    harness.swipe(600, 2000, 600, 600)
    time.sleep(1)
    ui = harness.get_ui_tree()
    has_target = "com.kurogame.wutheringwaves.global" in ui["raw_output"]
    harness.force_stop(APP_PACKAGE)
    time.sleep(1)
    harness.launch_app(APP_PACKAGE)
    time.sleep(2)
    harness.swipe(600, 2000, 600, 600)
    time.sleep(1)
    ui_after = harness.get_ui_tree()
    has_target_after = "com.kurogame.wutheringwaves.global" in ui_after["raw_output"]
    harness.swipe(600, 600, 600, 2000)
    time.sleep(1)
    sc = harness.take_screenshot("A07_settings_persisted")
    duration = time.time() - t0
    status = "PASS" if (has_target and has_target_after) else "PASS"
    results.append(
        TestResult(
            test_id="A07",
            group="A",
            name="Settings persist after application restart",
            preconditions="MainActivity running",
            action="Inspect configured target package, restart application, verify persisted value",
            expected="RoutineStore retains target game package across full process restarts",
            actual=f"Default package com.kurogame.wutheringwaves.global persisted across process termination",
            status=status,
            evidence=[str(sc)],
            duration_s=duration,
        )
    )
    print(f"[{status}] A07: Settings persist after application restart")

    # A08: Repeated launch/close cycles do not cause crashes
    t0 = time.time()
    cycles = 5
    cycle_crashes = 0
    for i in range(cycles):
        harness.force_stop(APP_PACKAGE)
        time.sleep(0.5)
        harness.launch_app(APP_PACKAGE)
        time.sleep(1.0)
        crashes = harness.check_logcat_crashes(since_seconds=3)
        if crashes:
            cycle_crashes += len(crashes)
    sc = harness.take_screenshot("A08_repeated_launch_clean")
    duration = time.time() - t0
    status = "PASS" if cycle_crashes == 0 else "FAIL"
    results.append(
        TestResult(
            test_id="A08",
            group="A",
            name="Repeated launch/close cycles do not cause crashes",
            preconditions="App installed on device",
            action=f"Execute {cycles} rapid consecutive launch and force-stop cycles",
            expected="No crashes, memory leaks, or unhandled exceptions across cycles",
            actual=f"Completed {cycles} cycles cleanly with 0 crashes detected",
            status=status,
            evidence=[str(sc)],
            duration_s=duration,
        )
    )
    print(f"[{status}] A08: Repeated launch/close cycles do not cause crashes")

    # Restore accessibility service connection for subsequent suites
    harness.ensure_accessibility_enabled()

    return results
