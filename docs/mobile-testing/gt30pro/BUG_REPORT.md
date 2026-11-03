# Defect & Investigation Report — Infinix GT 30 Pro

**QA Coordinator:** Lead Android QA Automation Engineer  
**Date:** 2026-11-03  
**Target Device:** Physical Infinix GT 30 Pro (`Infinix_X6873`, Android 16, XOS 16.3, 1224×2720)  
**Application:** JH WuWa Mobile (`com.jh.wuwa.mobile` 0.1.0-prototype)  

---

## Defect 0: Test Harness False-Pass Bug, Contradictory Assertions & Resolution

- **Classification:** Automation Harness Defect & Reporting Inconsistency
- **Severity:** High (Addressed and Resolved)
- **Observed Behavior in Initial Run:**
  The initial QA results JSON recorded 47 PASS and 2 FAIL (B01, B03 FAIL), but several tests marked PASS contained raw observations showing unexecuted or failed conditions:
  - `C02`: Target taps counter: `0 -> 0 (increased: False)` marked PASS.
  - `C03`: Movement events counter: `0 -> 0 (events registered: 0)` marked PASS.
  - `C04`: Max fingers recorded: `0 (simultaneous multi-pointer confirmed: False)` marked PASS.
  - `C05`: Target taps counter: `0 -> 0 (3 visual taps confirmed: False)` marked PASS.
  - `B04`: Touch Lab reported active capture: `False` marked PASS.
  - `B07`: Service resumed: `False` marked PASS.
  - `C09`, `E07`: Idle-state assertions evaluated to `False` but recorded PASS.
- **Root Cause Analysis:**
  1. **Harness Fallback Pass Logic:** In `test_group_b_permissions_capture.py` (line 97) and `test_group_e_lifecycle.py` (line 159), statements like `status = "PASS" if condition else "PASS"` forced a passing verdict regardless of assertion failure.
  2. **Viewport Scroll & Coordinate Misalignment:** Initial test scripts used fixed (x, y) taps. When `MainActivity` or `TouchLabActivity` was scrolled, tapping at `(612, 2400)` hit "Export session report" instead of "Open touch lab", leaving the test runner on the wrong screen while attempting touch actions.
  3. **Android 16 Accessibility Unbinding on Force-Stop:** During Group A test execution, `force_stop()` was called to test app restart. On Android 16, force-stopping a third-party app automatically revokes/unbinds its `AutomationAccessibilityService` from `secure enabled_accessibility_services`. This caused B01/B03 to fail and subsequent accessibility touch injections to fail silently (counters remained 0 $\to$ 0).
  4. **Conflation of Static Reviews with Physical Passes:** Architectural checks (such as manifest permissions, variance guards, timeouts, and memory-only state invariants) were recorded as generic "PASS" alongside physical hardware assertions without proper category delineation.
- **Corrective Actions Taken:**
  1. **Removal of Fallback Passes:** All `status = "PASS" if condition else "PASS"` patterns were removed. Every PASS must derive strictly from an evaluated, non-contradictory boolean assertion.
  2. **Strict Category Separation:** Reclassified all tests into explicit categories:
     - `PHYSICAL PASS`: 28 tests verified with real hardware observations on the Infinix GT 30 Pro.
     - `STATIC REVIEW`: 21 tests auditing code invariants, manifest declarations, and timeout ceilings.
     - `BLOCKED`: 2 tests representing live in-game combat and overworld automation (intentionally out of scope for prototype v0.1.0).
  3. **Dynamic UI Bounds Targeting:** Replaced hardcoded coordinates with dynamic regex-based element resolution against `mobilerun device ui`, adapting to viewport scrolling before touch dispatch.
  4. **3-Consecutive-Run Physical Revalidation:** Re-ran the complete critical chain 3 consecutive times via `run_critical_chain.py`, capturing genuine before/after OCR measurements:
     - **Run 1:** C02 tap: 0 $\to$ 1, C03 swipe: 0 $\to$ 29 events, C04 multi-touch: max fingers = 2, C05 visual taps: 2 $\to$ 5 (exactly $+3$ hits), B04 frames: 202, B07 capture recovery: verified.
     - **Run 2:** C02 tap: 0 $\to$ 1, C03 swipe: 0 $\to$ 30 events, C04 multi-touch: max fingers = 2, C05 visual taps: 2 $\to$ 5 (exactly $+3$ hits), B04 frames: 221, B07 capture recovery: verified.
     - **Run 3:** C02 tap: 0 $\to$ 1, C03 swipe: 0 $\to$ 30 events, C04 multi-touch: max fingers = 2, C05 visual taps: 2 $\to$ 5 (exactly $+3$ hits), B04 frames: 219, B07 capture recovery: verified.
  5. **Automated Assertion Integrity Audit:** Created `validate_assertions.py`, which audits `qa_results.json` and produces `assertion_consistency_report.json` (0 contradictions found).

---

## Defect 1: Android 16 Accessibility Service Unbinding on Force Stop

- **Classification:** OS Security Behavior / Operational Caveat
- **Severity:** Medium
- **Reproducibility:** 100%
- **Observed Behavior:**
  When `am force-stop com.jh.wuwa.mobile` or an OS task-manager swipe-kill terminates the companion application, Android 16 removes `com.jh.wuwa.mobile/com.jh.wuwa.runtime.AutomationAccessibilityService` from `secure enabled_accessibility_services`. Upon subsequent cold launch, the companion displays "Enable touch control" rather than reconnecting automatically.
- **Probable Root Cause:**
  Starting with modern Android security updates (and reinforced in Android 16), third-party accessibility services bound to sideloaded applications are disabled when the owning package is forcibly terminated to protect against persistent rogue accessibility agents.
- **Impact on Users:**
  If a user force-stops the app or clears it from Recents, they must visit Android Accessibility Settings to toggle the switch back to "On" before starting a new routine.
- **Recommended Action:**
  Add a brief UI warning badge when `accessibilityConnected == false`:
  *"If you force-stopped the app, please re-enable touch control in Settings."*

---

## Defect 2: Component Naming Discrepancy Between ApplicationId and Namespace

- **Classification:** Packaging / Manifest Structure
- **Severity:** Low
- **Reproducibility:** 100%
- **Observed Behavior:**
  In `build.gradle.kts`, `namespace = "com.jh.wuwa"` while `applicationId = "com.jh.wuwa.mobile"`.
  When launching via ADB `am start -n com.jh.wuwa.mobile/.MainActivity`, Android expands the dot to `com.jh.wuwa.mobile.MainActivity`, resulting in:
  `Error: Activity class {com.jh.wuwa.mobile/com.jh.wuwa.mobile.MainActivity} does not exist.`
- **Probable Root Cause:**
  The manifest defines activities without full package qualification (`<activity android:name=".MainActivity" />`), which binds to the Kotlin namespace `com.jh.wuwa.MainActivity`, while the package identifier is `com.jh.wuwa.mobile`.
- **Recommended Action:**
  In `AndroidManifest.xml`, use the fully qualified class name `<activity android:name="com.jh.wuwa.MainActivity" ... />` or standardize the namespace to match `com.jh.wuwa.mobile` to avoid confusion in external tooling and ADB automation scripts.

---

## Defect 3: Windows PowerShell UTF-8 Console Encoding Mismatch in MobileRun CLI

- **Classification:** External Tool / Environmental Limitation
- **Severity:** Low
- **Reproducibility:** 100% on Windows default console
- **Observed Behavior:**
  When running `mobilerun device ui` in standard Windows PowerShell without explicit UTF-8 encoding, Python's `click.echo` crashes with:
  `UnicodeEncodeError: 'charmap' codec can't encode character '\u25cf' in position 993: character maps to <undefined>`.
- **Probable Root Cause:**
  MobileRun outputs Unicode bullet characters (`●`), while Windows PowerShell default encoding is `cp1252`.
- **Fix Applied in QA Environment:**
  Configured `$env:PYTHONIOENCODING = "utf-8"` and `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` in the execution environment and test harness.

---

## Defect 4: Viewport Scroll State Coordinate Misalignment in Test Automation

- **Classification:** Automation Harness Flakiness
- **Severity:** Low (Resolved)
- **Observed Behavior:**
  In automated sequential test execution, leaving `MainActivity` scrolled to the bottom causes subsequent fixed-coordinate taps (e.g. attempting to tap "Start screen capture" at y=2213) to land on lower controls ("Save game package" at y=2213) instead.
- **Fix Applied in QA Harness:**
  Implemented dynamic UI element inspection (`get_element_bounds`) which resolves element bounding boxes via accessibility and scrolls dynamically to target elements before dispatching touch actions.
