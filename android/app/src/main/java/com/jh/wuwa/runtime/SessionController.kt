package com.jh.wuwa.runtime

import android.app.KeyguardManager
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import com.jh.wuwa.core.GesturePlan
import com.jh.wuwa.core.GesturePresets
import com.jh.wuwa.core.GrayFrame
import com.jh.wuwa.core.RoutineDecision
import com.jh.wuwa.core.TapRoutine
import com.jh.wuwa.core.VisualTapRunner
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.CopyOnWriteArraySet
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference

/** A published image is never recycled by the producer while a UI can hold it. */
data class CapturedFrame(
    val bitmap: Bitmap,
    val gray: GrayFrame,
    val displayWidth: Int,
    val displayHeight: Int,
    val rotation: Int,
    val sourcePackage: String = "",
)

data class SessionSnapshot(
    val captureActive: Boolean,
    val accessibilityConnected: Boolean,
    val targetPackage: String,
    val foregroundPackage: String?,
    val targetActive: Boolean,
    val status: String,
    val frameCount: Long,
    val frameAgeMs: Long?,
    val taps: Int,
    val routineRunning: Boolean,
)

/**
 * Process-local coordinator. Mutable routine state is confined to the main thread.
 * No token, screen content or game state survives process death.
 */
object SessionController {
    const val DEFAULT_TARGET = "com.kurogame.wutheringwaves.global"
    private const val ARM_TIMEOUT_MS = 10_000L
    private const val FRAME_MAX_AGE_MS = 1_000L
    private const val FRAME_STALL_TIMEOUT_MS = 2_500L
    private const val FOCUS_SETTLE_MS = 300L
    private val main = Handler(Looper.getMainLooper())
    private val listeners = CopyOnWriteArraySet<() -> Unit>()
    private val events = ArrayDeque<JSONObject>()
    private var appContext: Context? = null
    @Volatile private var appPackage = "com.jh.wuwa.mobile"
    @Volatile private var target = DEFAULT_TARGET
    @Volatile private var foreground: String? = null
    @Volatile private var focusEpoch = 0L
    @Volatile private var focusChangedAt = 0L
    @Volatile private var labActive = false
    @Volatile private var captureActive = false
    @Volatile private var access: AutomationAccessibilityService? = null
    @Volatile private var frame: CapturedFrame? = null
    private var frameFocusEpoch = -1L
    private var status = "Enable accessibility, then start screen capture."
    private var frameCount = 0L
    private var taps = 0
    private var pending: TapRoutine? = null
    private var pendingDeadline = 0L
    private var runner: VisualTapRunner? = null
    private var generation = 0L
    private var tickScheduled = false
    private var manualGesture = false
    private var captureStartedAt = 0L
    private var announceFirstFrame = false
    private data class PendingFrame(val capture: CapturedFrame, val permit: CapturePermit)
    private val pendingFrame = AtomicReference<PendingFrame?>(null)
    private val frameDeliveryScheduled = AtomicBoolean(false)

    val latestFrame: CapturedFrame? get() = frame

    val snapshot: SessionSnapshot
        get() {
            val now = SystemClock.elapsedRealtime()
            return SessionSnapshot(
                captureActive, access != null, target, foreground,
                isAllowedPackage(foreground), status, frameCount,
                frame?.let { (now - it.gray.capturedAtMs).coerceAtLeast(0L) },
                taps, pending != null || runner != null,
            )
        }

    fun configure(context: Context, targetPackage: String) = onMain {
        require(targetPackage.matches(Regex("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z0-9_]+)+"))) {
            "Enter a valid Android package name."
        }
        appContext = context.applicationContext
        appPackage = context.packageName
        if (target != targetPackage) {
            stopRoutine("Target changed; start a new routine.")
            target = targetPackage
            invalidateFocus()
            frame = null
            record("target_changed", "Selected $targetPackage")
        }
        refreshForeground()
        publish()
    }

    fun setLabActive(active: Boolean) = onMain {
        if (labActive != active) {
            labActive = active
            invalidateFocus()
        }
        if (!active && (runner?.routine?.targetPackage == appPackage || pending?.targetPackage == appPackage)) {
            stopRoutine("Touch lab left the foreground.")
        }
        if (!active && manualGesture) stopRoutine("Touch lab left the foreground.")
        refreshForeground()
        publish()
    }

    fun startRoutine(context: Context, routine: TapRoutine) = onMain {
        appContext = context.applicationContext
        appPackage = context.packageName
        stopRoutine("Previous routine replaced.")
        when {
            !captureActive -> fail("Start screen capture before running a routine.")
            access == null -> fail("Enable the JH Wuwa accessibility service first.")
            access?.isGestureInFlight == true -> fail("Wait for the current touch test to finish.")
            routine.targetPackage != target && routine.targetPackage != appPackage ->
                fail("This calibration belongs to another app. Select its target first.")
            else -> {
                generation++
                taps = 0
                pending = routine
                pendingDeadline = SystemClock.elapsedRealtime() + ARM_TIMEOUT_MS
                status = "Waiting for ${routine.targetPackage} and a fresh frame (10 seconds)."
                record("routine_armed", routine.name)
                scheduleTick()
                publish()
            }
        }
    }

    fun stopRoutine(reason: String = "Stopped by user") = onMain {
        generation++
        val wasRunning = pending != null || runner != null || manualGesture
        announceFirstFrame = false
        runner?.let {
            taps = it.completedTaps
            it.cancel(reason)
        }
        runner = null
        pending = null
        manualGesture = false
        status = reason
        if (wasRunning) record("routine_stopped", reason)
        publish()
    }

    /** Returns whether dispatch was accepted; completion is exposed in status. */
    fun requestGesture(plan: GesturePlan): Boolean {
        check(Looper.myLooper() == Looper.getMainLooper()) { "Call from the main thread." }
        if (runner != null || pending != null) {
            fail("Stop the routine before using a manual touch test.")
            return false
        }
        val service = access
        if (!captureActive || service == null) {
            fail("Enable accessibility and start capture before a touch test.")
            return false
        }
        if (service.isGestureInFlight) {
            // A rejected second click must not invalidate the first completion token.
            fail("A touch test is still finishing. Wait for its completion.")
            return false
        }
        refreshForeground()
        val current = frame
        if (current == null || !fresh(current) || !isAllowedPackage(foreground) ||
            current.sourcePackage != foreground
        ) {
            fail("Open the selected game or touch lab and wait for a fresh capture.")
            return false
        }
        val token = ++generation
        announceFirstFrame = false
        val accepted = service.dispatchPlan(plan, current.sourcePackage, current) { success ->
            if (token != generation) return@dispatchPlan
            manualGesture = false
            status = if (success) "Touch test completed. Check what happened on screen."
            else "Touch test cancelled or refused; no further input was sent."
            record(if (success) "gesture_completed" else "gesture_cancelled", "Manual touch test")
            publish()
        }
        if (accepted) {
            manualGesture = true
            status = "Touch test in progress (at most 750 ms)."
            record("gesture_dispatched", "Manual touch test")
            publish()
        } else fail(service.lastDispatchFailure)
        return accepted
    }

    fun stopCapture(context: Context) {
        stopRoutine("Capture stopped by user.")
        val captureIntent = Intent(context, CaptureService::class.java)
        context.stopService(captureIntent)
    }

    fun addListener(listener: () -> Unit) {
        listeners.add(listener)
        main.post { if (listener in listeners) listener() }
    }

    fun removeListener(listener: () -> Unit) { listeners.remove(listener) }

    fun exportReport(): String {
        check(Looper.myLooper() == Looper.getMainLooper()) { "Export from the main thread." }
        val current = snapshot
        return JSONObject().apply {
            put("schemaVersion", 1)
            put("app", "JH Wuwa Mobile")
            put("version", "0.1.0-prototype")
            put("evidenceScope", "Runtime diagnostics; not proof of successful gameplay")
            put("device", JSONObject().apply {
                put("manufacturer", Build.MANUFACTURER)
                put("model", Build.MODEL)
                put("androidSdk", Build.VERSION.SDK_INT)
                put("androidRelease", Build.VERSION.RELEASE)
            })
            put("session", JSONObject().apply {
                put("elapsedMs", if (captureStartedAt == 0L) 0 else SystemClock.elapsedRealtime() - captureStartedAt)
                put("captureActive", current.captureActive)
                put("accessibilityConnected", current.accessibilityConnected)
                put("targetPackage", current.targetPackage)
                put("foregroundPackage", current.foregroundPackage ?: JSONObject.NULL)
                put("framesAccepted", current.frameCount)
                put("lastFrameAgeMs", current.frameAgeMs ?: JSONObject.NULL)
                put("gesturesCompletedInRoutine", current.taps)
                put("routineRunning", current.routineRunning)
                put("status", current.status)
                frame?.let {
                    put("displayWidth", it.displayWidth)
                    put("displayHeight", it.displayHeight)
                    put("analysisWidth", it.gray.width)
                    put("analysisHeight", it.gray.height)
                    put("rotation", it.rotation)
                }
            })
            put("events", JSONArray(events.toList()))
            put("containsScreenshots", false)
            put("physicalGameValidation", "NOT_ATTESTED")
        }.toString(2)
    }

    internal fun connectAccessibility(service: AutomationAccessibilityService) = onMain {
        access = service
        appContext = service.applicationContext
        appPackage = service.packageName
        status = if (captureActive) "Accessibility connected. Capture is ready."
        else "Accessibility connected. Start screen capture next."
        record("accessibility_connected", "Service connected")
        refreshForeground()
        publish()
    }

    internal fun disconnectAccessibility(service: AutomationAccessibilityService) = onMain {
        if (access !== service) return@onMain
        access = null
        foreground = null
        stopRoutine("Accessibility disconnected. Enable it before continuing.")
        record("accessibility_disconnected", "Service unavailable")
    }

    internal fun foregroundChanged(packageName: String?) = onMain {
        updateForeground(packageName)
        val activeRunner = runner
        if (activeRunner != null && !isRoutineTargetActive(activeRunner.routine.targetPackage)) {
            stopRoutine("The target app left the foreground. Start again to resume.")
        }
        if (manualGesture && !isAllowedPackage(packageName)) {
            stopRoutine("The touch-test target left the foreground.")
        }
        publish()
    }

    internal fun captureStarted() = onMain {
        captureActive = true
        invalidateFocus()
        pendingFrame.set(null)
        frame = null
        frameFocusEpoch = -1L
        frameCount = 0
        captureStartedAt = SystemClock.elapsedRealtime()
        announceFirstFrame = true
        status = "Capture active. Open the selected game or touch lab."
        record("capture_started", "User-granted screen capture")
        publish()
    }

    internal fun captureStopped(reason: String) = onMain {
        captureActive = false
        invalidateFocus()
        pendingFrame.set(null)
        stopRoutine(reason)
        record("capture_stopped", reason)
        publish()
    }

    internal fun captureFailed(reason: String) = onMain {
        captureActive = false
        invalidateFocus()
        pendingFrame.set(null)
        stopRoutine(reason)
        record("capture_failed", reason)
        publish()
    }

    internal data class CapturePermit(val packageName: String, val focusEpoch: Long)

    /** Worker-thread fast filter. A focus transition invalidates queued captures. */
    internal fun capturePermit(): CapturePermit? {
        val epoch = focusEpoch
        val packageName = foreground ?: return null
        if (!captureActive || !isAllowedPackage(packageName) ||
            SystemClock.elapsedRealtime() - focusChangedAt < FOCUS_SETTLE_MS
        ) return null
        return CapturePermit(packageName, epoch)
    }

    internal fun acceptFrame(captured: CapturedFrame, permit: CapturePermit) {
        if (!captureActive || permit.focusEpoch != focusEpoch) return
        // Keep only the newest frame when the UI thread is busy. Never queue a
        // bitmap-bearing lambda for every capture callback.
        pendingFrame.set(PendingFrame(captured, permit))
        scheduleFrameDelivery()
    }

    private val deliverNewestFrame = object : Runnable {
        override fun run() {
            try {
                pendingFrame.getAndSet(null)?.let { deliverFrame(it.capture, it.permit) }
            } finally {
                frameDeliveryScheduled.set(false)
                if (pendingFrame.get() != null) scheduleFrameDelivery()
            }
        }
    }

    private fun scheduleFrameDelivery() {
        if (frameDeliveryScheduled.compareAndSet(false, true)) main.post(deliverNewestFrame)
    }

    private fun deliverFrame(captured: CapturedFrame, permit: CapturePermit) {
        if (!captureActive || isLocked()) return
        val actual = access?.activePackage()
        updateForeground(actual)
        if (actual != captured.sourcePackage || !isAllowedPackage(actual) ||
            permit.focusEpoch != focusEpoch || permit.packageName != actual ||
            captured.gray.capturedAtMs - focusChangedAt < FOCUS_SETTLE_MS
        ) return
        if (captured.gray.capturedAtMs <= (frame?.gray?.capturedAtMs ?: -1L)) return
        frame = captured
        frameFocusEpoch = permit.focusEpoch
        frameCount++
        if (announceFirstFrame && runner == null && pending == null && !manualGesture) {
            status = "Capturing ${captured.sourcePackage}. Ready for calibration or touch tests."
            announceFirstFrame = false
        }
        publish()
    }

    internal fun isAllowedPackage(packageName: String?): Boolean = when (packageName) {
        null -> false
        appPackage -> labActive // The main/configuration activities are never touch targets.
        else -> packageName == target
    }

    internal fun isRoutineTargetActive(packageName: String): Boolean =
        foreground == packageName && isAllowedPackage(packageName) && !isLocked()

    internal fun isLocked(): Boolean =
        appContext?.getSystemService(KeyguardManager::class.java)?.isKeyguardLocked ?: true

    private val tick = object : Runnable {
        override fun run() {
            tickScheduled = false
            runTick()
            if (runner != null || pending != null) scheduleTick()
        }
    }

    private fun scheduleTick() {
        if (tickScheduled) return
        tickScheduled = true
        main.postDelayed(tick, 100L)
    }

    private fun runTick() {
        if (pending == null && runner == null) return
        if (!captureActive || access == null || isLocked()) {
            stopRoutine("Capture/accessibility unavailable or device locked.")
            return
        }
        refreshForeground()
        val now = SystemClock.elapsedRealtime()
        pending?.let { armed ->
            if (now >= pendingDeadline) {
                stopRoutine("Could not get a fresh frame from the target within 10 seconds.")
                return
            }
            val candidate = frame
            if (!isRoutineTargetActive(armed.targetPackage) || candidate == null ||
                candidate.sourcePackage != armed.targetPackage || !fresh(candidate)
            ) return
            if (candidate.gray.width != armed.template.frameWidth ||
                candidate.gray.height != armed.template.frameHeight
            ) {
                stopRoutine("Capture dimensions changed. Create a new calibration.")
                return
            }
            runner = VisualTapRunner(armed, now)
            pending = null
            status = "Running ${armed.name}."
            record("routine_started", armed.name)
        }
        val active = runner ?: return
        if (!isRoutineTargetActive(active.routine.targetPackage)) {
            stopRoutine("The target app left the foreground. Start again to resume.")
            return
        }
        val latest = frame
        if (latest == null || latest.sourcePackage != active.routine.targetPackage ||
            now - latest.gray.capturedAtMs > FRAME_STALL_TIMEOUT_MS
        ) {
            stopRoutine("Target capture stalled. Restart capture before continuing.")
            return
        }
        when (val decision = active.update(latest.gray, now, targetActive = true, captureActive = true)) {
            RoutineDecision.Wait -> {
                status = active.message
                taps = active.completedTaps
                publish()
            }
            is RoutineDecision.Finished -> finishRoutine(active, decision.reason)
            is RoutineDecision.Tap -> {
                val token = generation
                val accepted = access?.dispatchPlan(
                    GesturePresets.tap(decision.point), active.routine.targetPackage, latest,
                ) { success ->
                    if (token != generation || runner !== active) return@dispatchPlan
                    active.acknowledgeTap(success, SystemClock.elapsedRealtime())
                    taps = active.completedTaps
                    record(if (success) "routine_gesture_completed" else "routine_gesture_cancelled", "Action $taps")
                    status = active.message
                    if (active.finished) finishRoutine(active, active.message) else publish()
                } ?: false
                if (!accepted && token == generation && runner === active) {
                    active.acknowledgeTap(false, now)
                    finishRoutine(active, access?.lastDispatchFailure ?: "Accessibility unavailable.")
                }
            }
        }
    }

    private fun finishRoutine(active: VisualTapRunner, reason: String) {
        if (runner !== active) return
        taps = active.completedTaps
        runner = null
        pending = null
        generation++
        status = reason
        record("routine_finished", reason)
        publish()
    }

    private fun fresh(value: CapturedFrame): Boolean {
        val age = SystemClock.elapsedRealtime() - value.gray.capturedAtMs
        return age in 0..FRAME_MAX_AGE_MS && frameFocusEpoch == focusEpoch
    }

    private fun refreshForeground() { updateForeground(access?.activePackage()) }

    private fun updateForeground(packageName: String?) {
        if (foreground != packageName) {
            foreground = packageName
            invalidateFocus()
        }
    }

    private fun invalidateFocus() {
        focusEpoch++
        focusChangedAt = SystemClock.elapsedRealtime()
    }

    private fun fail(reason: String) {
        announceFirstFrame = false
        status = reason
        record("action_refused", reason)
        publish()
    }

    private fun record(type: String, detail: String) {
        events.addLast(JSONObject().apply {
            put("elapsedRealtimeMs", SystemClock.elapsedRealtime())
            put("type", type)
            put("detail", detail)
        })
        while (events.size > 200) events.removeFirst()
    }

    private fun publish() {
        if (Looper.myLooper() != Looper.getMainLooper()) {
            main.post { publish() }
            return
        }
        listeners.forEach { it() }
    }

    private inline fun onMain(crossinline action: () -> Unit) {
        if (Looper.myLooper() == Looper.getMainLooper()) action() else main.post { action() }
    }
}
