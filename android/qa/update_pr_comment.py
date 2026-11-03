"""Update PR #3 comment with corrected evidence and qualified verdict."""

import json
import subprocess
from pathlib import Path

COMMENT_ID = 6600181619
REPO = "jonhue1403/jh-wuthering-waves"

comment_body = """### Corrected Physical Device QA Validation Report — Infinix GT 30 Pro

**Evaluation Date:** 2026-11-03  
**Status:** Feasibility Prototype Validated on Physical Hardware (Critical Gate Passed, Draft PR Maintained)  
**Target Device:** Infinix GT 30 Pro (`Infinix_X6873`, Android 16 / API 36, XOS 16.3, 1224×2720 @ 480dpi)  
**Prototype Evaluated:** `com.jh.wuwa.mobile` (v0.1.0-prototype, PR #3)  
**Testing Branch:** `qa/android-gt30pro-validation` (commit `ff967d4`)  

---

### 1. Retraction and Qualification of Initial Test Claims

Following independent QA review, the initial validation report has been thoroughly audited, reconciled, and corrected:
- **Retracted False Passes:** The initial report contained a harness logic defect (`status = "PASS" if condition else "PASS"`) and viewport coordinate misalignment that caused several tests to record PASS despite raw observations reading `0 -> 0` (C02, C03, C04, C05). Those false passes are retracted.
- **Retracted Latency Claim:** The previous claim of "< 50ms display capture latency" was an unmeasured engineering estimate. End-to-end optical latency was not verified with high-speed camera hardware and is retracted.
- **Qualified Power & Stability:** A 0% battery delta across a 30-second benchmark reflects Android integer battery API granularity, not zero power consumption. A 30-second benchmark validates initial runtime memory bounds (83.2 MB PSS), not multi-hour stability under 3D GPU gaming load.
- **Host OCR Clarification:** OpenVINO OCR was executed on the Windows development host to assert Canvas metrics; on-device inference in the Android companion uses native Kotlin `TemplateMatcher`.
- **Privacy Sanitization:** Physical device hardware serials and USB PnP instance IDs have been redacted from all public reports, scripts, and committed JSON artifacts.

---

### 2. Physical Hardware Revalidation (3 Consecutive Critical Runs)

The critical on-device chain was executed across **three consecutive, uninterrupted runs** on the connected Infinix GT 30 Pro via `android/qa/run_critical_chain.py`. Every touch gesture and visual hit was empirically measured via OCR with non-zero before/after increments:

| Step / Assertion | Target Condition | Run 1 Observed | Run 2 Observed | Run 3 Observed | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Accessibility Binding** | Bound in secure settings | Bound | Bound | Bound | **PHYSICAL PASS** |
| **CaptureService State** | Running (`types=0x00000020`) | Active | Active | Active | **PHYSICAL PASS** |
| **Touch Lab Entry** | Dynamic bounds resolution | Entered (`True`) | Entered (`True`) | Entered (`True`) | **PHYSICAL PASS** |
| **Baseline OCR** | Metrics parsed | Taps=0, Fig=0, Mov=0 | Taps=0, Fig=0, Mov=0 | Taps=0, Fig=0, Mov=0 | **PHYSICAL PASS** |
| **C02 Single Tap** | Target taps counter increases | `0 -> 1` | `0 -> 1` | `0 -> 1` | **PHYSICAL PASS** |
| **C03 Swipe** | Movement events increase | `0 -> 29` | `0 -> 30` | `0 -> 30` | **PHYSICAL PASS** |
| **C04 Two Fingers** | Max simultaneous fingers >= 2 | `max_fingers = 2` | `max_fingers = 2` | `max_fingers = 2` | **PHYSICAL PASS** |
| **C05 3 Visual Taps** | Target taps increases by exactly +3 | `2 -> 5` (+3 hits) | `2 -> 5` (+3 hits) | `2 -> 5` (+3 hits) | **PHYSICAL PASS** |
| **C07 Stop & Return** | Return cleanly to main screen | `True` | `True` | `True` | **PHYSICAL PASS** |
| **B04 Advancing Frames** | Frame counter advances (>0) | `202 frames` | `221 frames` | `219 frames` | **PHYSICAL PASS** |
| **B05/B07 Recovery** | Clean stop -> restart -> consent | `stopped=True, resumed=True` | `stopped=True, resumed=True` | `stopped=True, resumed=True` | **PHYSICAL PASS** |
| **Run Overall Verdict** | All 10 assertions verified | **PASSED** | **PASSED** | **PASSED** | **GATE PASSED** |

---

### 3. Comprehensive Suite Status (51 Tests Audited)

All test cases have been cleanly categorized and audited with zero contradictions (`assertion_consistency_report.json`):
- **PHYSICAL PASS (28 Tests):** Display resolution, responsiveness, accessibility touch dispatch, MediaProjection active capture, frame delivery, swipe/multi-touch/visual tap sequences, session return, clean restart, and game package detection.
- **STATIC REVIEW (21 Tests):** Code invariants, MIN_VARIANCE contrast rejection, 60s timeout ceilings, 1000ms frame freshness guards, KeyguardManager lock checks, and session report privacy audits (zero screenshots/tokens).
- **BLOCKED / NOT RUN (2 Tests):** Live in-game combat loops (H01) and overworld daily quest farming (H02) are intentionally blocked and out of scope for the v0.1.0 prototype.
- **PHYSICAL FAIL:** 0
- **Contradictory Observations:** 0

---

### 4. Release Decision: PR #3 Remains in Draft

**Recommendation:** PR #3 **must remain in draft and not be merged at this stage**.
1. **Prototype Scope:** The prototype successfully validates the technical feasibility of MediaProjection capture and accessibility touch injection on physical hardware.
2. **Unverified Gameplay:** Live in-game combat and multi-hour gaming endurance under 3D GPU load have not been tested.
3. **Android 16 Operational Caveat:** When the app is force-stopped or swiped away from Recents, Android 16 automatically revokes the accessibility service. A user-facing warning badge and deep link must be implemented prior to merge.

**Corrected Evidence References:**
- [TEST_RESULTS.md](https://github.com/jonhue1403/jh-wuthering-waves/blob/qa/android-gt30pro-validation/docs/mobile-testing/gt30pro/TEST_RESULTS.md)
- [BUG_REPORT.md](https://github.com/jonhue1403/jh-wuthering-waves/blob/qa/android-gt30pro-validation/docs/mobile-testing/gt30pro/BUG_REPORT.md)
- [QA_SUMMARY.md](https://github.com/jonhue1403/jh-wuthering-waves/blob/qa/android-gt30pro-validation/docs/mobile-testing/gt30pro/QA_SUMMARY.md)
- [critical_chain_results.json](https://github.com/jonhue1403/jh-wuthering-waves/blob/qa/android-gt30pro-validation/android/qa/critical_chain_results.json)
- [assertion_consistency_report.json](https://github.com/jonhue1403/jh-wuthering-waves/blob/qa/android-gt30pro-validation/android/qa/assertion_consistency_report.json)
"""

payload_file = Path("comment_payload.json")
with open(payload_file, "w", encoding="utf-8") as f:
    json.dump({"body": comment_body}, f, ensure_ascii=False)

cmd = [
    "gh", "api", "-X", "PATCH",
    f"repos/{REPO}/issues/comments/{COMMENT_ID}",
    "--input", str(payload_file)
]

res = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
print("Status code:", res.returncode)
if res.returncode == 0:
    print("Successfully updated PR #3 comment!")
else:
    print("Error updating PR #3 comment:", res.stderr)

if payload_file.exists():
    payload_file.unlink(missing_ok=True)
