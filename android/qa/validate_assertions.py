"""Assertion Consistency and Integrity Validator for Android Physical QA."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List

QA_DIR = Path(__file__).resolve().parent
RESULTS_FILE = QA_DIR / "qa_results.json"
CRITICAL_CHAIN_FILE = QA_DIR / "critical_chain_results.json"
OUTPUT_REPORT = QA_DIR / "assertion_consistency_report.json"

FORBIDDEN_SERIALS = ["143382554J102386"]
CONTRADICTION_PATTERNS = [
    r"increased:\s*False",
    r"confirmed:\s*False",
    r"0\s*->\s*0",
    r"active:\s*False",
    r"resumed:\s*False",
    r"bound:\s*False",
    r"shows connected:\s*False",
    r"shows idle ready:\s*False",
    r"after launch is idle:\s*False",
]


def audit_results() -> Dict[str, Any]:
    issues: List[Dict[str, Any]] = []

    # 1. Audit critical chain results
    if not CRITICAL_CHAIN_FILE.exists():
        issues.append({"scope": "critical_chain", "issue": "critical_chain_results.json does not exist"})
        critical_summary = {}
    else:
        with open(CRITICAL_CHAIN_FILE, "r", encoding="utf-8") as f:
            critical_summary = json.load(f)

        if not critical_summary.get("all_three_runs_passed"):
            issues.append({"scope": "critical_chain", "issue": "Not all 3 consecutive critical runs passed"})

        runs = critical_summary.get("runs", [])
        if len(runs) != 3:
            issues.append({"scope": "critical_chain", "issue": f"Expected 3 consecutive runs, found {len(runs)}"})

        for r in runs:
            idx = r.get("run_index")
            assertions = r.get("assertions", {})
            # Verify C02
            c02 = assertions.get("C02_single_tap", {})
            if not c02.get("passed") or "target_taps = 0" in c02.get("actual", ""):
                issues.append({"scope": f"critical_chain_run_{idx}", "test": "C02", "issue": "C02 tap did not increase"})
            # Verify C03
            c03 = assertions.get("C03_swipe", {})
            if not c03.get("passed") or "move_events = 0" in c03.get("actual", ""):
                issues.append({"scope": f"critical_chain_run_{idx}", "test": "C03", "issue": "C03 move events did not increase"})
            # Verify C04
            c04 = assertions.get("C04_two_fingers", {})
            if not c04.get("passed") or "max_fingers = 0" in c04.get("actual", ""):
                issues.append({"scope": f"critical_chain_run_{idx}", "test": "C04", "issue": "C04 max_fingers < 2"})
            # Verify C05
            c05 = assertions.get("C05_three_visual_taps", {})
            if not c05.get("passed"):
                issues.append({"scope": f"critical_chain_run_{idx}", "test": "C05", "issue": "C05 3 visual taps failed"})
            # Verify B04
            b04 = assertions.get("B04_frames_advancing", {})
            if not b04.get("passed") or "frame_count = 0" in b04.get("actual", ""):
                issues.append({"scope": f"critical_chain_run_{idx}", "test": "B04", "issue": "B04 frames not advancing"})
            # Verify B07
            b07 = assertions.get("B07_capture_recovery", {})
            if not b07.get("passed"):
                issues.append({"scope": f"critical_chain_run_{idx}", "test": "B07", "issue": "B07 capture recovery failed"})

    # 2. Audit qa_results.json
    if not RESULTS_FILE.exists():
        issues.append({"scope": "qa_results", "issue": "qa_results.json does not exist"})
        qa_data = {}
    else:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            raw_text = f.read()
            qa_data = json.loads(raw_text)

        # Check for serial leaks in JSON
        for s in FORBIDDEN_SERIALS:
            if s in raw_text:
                issues.append({"scope": "privacy", "issue": f"Forbidden hardware serial {s} exposed in qa_results.json"})

        # Check each test result for contradictions and classifications
        results_list = qa_data.get("results", [])
        for item in results_list:
            tid = item.get("test_id")
            status = item.get("status")
            category = item.get("category", "")
            actual = str(item.get("actual", ""))

            # Contradiction check: PASS with failing observation
            if status == "PASS" or category == "PHYSICAL PASS":
                for pattern in CONTRADICTION_PATTERNS:
                    if re.search(pattern, actual, re.IGNORECASE):
                        issues.append({
                            "scope": "contradiction",
                            "test_id": tid,
                            "issue": f"Test {tid} marked PASS but actual observation contains failing pattern: '{pattern}' in '{actual}'"
                        })

            # Check relative evidence paths
            for ev in item.get("evidence", []):
                if ":\\" in ev or ":/" in ev:
                    issues.append({
                        "scope": "hygiene",
                        "test_id": tid,
                        "issue": f"Evidence path is absolute instead of sanitized relative: {ev}"
                    })

    consistent = (len(issues) == 0)
    report = {
        "timestamp": qa_data.get("timestamp"),
        "is_consistent": consistent,
        "issue_count": len(issues),
        "issues": issues,
        "critical_chain_validated_3_runs": critical_summary.get("all_three_runs_passed", False),
        "total_tests_audited": len(qa_data.get("results", [])),
    }

    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Assertion Consistency Audit Complete: {'CONSISTENT' if consistent else 'INCONSISTENT'}")
    print(f"Total Issues Found: {len(issues)}")
    if issues:
        for iss in issues[:10]:
            print(f"  - [{iss.get('scope')}] {iss.get('issue')}")
    return report


if __name__ == "__main__":
    report = audit_results()
    exit(0 if report["is_consistent"] else 1)
