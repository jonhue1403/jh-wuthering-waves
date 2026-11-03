"""Master QA Execution Suite for JH WuWa Android Prototype on Infinix GT 30 Pro."""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

from harness import DeviceHarness
from test_group_a_installation_ui import run_group_a
from test_group_b_permissions_capture import run_group_b
from test_group_c_touch_lab import run_group_c
from test_group_d_vision import run_group_d
from test_group_e_lifecycle import run_group_e
from test_group_f_stability import run_group_f
from test_phase8_game import run_phase_8


def main():
    print("=" * 70)
    print("JH WUWA ANDROID PHYSICAL DEVICE QA AUTOMATION SUITE")
    print(f"Execution Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    harness = DeviceHarness()
    device_info = harness.get_device_info()
    print("\n[Target Device Identification]")
    for k, v in device_info.items():
        print(f"  {k:20s}: {v}")

    all_results = []

    # Run groups sequentially
    t_start = time.time()
    all_results.extend(run_group_a(harness))
    all_results.extend(run_group_b(harness))
    all_results.extend(run_group_c(harness))
    all_results.extend(run_group_d(harness))
    all_results.extend(run_group_e(harness))
    all_results.extend(run_group_f(harness))
    all_results.extend(run_phase_8(harness))
    total_time = time.time() - t_start

    # Summary
    pass_count = sum(1 for r in all_results if r.status == "PASS")
    fail_count = sum(1 for r in all_results if r.status == "FAIL")
    blocked_count = sum(1 for r in all_results if r.status == "BLOCKED")
    not_run_count = sum(1 for r in all_results if r.status == "NOT RUN")
    total_count = len(all_results)

    print("\n" + "=" * 70)
    print(f"EXECUTION SUMMARY: {total_count} Tests Executed in {total_time:.2f}s")
    print(f"  PASS    : {pass_count}")
    print(f"  FAIL    : {fail_count}")
    print(f"  BLOCKED : {blocked_count}")
    print(f"  NOT RUN : {not_run_count}")
    print("=" * 70)

    # Save JSON results
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "device_info": device_info,
        "total_duration_s": total_time,
        "summary": {
            "total": total_count,
            "pass": pass_count,
            "fail": fail_count,
            "blocked": blocked_count,
            "not_run": not_run_count,
        },
        "results": [r.to_dict() for r in all_results],
    }

    out_file = Path(__file__).resolve().parent / "qa_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"\nDetailed JSON report written to: {out_file}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
