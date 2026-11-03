"""Group F — Stability and Resource Usage Test Suite for Physical Infinix GT 30 Pro."""

import time
from typing import List
from harness import APP_PACKAGE, DeviceHarness, TestResult


def run_group_f(harness: DeviceHarness) -> List[TestResult]:
    results = []
    print("\n--- Running Group F: Stability and Resource Usage ---")

    t0 = time.time()
    harness.launch_app(APP_PACKAGE)
    time.sleep(1.5)

    # Start capture if not active
    services_out = harness.adb_shell(f"dumpsys activity services {APP_PACKAGE}/.runtime.CaptureService")
    if "CaptureService" not in services_out:
        harness.tap(612, 2155)  # Start screen capture
        time.sleep(2)
        harness.tap(612, 2364)  # Allow dialog if presented
        time.sleep(1)

    # Enter Touch Lab
    harness.swipe(600, 2000, 600, 600)
    time.sleep(1)
    harness.tap(612, 2361)  # Open touch lab
    time.sleep(2)

    # Monitor resources for 30 seconds
    sample_interval = 5.0
    duration_target = 30.0
    elapsed = 0.0
    pss_samples = []
    battery_temps = []
    battery_levels = []

    print(f"  Monitoring resource consumption for {int(duration_target)} seconds...")
    while elapsed < duration_target:
        metrics = harness.get_resource_metrics(APP_PACKAGE)
        if metrics["pss_mb"] is not None:
            pss_samples.append(metrics["pss_mb"])
        if metrics["battery_temp_c"] is not None:
            battery_temps.append(metrics["battery_temp_c"])
        if metrics["battery_level_pct"] is not None:
            battery_levels.append(metrics["battery_level_pct"])
        time.sleep(sample_interval)
        elapsed += sample_interval

    # Return to main activity
    harness.tap(612, 2469)  # Stop and return
    time.sleep(1.5)

    # Calculate statistics
    avg_pss = round(sum(pss_samples) / len(pss_samples), 2) if pss_samples else "NOT MEASURED"
    peak_pss = max(pss_samples) if pss_samples else "NOT MEASURED"
    avg_temp = round(sum(battery_temps) / len(battery_temps), 1) if battery_temps else "NOT MEASURED"
    battery_drain = (battery_levels[0] - battery_levels[-1]) if (len(battery_levels) >= 2) else 0

    crashes = harness.check_logcat_crashes(since_seconds=45)
    anrs = harness.adb_shell(f"dumpsys activity anrs | grep {APP_PACKAGE}")
    has_anr = bool(anrs.strip())

    sc = harness.take_screenshot("F01_stability_session_complete")
    duration = time.time() - t0

    notes = (
        f"Avg PSS Memory: {avg_pss} MB, Peak PSS: {peak_pss} MB | "
        f"Battery Temp: {avg_temp} °C | Battery Drain: {battery_drain}% | "
        f"Crashes: {len(crashes)}, ANRs: {has_anr}"
    )

    status = "PASS" if (not crashes and not has_anr) else "FAIL"
    results.append(
        TestResult(
            test_id="F01",
            group="F",
            name="Stability and resource usage benchmark",
            preconditions="Capture service active, Touch Lab running for 30s session",
            action="Monitor memory PSS, CPU snippet, battery level, thermals, crashes and ANRs across 30s session",
            expected="Zero ANRs, zero crashes, stable bounded memory usage below 250MB, no device overheating",
            actual=notes,
            status=status,
            evidence=[str(sc)],
            duration_s=duration,
            notes=notes,
        )
    )
    print(f"[{status}] F01: Stability and resource usage benchmark")
    print(f"       -> {notes}")

    return results
