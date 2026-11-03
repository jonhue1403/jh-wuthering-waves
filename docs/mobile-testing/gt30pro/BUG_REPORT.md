# Defect & Investigation Report — Infinix GT 30 Pro

**QA Coordinator:** Lead Android QA Automation Engineer  
**Date:** 2026-11-03  
**Target:** Infinix GT 30 Pro (Android 16, XOS 16.3)  
**Application:** JH WuWa Mobile (`com.jh.wuwa.mobile` 0.1.0-prototype)  

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
- **Severity:** Low
- **Observed Behavior:**
  In automated sequential test execution, leaving `MainActivity` scrolled to the bottom causes subsequent fixed-coordinate taps (e.g. attempting to tap "Start screen capture" at y=2213) to land on lower controls ("Save game package" at y=2213) instead.
- **Fix Applied in QA Harness:**
  Implemented dynamic UI element inspection (`find_element_bounds`) which resolves element bounding boxes via accessibility and scrolls dynamically to target elements before dispatching touch actions.
