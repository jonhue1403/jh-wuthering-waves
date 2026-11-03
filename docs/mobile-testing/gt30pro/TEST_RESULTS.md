# Physical Device Test Results — Infinix GT 30 Pro

**Execution Date:** 2026-11-03  
**Target Device:** Infinix GT 30 Pro (`Infinix_X6873`, Android 16, XOS 16.3, 1224×2720 @ 480dpi)  
**Application:** JH WuWa Mobile (`com.jh.wuwa.mobile` 0.1.0-prototype)  
**Total Tests Evaluated:** 51  
**Reconciled Status:**
- **PHYSICAL PASS:** 28 tests (executed and asserted on physical hardware)
- **STATIC REVIEW:** 21 tests (code invariant, architecture, and security reviews)
- **BLOCKED / NOT RUN:** 2 tests (in-game live combat and overworld farming, intentionally out of scope for prototype v0.1.0)
- **FAIL:** 0
- **Contradictory Observations:** 0 (audited by `validate_assertions.py`)

---

## 1. Three Consecutive Critical Validation Runs

The critical chain was executed across **3 consecutive, uninterrupted runs** on the physical Infinix GT 30 Pro using `android/qa/run_critical_chain.py`:

**Chain per run:**  
Accessibility active $\to$ MediaProjection capture active $\to$ Frame delivery $\to$ Single Tap (C02) $\to$ Swipe (C03) $\to$ Dual Pointer Multi-Touch (C04) $\to$ Three Visual Taps (C05/C06) $\to$ Stop & Return (C07) $\to$ Advancing frame counter (B04) $\to$ Capture recovery (B05/B07).

### Critical Runs Observation Matrix

| Step / Assertion | Target Condition | Run 1 Observed | Run 2 Observed | Run 3 Observed | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Accessibility Binding** | Bound in secure settings | `Bound` | `Bound` | `Bound` | **PHYSICAL PASS** |
| **CaptureService State** | Running (`types=0x00000020`) | `Active` | `Active` | `Active` | **PHYSICAL PASS** |
| **Touch Lab Entry** | Dynamic bounds resolution | Entered (`True`) | Entered (`True`) | Entered (`True`) | **PHYSICAL PASS** |
| **Baseline OCR** | Metrics region parsed | Taps=0, Fig=0, Mov=0 | Taps=0, Fig=0, Mov=0 | Taps=0, Fig=0, Mov=0 | **PHYSICAL PASS** |
| **C02 Single Tap** | Target taps counter increases | `0 -> 1` | `0 -> 1` | `0 -> 1` | **PHYSICAL PASS** |
| **C03 Swipe** | Movement events counter increases | `0 -> 29` | `0 -> 30` | `0 -> 30` | **PHYSICAL PASS** |
| **C04 Two Fingers** | Max simultaneous fingers $\ge 2$ | `max_fingers = 2` | `max_fingers = 2` | `max_fingers = 2` | **PHYSICAL PASS** |
| **C05/C06 3 Visual Taps** | Target taps increases by exactly $+3$ | `2 -> 5` (+3 hits) | `2 -> 5` (+3 hits) | `2 -> 5` (+3 hits) | **PHYSICAL PASS** |
| **C07 Stop & Return** | Return cleanly to main screen | `True` | `True` | `True` | **PHYSICAL PASS** |
| **B04 Advancing Frames** | Frame counter advances ($>0$) | `202 frames` | `221 frames` | `219 frames` | **PHYSICAL PASS** |
| **B05/B07 Recovery** | Clean stop $\to$ restart $\to$ consent | `stopped=True, resumed=True` | `stopped=True, resumed=True` | `stopped=True, resumed=True` | **PHYSICAL PASS** |
| **Run Overall Verdict** | All 10 assertions true | **PASSED** | **PASSED** | **PASSED** | **GATE PASSED** |

> **Note on OCR Verification:** Canvas metric extraction was performed using OpenVINO OCR executed on the Windows development host against uncompressed device screenshots. On-device inference in the Android companion uses the lightweight `TemplateMatcher` native Kotlin routine.

---

## 2. Comprehensive Test Classification Table

### Group A: Installation & UI (8 Tests)

| Test ID | Category | Description | Status | Measured / Observed Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **A01** | PHYSICAL PASS | APK installation succeeds | **PASS** | Package path confirmed; `versionName=0.1.0-prototype`, `versionCode=1` verified |
| **A02** | PHYSICAL PASS | App launches without crashing | **PASS** | Process alive, 0 fatal exceptions in logcat |
| **A03** | PHYSICAL PASS | Main screen displays controls | **PASS** | Header, session card, touch controls, capture button verified in accessibility tree |
| **A04** | PHYSICAL PASS | Portrait layout renders correctly | **PASS** | 1224×2720 display resolution utilized, screenshot `A04_portrait_layout.png` |
| **A05** | PHYSICAL PASS | Landscape layout adaptation | **PASS** | Adapts to 2720×1224 mode with dual-column scrollable controls, screenshot `A05_landscape_layout.png` |
| **A06** | PHYSICAL PASS | Scrolling and lower controls usable | **PASS** | Dynamic scrolling reveals Touch Lab button, session export, and game package controls |
| **A07** | PHYSICAL PASS | Settings persist after restart | **PASS** | Target package configuration persisted across app cold restart |
| **A08** | PHYSICAL PASS | Repeated launch/close cycles | **PASS** | 5 consecutive launch/close cycles executed cleanly with 0 crashes |

### Group B: Permissions & Screen Capture (8 Tests)

| Test ID | Category | Description | Status | Measured / Observed Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **B01** | PHYSICAL PASS | Accessibility service connection | **PASS** | Enabled in secure settings, UI reflects `Touch control connected` |
| **B02** | STATIC REVIEW | Screen-capture manifest declaration | **PASS** | Verified `android.permission.FOREGROUND_SERVICE_MEDIA_PROJECTION` in AndroidManifest |
| **B03** | PHYSICAL PASS | Capture starts after user approval | **PASS** | `CaptureService` confirmed running with `types=0x00000020` (mediaProjection) |
| **B04** | PHYSICAL PASS | Frame counter increases during capture | **PASS** | Verified advancing frame counts across 3 runs (202, 221, 219 frames delivered) |
| **B05** | PHYSICAL PASS | Capture stops after user stop button | **PASS** | Tap "Stop screen capture" destroyed `CaptureService` cleanly, dumpsys reports (nothing) |
| **B06** | STATIC REVIEW | Orientation mismatch invalidation | **PASS** | DisplayListener guard terminates session on display geometry change |
| **B07** | PHYSICAL PASS | Capture recovers through fresh start | **PASS** | Fresh start prompts MediaProjection dialog, user consent restores capture cleanly |
| **B08** | STATIC REVIEW | Unauthorized touch input prevented | **PASS** | Verified code guard: package check, focus check, keyguard lock check, frame freshness |

### Group C: Touch Lab (10 Tests)

| Test ID | Category | Description | Status | Measured / Observed Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **C01** | PHYSICAL PASS | Open the Touch Lab | **PASS** | `TouchLabActivity` opened displaying information, TouchLabView canvas, and controls |
| **C02** | PHYSICAL PASS | Single tap registers on target | **PASS** | Tap hits checkerboard target; OCR confirmed `Target taps: 0 -> 1` in all 3 runs |
| **C03** | PHYSICAL PASS | Swipe produces movement events | **PASS** | Swipe stroke produced 29, 30, 30 `Movement events` across runs |
| **C04** | PHYSICAL PASS | Multi-touch registers simultaneous fingers | **PASS** | Dual-pointer gesture registered `Max fingers: 2` simultaneously in all 3 runs |
| **C05** | PHYSICAL PASS | Three visual taps complete correctly | **PASS** | Template matcher performed 3 full visual match-tap cycles: `Target taps: 2 -> 5` (+3 hits) |
| **C06** | PHYSICAL PASS | Target disappearance & reappearance | **PASS** | Target disappeared for 1000ms after each hit; routine waited for reappearance |
| **C07** | PHYSICAL PASS | Stop cancels further actions | **PASS** | "Stop and return" halted routine immediately and exited lab |
| **C08** | STATIC REVIEW | Leaving lab cancels routines | **PASS** | `onPause()` resets `labActive=false`, deauthorizing companion frames |
| **C09** | PHYSICAL PASS | Reopening lab initializes in idle state | **PASS** | Reopened Touch Lab initialized in clean state (OCR verified baseline: 0 taps, 0 fingers, 0 moves) |
| **C10** | STATIC REVIEW | Rapid button presses guarded | **PASS** | Verified in-flight lock (`synchronized(this) { if (inFlight != null) return false }`) |

### Group D: Vision & Image Processing (10 Tests)

| Test ID | Category | Description | Status | Measured / Observed Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **D01** | PHYSICAL PASS | Capture usable image | **PASS** | Uncompressed display buffer acquired at 1224×2720 resolution |
| **D02** | STATIC REVIEW | Calibrate distinctive target | **PASS** | High-contrast 6×6 checkerboard pattern extraction logic verified |
| **D03** | STATIC REVIEW | Save calibration | **PASS** | RoutineStore JSON serialization to app-private SharedPreferences verified |
| **D04** | PHYSICAL PASS | Recognition succeeds on target | **PASS** | TemplateMatcher scored > 0.82 on live checkerboard target, triggering 3 accurate taps |
| **D05** | STATIC REVIEW | Rejects visibly different target | **PASS** | VisualTapRunner state machine verifies NCC score drops below 0.82 during target absence |
| **D06** | STATIC REVIEW | Low-contrast calibration rejected | **PASS** | Verified MIN_VARIANCE (12.0f) guard in TemplateMatcher.kt |
| **D07** | PHYSICAL PASS | Tap-limit enforcement | **PASS** | Routine halted strictly upon reaching configured `maxTaps = 3` (Target taps 2 $\to$ 5) |
| **D08** | STATIC REVIEW | Routine timeout stops routine | **PASS** | Verified 60,000ms routine ceiling timeout in VisualTapRunner.kt |
| **D09** | STATIC REVIEW | Stale frames rejected | **PASS** | Verified 1,000ms frame freshness age guard in SessionController.kt |
| **D10** | STATIC REVIEW | Geometry change invalidates calibration | **PASS** | Display size/orientation mismatch aborts dispatch |

### Group E: Lifecycle & Session Management (10 Tests)

| Test ID | Category | Description | Status | Measured / Observed Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **E01** | PHYSICAL PASS | Background/foreground transitions | **PASS** | App paused on Home press, restored cleanly without state corruption |
| **E02** | STATIC REVIEW | Screen off & lock behavior | **PASS** | `isLocked()` KeyguardManager check suppresses gesture dispatch when device is locked |
| **E03** | STATIC REVIEW | Permission revocation handling | **PASS** | Service unbind cleans up singleton state and cancels active routines |
| **E04** | STATIC REVIEW | Capture service restart cleanup | **PASS** | VirtualDisplay and ImageReader released cleanly in teardown() |
| **E05** | STATIC REVIEW | Accessibility disconnection | **PASS** | `onInterrupt()` stops routines and alerts user |
| **E06** | PHYSICAL PASS | Manual relaunch after kill | **PASS** | Cold start returns app to clean initial state |
| **E07** | STATIC REVIEW | No unintended automatic resumption | **PASS** | Routine runner and pending state confined to volatile memory, never persisted |
| **E08** | STATIC REVIEW | Session report export | **PASS** | JSON report generated with version and event timeline |
| **E09** | STATIC REVIEW | Report contains no screen content | **PASS** | Zero bitmaps, tokens, or personal identifiers present in exported JSON (`containsScreenshots: false`) |
| **E10** | STATIC REVIEW | All test actions terminate safely | **PASS** | All routines and background handlers stopped cleanly on shutdown |

### Group F: Stability & Telemetry Benchmark (1 Test)

| Test ID | Category | Description | Status | Measured / Observed Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **F01** | PHYSICAL PASS | Stability & resource usage benchmark | **PASS** | Avg PSS Memory: **83.2 MB**, Peak PSS: **83.8 MB**, Battery Temp: **34.3 °C**, Crashes: **0**, ANRs: **0** |

### Group G: Game Package Integration (2 Tests)

| Test ID | Category | Description | Status | Measured / Observed Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **G01** | PHYSICAL PASS | Wuthering Waves package detection | **PASS** | `com.kurogame.wutheringwaves.global` (v3.7.1) detected on physical device |
| **G02** | STATIC REVIEW | Game target alignment | **PASS** | Companion default target aligns with installed global game package |

### Group H: Live In-Game Automation (2 Tests — BLOCKED)

| Test ID | Category | Description | Status | Reason for Blocked Status |
| :--- | :--- | :--- | :--- | :--- |
| **H01** | BLOCKED | In-game combat loop automation | **BLOCKED** | Prototype v0.1.0 is an on-device feasibility prototype. Live in-game combat loops are outside prototype scope and non-destructive testing policy. |
| **H02** | BLOCKED | Overworld navigation and daily quests | **BLOCKED** | Live game account interactions and destructive overworld actions are out of scope. |

---

## 3. Qualified Resource & Telemetry Findings

During the 30-second benchmark session on the physical Infinix GT 30 Pro:

- **Average Application PSS Memory:** 83.20 MB (Peak: 83.79 MB) — well within the 250 MB ceiling.
- **Battery Temperature:** 34.3 °C steady (no thermal throttling or overheating).
- **Battery Level Delta:** 0% recorded over 30s benchmark.  
  > *Qualification:* This reflects the integer reporting resolution of Android's `dumpsys battery` over a brief window; it does not indicate zero power draw.
- **Application Stability:** 0 fatal crashes, 0 ANRs.  
  > *Qualification:* A 30-second benchmark demonstrates initial runtime resource stability; it does not constitute proof of multi-hour stability under 3D GPU load during extended gameplay.
- **Frame & Gesture Timing:**  
  Frames were delivered continuously to `SessionController` (advancing by >200 frames per session). Gesture submission delay was ~180ms as configured in `TouchLabActivity`.  
  > *Qualification:* Frame delivery latency below 50ms is an engineering estimate based on frame intervals; formal sub-50ms latency claims require hardware high-speed camera verification.
