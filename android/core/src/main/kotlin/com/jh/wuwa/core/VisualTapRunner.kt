package com.jh.wuwa.core

data class TapRoutine(
    val name: String,
    val targetPackage: String,
    val template: VisualTemplate,
    val tap: NormalizedPoint = template.region.center,
    val maxTaps: Int = 1,
    val timeoutMs: Long = 60_000,
    val cooldownMs: Long = 1500,
    val matchThreshold: Double = 0.97,
    val stableFrames: Int = 3,
) {
    init {
        require(name.isNotBlank() && name.length <= 120 && name.none { it.isISOControl() }) {
            "Provide a short, non-empty routine name"
        }
        require(targetPackage.length <= 255 && PACKAGE.matches(targetPackage)) {
            "Provide a valid Android application package"
        }
        require(maxTaps in 1..50) { "A routine must allow between 1 and 50 taps" }
        require(timeoutMs in 1000L..300_000L) { "Routine timeout must be between 1 and 300 seconds" }
        require(cooldownMs in 250L..60_000L) { "Tap cooldown must be between 250 ms and 60 seconds" }
        require(matchThreshold.isFinite() && matchThreshold in 0.90..1.0) {
            "Match threshold must be between 0.90 and 1.0"
        }
        require(stableFrames in 2..10) { "Require between 2 and 10 stable frames" }
    }

    private companion object {
        val PACKAGE = Regex("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z][A-Za-z0-9_]*)+")
    }
}

sealed interface RoutineDecision {
    data object Wait : RoutineDecision
    data class Tap(val point: NormalizedPoint) : RoutineDecision
    data class Finished(val reason: String) : RoutineDecision
}

/**
 * One bounded observe/act/acknowledge cycle. A dispatched touch is not evidence
 * that a game reward was collected; completedTaps counts successful touch callbacks.
 */
class VisualTapRunner(val routine: TapRoutine, val startedAtMs: Long) {
    @Volatile
    var completedTaps: Int = 0
        private set

    @Volatile
    var message: String = "Waiting for a stable target"
        private set

    @Volatile
    var finished: Boolean = false
        private set

    // Freeze template pixels so a UI or persistence buffer cannot alter a running routine.
    private val template = routine.template.copy(samples = routine.template.samples.copyOf())
    private var lastFrameMs = -1L
    private var lastAcknowledgementMs = -1L
    private var pendingSinceMs: Long? = null
    private var matchedFrames = 0
    private var absentFrames = 0
    private var awaitingDisappearance = false

    init {
        require(startedAtMs >= 0) { "Start timestamp must be non-negative" }
    }

    @Synchronized
    fun update(
        frame: GrayFrame?,
        nowMs: Long,
        targetActive: Boolean,
        captureActive: Boolean,
    ): RoutineDecision {
        if (finished) return RoutineDecision.Finished(message)
        if (nowMs < startedAtMs) return finish("Monotonic clock changed; start a new session")
        if (!captureActive) return finish("Screen capture ended")
        if (!targetActive) return finish("Target app is no longer active")
        if (nowMs - startedAtMs >= routine.timeoutMs) return finish("Routine timed out")
        if (frame != null && (frame.width != template.frameWidth || frame.height != template.frameHeight)) {
            return finish("Capture dimensions changed; calibrate the target again")
        }

        pendingSinceMs?.let { dispatchedAt ->
            if (nowMs - dispatchedAt >= GESTURE_ACK_TIMEOUT_MS) {
                return finish("Gesture did not complete; stopped")
            }
            return RoutineDecision.Wait
        }

        if (frame == null || frame.capturedAtMs > nowMs || nowMs - frame.capturedAtMs > MAX_FRAME_AGE_MS) {
            matchedFrames = 0
            absentFrames = 0
            message = "Waiting for a fresh game frame"
            return RoutineDecision.Wait
        }
        // Polls of the same frame never increase stability, and a pre-action frame
        // cannot attest to disappearance or reappearance after the action.
        if (frame.capturedAtMs <= lastFrameMs || frame.capturedAtMs <= lastAcknowledgementMs) {
            return RoutineDecision.Wait
        }
        if (lastFrameMs >= 0 && frame.capturedAtMs - lastFrameMs > MAX_FRAME_AGE_MS) {
            // Callers may deliver only new frames, so do not rely on an intervening
            // polling tick to invalidate stability after a capture stall.
            matchedFrames = 0
            absentFrames = 0
        }
        lastFrameMs = frame.capturedAtMs
        val similarity = TemplateMatcher.similarity(frame, template)

        if (awaitingDisappearance) {
            // Hysteresis prevents tiny lighting/compression changes from rearming a tap.
            absentFrames = if (similarity < routine.matchThreshold - 0.12) absentFrames + 1 else 0
            if (absentFrames >= ABSENT_FRAMES_REQUIRED) {
                awaitingDisappearance = false
                absentFrames = 0
                matchedFrames = 0
                message = "Waiting for the target to reappear"
            } else {
                message = "Waiting for the tapped target to disappear"
            }
            return RoutineDecision.Wait
        }

        matchedFrames = if (similarity >= routine.matchThreshold) matchedFrames + 1 else 0
        if (matchedFrames < routine.stableFrames) {
            message = "Waiting for a stable target"
            return RoutineDecision.Wait
        }
        if (lastAcknowledgementMs >= 0 && nowMs - lastAcknowledgementMs < routine.cooldownMs) {
            message = "Waiting for tap cooldown"
            return RoutineDecision.Wait
        }

        pendingSinceMs = nowMs
        matchedFrames = 0
        message = "Dispatching tap ${completedTaps + 1} of ${routine.maxTaps}"
        return RoutineDecision.Tap(routine.tap)
    }

    @Synchronized
    fun acknowledgeTap(success: Boolean, nowMs: Long) {
        val dispatchedAt = pendingSinceMs ?: return
        if (finished) return
        if (nowMs < dispatchedAt || nowMs - dispatchedAt >= GESTURE_ACK_TIMEOUT_MS) {
            finish("Gesture completion arrived outside its deadline")
            return
        }
        if (nowMs - startedAtMs >= routine.timeoutMs) {
            finish("Routine timed out")
            return
        }
        pendingSinceMs = null
        if (!success) {
            finish("Gesture was cancelled or rejected")
            return
        }
        completedTaps += 1
        lastAcknowledgementMs = nowMs
        if (completedTaps >= routine.maxTaps) {
            finish("Completed $completedTaps tap${if (completedTaps == 1) "" else "s"}")
        } else {
            awaitingDisappearance = true
            absentFrames = 0
            matchedFrames = 0
            message = "Waiting for the tapped target to disappear"
        }
    }

    @Synchronized
    fun cancel(reason: String) {
        if (!finished) finish(reason.ifBlank { "Stopped by user" })
    }

    private fun finish(reason: String): RoutineDecision.Finished {
        finished = true
        pendingSinceMs = null
        message = reason
        return RoutineDecision.Finished(reason)
    }

    private companion object {
        const val MAX_FRAME_AGE_MS = 1000L
        const val GESTURE_ACK_TIMEOUT_MS = 2000L
        const val ABSENT_FRAMES_REQUIRED = 2
    }
}
