---
title: Android on-device feasibility prototype
created: 2026-11-03
status: in-review-device-validation-pending
baseline_commit: d13798d2e46dbb913f0c167e664d29cba6d1174b
---

# Android on-device feasibility prototype

## Intent and approval

The user approved the Android feasibility prototype proposed in the preceding
conversation: run capture, local recognition and touch actions on the phone while
the PC is off. Full game parity is an eventual objective, not an observed result.
This implementation is the first runnable capability proof; native game testing
requires the user's device and remains a separate acceptance gate.

## Scope

- Add a self-contained `android/` application to this existing fork. Keep the
  desktop runtime and its validation records intact.
- Kotlin, Android API 26+, compile/target API 35, JDK 17, AGP 8.9.2,
  Kotlin 2.1.20, Gradle 8.11.1. Native Android views keep the first APK small.
- User-granted MediaProjection capture with a visible foreground service.
- User-enabled AccessibilityService, one bounded gesture dispatcher, and explicit
  target-app checks. Standard permissions; no root or PC connection at runtime.
- A touch laboratory in this app to prove taps, swipes and overlapping pointers.
- Capture a game frame, drag-select a visual target, persist that calibration and
  run a bounded image-conditioned tap routine. This is not a preverified daily or
  combat profile. Show that distinction in the UI and documentation.
- Local session diagnostics and JSON export through the system document picker.
- No cloud inference or network permission in the app. No bundled game assets,
  account credentials, arbitrary scripting, or background startup after reboot.

## Runtime invariants

| Event | Required behavior |
| --- | --- |
| Capture permission denied/revoked | Show actionable state; release resources; stop routine. |
| Device locked / screen off / capture size or rotation changes | Stop capture and routine; require fresh user start. |
| Another app becomes active | Stop the routine; never automatically resume. |
| Frame older than 1000 ms / non-increasing timestamp | Never dispatch from it. |
| Target appearance stays unchanged after a tap | Wait for it to disappear before another tap. |
| Gesture completion arrives after stop | Ignore it through a run generation token. |
| Timeout, dispatch refusal, or cancellation | Stop with a concrete reason. |
| Stop pressed mid-gesture | Stop scheduling immediately. Current finite gesture may finish within 750 ms. |

## Shared code contracts

All core types live in `com.jh.wuwa.core` in the independent JVM `:core` module.
Android runtime lives in `com.jh.wuwa.runtime`; UI in `com.jh.wuwa`.

Core types:

```kotlin
data class NormalizedPoint(val x: Float, val y: Float)
data class NormalizedRect(val left: Float, val top: Float, val right: Float, val bottom: Float) {
    val center: NormalizedPoint
}
data class GrayFrame(val width: Int, val height: Int, val pixels: ByteArray, val capturedAtMs: Long)
data class VisualTemplate(val region: NormalizedRect, val frameWidth: Int, val frameHeight: Int,
                          val samples: ByteArray, val sampleSize: Int = 24)
object TemplateMatcher {
    fun capture(frame: GrayFrame, region: NormalizedRect, sampleSize: Int = 24): VisualTemplate
    fun similarity(frame: GrayFrame, template: VisualTemplate): Double
}
data class TapRoutine(val name: String, val targetPackage: String, val template: VisualTemplate,
                      val tap: NormalizedPoint = template.region.center,
                      val maxTaps: Int = 1, val timeoutMs: Long = 60_000,
                      val cooldownMs: Long = 1500, val matchThreshold: Double = 0.97,
                      val stableFrames: Int = 3)
sealed interface RoutineDecision {
    data object Wait : RoutineDecision
    data class Tap(val point: NormalizedPoint) : RoutineDecision
    data class Finished(val reason: String) : RoutineDecision
}
class VisualTapRunner(val routine: TapRoutine, val startedAtMs: Long) {
    val completedTaps: Int
    val message: String
    val finished: Boolean
    fun update(frame: GrayFrame?, nowMs: Long, targetActive: Boolean, captureActive: Boolean): RoutineDecision
    fun acknowledgeTap(success: Boolean, nowMs: Long)
    fun cancel(reason: String)
}
data class TouchStroke(val points: List<NormalizedPoint>, val startMs: Long, val durationMs: Long)
data class GesturePlan(val strokes: List<TouchStroke>)
object GesturePresets {
    fun tap(point: NormalizedPoint): GesturePlan
    fun swipe(from: NormalizedPoint, to: NormalizedPoint, durationMs: Long = 500): GesturePlan
    fun moveAndTap(from: NormalizedPoint, to: NormalizedPoint, attack: NormalizedPoint): GesturePlan
}
```

Core validation rejects non-finite coordinates, invalid geometry, oversized
inputs, calibration with insufficient contrast, different frame dimensions,
unbounded routines, and gestures exceeding 750 ms. Matching uses only the chosen
region; no claim of universal mobile HUD recognition.

Android runtime contracts (UI consumes these; the runtime module owns them):

```kotlin
data class CapturedFrame(val bitmap: Bitmap, val gray: GrayFrame,
                         val displayWidth: Int, val displayHeight: Int, val rotation: Int,
                         val sourcePackage: String = "")
data class SessionSnapshot(val captureActive: Boolean, val accessibilityConnected: Boolean,
    val targetPackage: String, val foregroundPackage: String?, val targetActive: Boolean,
    val status: String, val frameCount: Long, val frameAgeMs: Long?,
    val taps: Int, val routineRunning: Boolean)
object SessionController {
    val snapshot: SessionSnapshot
    val latestFrame: CapturedFrame?
    fun configure(context: Context, targetPackage: String)
    fun setLabActive(active: Boolean)
    fun startRoutine(context: Context, routine: TapRoutine)
    fun stopRoutine(reason: String = "Stopped by user")
    fun requestGesture(plan: GesturePlan): Boolean
    fun stopCapture(context: Context)
    fun addListener(listener: () -> Unit)
    fun removeListener(listener: () -> Unit)
    fun exportReport(): String
}
class CaptureService : Service { companion object {
    fun start(context: Context, resultCode: Int, resultData: Intent)
} }
class AutomationAccessibilityService : AccessibilityService
```

Listeners notify on the main thread. Published capture bitmaps are immutable and
must not be recycled while another consumer may hold them. Frame analysis is
downsampled to at most 720 px wide and throttled; source/display geometry is
preserved and any orientation change invalidates the session. Capture frames are
retained only for the selected foreground game or the resumed touch lab. A start
may wait up to 10 seconds for the selected app to appear; once running, focus loss
ends it. The accessibility service verifies the active window immediately before
each gesture; lab mode only permits the app's resumed lab activity.

## Ownership and code map

- `android/core/src/` — agent core logic and unit tests; no Android dependencies.
- `android/app/src/main/java/com/jh/wuwa/runtime/` — agent capture, session,
  accessibility and gesture dispatch.
- `android/app/src/main/java/com/jh/wuwa/` excluding runtime — root app, calibration,
  storage, lab and diagnostics UI.
- Gradle, manifest/resources, CI, documentation — root.
- Existing `src/`, `tests/` and Windows workflows — no implementation changes.

## Acceptance and verification

- [x] Unit tests cover frame geometry, stale frames, appearance transitions,
  action limits, loss of focus/capture, timeouts and bounded multi-touch plans.
- [x] `:core:test :app:testDebugUnitTest :app:lintDebug :app:assembleDebug` pass.
- [x] APK metadata/signature verified; no network or storage permission requested.
- [x] Independent review of lifecycle, target checks, and cancellation behavior.
- [ ] Install and demonstrate capture + touch + visual routine on Android.
- [ ] Wuthering Waves session on the target physical phone, including interruption
  and sustained-performance tests. Remains NOT RUN without the device.

Software checks and device/gameplay evidence must be reported separately. A passing
build is not evidence of a successful daily, boss kill, or farming loop.

## Implementation notes

2026-11-03: Implemented the standalone Android application, independent core,
touch lab, visual calibration, bounded routines, metadata export, Gradle wrapper
and Android CI workflow. Existing desktop validation history is not mobile evidence.

Frame delivery uses one pending slot to bound memory when the main thread is
busy. Capture teardown is serialized with image processing. Focus-generation
checks reject frames queued before an app transition; leaving the lab cancels
both armed and running lab routines. Landscape lab/calibration layouts preserve
the target geometry while controls scroll separately.

## Review and verification log

The final local command passed with **62 tests** (34 core and 28 Android component
tests), no failures, errors or skips. Android component tests use Robolectric at
API 35; they are not tests on a physical device. Lint completed with zero errors
and 11 warnings. The debug APK assembled and passed `apksigner verify`.

An independent source review checked capture teardown, frame ownership, focus
boundaries, queued callbacks, manual gesture reentry, lab lifecycle and landscape
layout. The concrete findings were fixed and the final verification was rerun.

See [the verification record](android-verification-2026-11-03.md) for the artifact
identity, warning details and evidence boundary. Physical capture/input, game
response and sustained device behavior remain unverified.
