package com.jh.wuwa.runtime

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.content.Intent
import android.graphics.Path
import android.os.Handler
import android.os.Build
import android.os.Looper
import android.os.SystemClock
import android.view.accessibility.AccessibilityEvent
import com.jh.wuwa.core.GesturePlan

/** Uses only window package identity, never accessibility text or game memory. */
class AutomationAccessibilityService : AccessibilityService() {
    private val main = Handler(Looper.getMainLooper())
    private var dispatchId = 0L
    private var inFlight: Long? = null
    private var pendingCompletion: ((Boolean) -> Unit)? = null
    var lastDispatchFailure: String = "Touch dispatch was refused."
        private set
    val isGestureInFlight: Boolean get() = inFlight != null

    override fun onServiceConnected() {
        super.onServiceConnected()
        SessionController.connectAccessibility(this)
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return
        SessionController.foregroundChanged(activePackage())
    }

    override fun onInterrupt() {
        SessionController.stopRoutine("Accessibility was interrupted. Start again when ready.")
    }

    override fun onUnbind(intent: Intent?): Boolean {
        disconnect()
        return super.onUnbind(intent)
    }

    override fun onDestroy() {
        disconnect()
        super.onDestroy()
    }

    @Suppress("DEPRECATION")
    internal fun activePackage(): String? {
        if (SessionController.isLocked()) return null
        return try {
            val root = rootInActiveWindow ?: return null
            try { root.packageName?.toString() } finally {
                if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) root.recycle()
            }
        } catch (_: SecurityException) {
            null
        }
    }

    internal fun dispatchPlan(
        plan: GesturePlan,
        expectedPackage: String,
        capture: CapturedFrame,
        completion: (Boolean) -> Unit,
    ): Boolean {
        check(Looper.myLooper() == Looper.getMainLooper())
        if (inFlight != null) return refuse("A touch gesture is still finishing. Try again shortly.")
        val currentPackage = activePackage()
        SessionController.foregroundChanged(currentPackage)
        if (currentPackage != expectedPackage || !SessionController.isAllowedPackage(currentPackage)) {
            return refuse("Touch blocked because the target is not the active app.")
        }
        if (!SessionController.snapshot.captureActive || capture.sourcePackage != expectedPackage) {
            return refuse("Touch blocked because capture does not belong to the active target.")
        }
        val age = SystemClock.elapsedRealtime() - capture.gray.capturedAtMs
        if (age !in 0..1_000L) return refuse("Touch blocked because its screen capture is stale.")
        val geometry = CaptureService.displayGeometry(this)
        if (geometry.width != capture.displayWidth || geometry.height != capture.displayHeight ||
            geometry.rotation != capture.rotation
        ) return refuse("Display geometry changed. Restart capture and recalibrate.")

        val description = try {
            require(plan.strokes.isNotEmpty() && plan.strokes.size <= GestureDescription.getMaxStrokeCount())
            val builder = GestureDescription.Builder()
            plan.strokes.forEach { stroke ->
                require(stroke.startMs in 0L..750L && stroke.durationMs in 1L..750L &&
                    stroke.startMs + stroke.durationMs <= 750 && stroke.points.isNotEmpty())
                val path = Path()
                stroke.points.forEachIndexed { index, point ->
                    require(point.x.isFinite() && point.y.isFinite() &&
                        point.x in 0f..1f && point.y in 0f..1f)
                    val x = point.x * (capture.displayWidth - 1)
                    val y = point.y * (capture.displayHeight - 1)
                    if (index == 0) path.moveTo(x, y) else path.lineTo(x, y)
                }
                builder.addStroke(GestureDescription.StrokeDescription(path, stroke.startMs, stroke.durationMs))
            }
            builder.build()
        } catch (_: IllegalArgumentException) {
            return refuse("Invalid touch plan; gestures must be finite and at most 750 ms.")
        }
        val id = ++dispatchId
        inFlight = id
        pendingCompletion = completion
        val accepted = try {
            dispatchGesture(description, object : GestureResultCallback() {
                override fun onCompleted(gestureDescription: GestureDescription?) { complete(id, true) }
                override fun onCancelled(gestureDescription: GestureDescription?) { complete(id, false) }
            }, main)
        } catch (_: IllegalStateException) {
            false
        } catch (_: SecurityException) {
            false
        }
        if (!accepted) {
            inFlight = null
            pendingCompletion = null
            return refuse("Android refused the gesture. Verify accessibility is enabled.")
        }
        // Defensive callback bound. This does not manufacture a success result.
        main.postDelayed({ complete(id, false) }, 1_750L)
        return true
    }

    private fun complete(id: Long, success: Boolean) {
        if (inFlight != id) return
        val callback = pendingCompletion
        inFlight = null
        pendingCompletion = null
        callback?.invoke(success)
    }

    private fun refuse(reason: String): Boolean {
        lastDispatchFailure = reason
        return false
    }

    private fun disconnect() {
        SessionController.disconnectAccessibility(this)
        val id = inFlight
        if (id != null) complete(id, false)
        main.removeCallbacksAndMessages(null)
    }
}
