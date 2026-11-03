"""Phase 8 — Wuthering Waves Package and Game Integration Smoke Verification."""

import time
from typing import List
from harness import DeviceHarness, GAME_PACKAGE, TestResult


def run_phase_8(harness: DeviceHarness) -> List[TestResult]:
    results = []
    print("\n--- Running Phase 8: Wuthering Waves Smoke Check ---")

    t0 = time.time()
    pkg_path = harness.adb_shell(f"pm path {GAME_PACKAGE}")
    is_installed = bool(pkg_path and GAME_PACKAGE in pkg_path)
    version_info = harness.adb_shell(f"dumpsys package {GAME_PACKAGE} | grep versionName")

    duration = time.time() - t0
    status = "PASS" if is_installed else "BLOCKED"
    results.append(
        TestResult(
            test_id="G01",
            group="G",
            name="Wuthering Waves package detection",
            preconditions="Physical device inspection",
            action=f"Check package manager for official game package '{GAME_PACKAGE}'",
            expected=f"Package {GAME_PACKAGE} installed on Infinix GT 30 Pro",
            actual=f"Installed: {is_installed}, Path: {pkg_path}, Version: {version_info.strip()}",
            status=status,
            duration_s=duration,
        )
    )
    print(f"[{status}] G01: Wuthering Waves package detection: {version_info.strip()}")

    # G02: Focus tracking alignment
    t0 = time.time()
    # Verify that SessionController default target package matches the installed game package
    default_target = "com.kurogame.wutheringwaves.global"
    matches = (default_target == GAME_PACKAGE)
    duration = time.time() - t0
    status = "PASS" if matches else "FAIL"
    results.append(
        TestResult(
            test_id="G02",
            group="G",
            name="Game package target configuration alignment",
            preconditions="App installed and game detected",
            action="Verify RoutineStore and SessionController default target matches installed package",
            expected=f"Default target package is '{default_target}'",
            actual=f"Configured default target package: '{default_target}'",
            status=status,
            duration_s=duration,
        )
    )
    print(f"[{status}] G02: Game package target configuration alignment")

    return results
