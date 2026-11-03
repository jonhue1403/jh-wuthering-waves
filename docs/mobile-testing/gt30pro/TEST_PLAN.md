# Physical Device Test Plan — Infinix GT 30 Pro

**Component:** JH WuWa Mobile (`com.jh.wuwa.mobile` 0.1.0-prototype)  
**Execution Context:** Physical Device On-Board Validation  
**Target:** Infinix GT 30 Pro (Android 16, XOS 16.3, 1224×2720)  

---

## 1. Test Matrix Overview

The test plan evaluates the Android on-device prototype across seven structural groups:

| Group | Category | Objectives |
| :--- | :--- | :--- |
| **Group A** | Installation & UI | Package deployment, startup crash immunity, viewport scaling, orientation handling, settings persistence, process cycling. |
| **Group B** | Permissions & Capture | Accessibility binding, notification runtime approval, MediaProjection foreground service, frame reception, rotation invalidation, unauthorized dispatch guards. |
| **Group C** | Touch Lab | Native canvas touch tracking, single tap dispatch, swipe stroke generation, multi-touch dual pointer dispatch, 3-cycle image-conditioned visual taps, cancellation and lifecycle safety. |
| **Group D** | Image Recognition | Grayscale conversion, variance thresholding, high-contrast target calibration, normalized coordinate bounding, live template correlation, stale frame suppression. |
| **Group E** | Lifecycle & Recovery | Background/foreground cycling, screen lock suppression, service unbind recovery, process restart state purity, JSON diagnostic export audit. |
| **Group F** | Stability & Resources | 30-second sustained capture benchmark, memory PSS overhead, thermal behavior, battery drain, crash and ANR zero-tolerance check. |
| **Group G** | Game Integration | Identification of installed game package (`com.kurogame.wutheringwaves.global`), launch intent validation, default target alignment. |

---

## 2. Test Execution Matrix

### Group A — Installation & UI
- **A01: APK installation succeeds** — Verify `pm path com.jh.wuwa.mobile` and version properties (`0.1.0-prototype`).
- **A02: Application launches without crashing** — Launch `MainActivity` via intent, confirm PID alive and zero fatal exceptions in logcat.
- **A03: Main screen displays expected controls** — Inspect accessibility hierarchy for session status, control connect buttons, capture start/stop, calibration triggers.
- **A04: Portrait layout renders correctly** — Verify display bounds (1224×2720) and render layout without viewport truncation.
- **A05: Landscape layout renders correctly** — Rotate device to landscape (`user_rotation 1`), verify UI adaptation and return to portrait.
- **A06: Scrolling and buttons remain usable** — Swipe down ScrollView to uncover Touch Lab entry, session export, and game package settings.
- **A07: Settings persist after application restart** — Verify `RoutineStore` persists target package configuration across complete process death.
- **A08: Repeated launch/close cycles do not cause crashes** — Five consecutive rapid launch/kill cycles to detect initialization memory leaks or ANRs.

### Group B — Permissions & Capture
- **B01: Accessibility service setup** — Confirm `AutomationAccessibilityService` is active in `secure enabled_accessibility_services` and UI reflects connected status.
- **B02: Screen-capture permission request** — Verify `FOREGROUND_SERVICE_MEDIA_PROJECTION` declaration in AndroidManifest and capture intent dispatch.
- **B03: Capture starts after user approval** — Confirm `CaptureService` runs as active foreground service with type `mediaProjection` upon approval.
- **B04: Frame counter increases while capturing permitted content** — Verify frame delivery to `SessionController` while active in permitted package.
- **B05: Capture stops after revocation** — Tap "Stop screen capture" and confirm `CaptureService` termination and UI state transition.
- **B06: Switching orientation invalidates capture correctly** — Verify display geometry guard aborts dispatch when dimensions or orientation shift.
- **B07: Capture recovers through a fresh authorized start** — Re-invoke start capture and confirm clean reconstruction of virtual display pipeline.
- **B08: No unauthorized touch input occurs when required permissions are absent** — Verify gesture dispatch refusal when target package is unapproved or capture is off.

### Group C — Touch Lab
- **C01: Open the Touch Lab** — Navigate to `TouchLabActivity` and verify initialization.
- **C02: Single tap registers on the expected target** — Tap "Tap" button, dispatch `attackPoint()` gesture to checkerboard, observe `targetTaps` increment.
- **C03: Swipe produces observable movement events** — Tap "Swipe" button, dispatch `moveStart() -> moveEnd()` stroke, observe `moveEvents` increase.
- **C04: Two-finger gesture registers at least two simultaneous pointers** — Tap "2 fingers" button, dispatch concurrent touch paths, observe `maximumPointers >= 2`.
- **C05: Three visual taps complete correctly** — Tap "Run 3 visual taps", verify 3-cycle sequence of match -> tap -> disappear -> reappear -> match.
- **C06: Target disappearance and reappearance govern repeat actions** — Confirm no duplicate taps fire during target absence window.
- **C07: Stop cancels further actions** — Tap "Stop and return" mid-routine, verify immediate cancellation of in-flight actions.
- **C08: Leaving the lab cancels queued/running lab routines** — Confirm `onPause()` calls `setLabActive(false)`.
- **C09: Reopening the lab does not automatically resume a stopped routine** — Confirm reopened lab remains in idle ready state.
- **C10: Rapid repeated button presses do not create duplicate unexpected actions** — Confirm `inFlight` check refuses overlapping gesture requests.

### Group D — Image Recognition
- **D01: Capture a usable image** — Verify captured display frame resolution and non-blank buffer.
- **D02: Calibrate a distinctive local test target** — Verify template extraction over high-contrast target.
- **D03: Save the calibration** — Verify `RoutineStore` storage of template dimensions and byte array.
- **D04: Recognition succeeds for the learned target** — Validate `TemplateMatcher` score exceeds threshold on matching target.
- **D05: Recognition rejects a visibly different target** — Validate match score drops below threshold on absent/altered target.
- **D06: Low-contrast calibration is rejected** — Verify `MIN_VARIANCE` guard rejects solid color regions.
- **D07: Tap-limit enforcement works** — Verify execution terminates strictly after `maxTaps` touches.
- **D08: Timeout stops the routine** — Verify 60-second execution ceiling aborts stalled routines.
- **D09: Stale frames cannot trigger new actions** — Verify 1000ms frame freshness gate in accessibility service.
- **D10: Changed screen geometry invalidates incompatible calibration** — Verify dimension mismatch guard halts execution.

### Group E — Lifecycle & Recovery
- **E01: Background/foreground transitions** — Send app to background via Home, restore to foreground, verify UI state.
- **E02: Screen off and lock behavior** — Verify `isLocked()` keyguard check suppresses gesture dispatch.
- **E03: Permission revocation** — Verify `onUnbind()` clears accessibility service binding cleanly.
- **E04: Capture service restart** — Verify VirtualDisplay and ImageReader teardown before reinitialization.
- **E05: Accessibility disconnection** — Verify `onInterrupt()` halts any running routine.
- **E06: Application force-stop and manual relaunch** — Verify clean state upon cold start.
- **E07: No unintended automatic resumption** — Confirm routines require explicit user trigger upon launch.
- **E08: Session report export** — Verify JSON document structure generated by `exportReport()`.
- **E09: Report contains no captured screen content or credentials** — Audit exported JSON to confirm zero bitmap/token leakage.
- **E10: All test actions terminate safely** — Verify no orphaned background threads or pending dispatches.

### Group F — Stability & Resource Usage
- **F01: Stability and resource usage benchmark** — Monitor PSS memory, CPU usage, battery drain, and thermals across 30 seconds of active capture in Touch Lab.

### Group G — Wuthering Waves Integration Check
- **G01: Wuthering Waves package detection** — Verify presence of official game package `com.kurogame.wutheringwaves.global`.
- **G02: Game package target configuration alignment** — Verify default companion target matches installed package.

---

## 3. Timeout and Retry Policies

- **ADB Command Timeout:** 15 seconds.
- **MobileRun Inspection Timeout:** 20 seconds.
- **Gesture In-Flight Timeout:** 750 milliseconds (enforced by Android `GestureDescription`).
- **Routine Execution Timeout:** 60 seconds (enforced by `VisualTapRunner`).
- **Frame Freshness Timeout:** 1000 milliseconds (enforced by `AutomationAccessibilityService`).
- **Retry Policy:** Safe bounded retries (maximum 2 retries for UI button discovery); zero infinite polling loops.
