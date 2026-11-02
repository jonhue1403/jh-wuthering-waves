package com.jh.wuwa.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class VisualTapRunnerTest {
    private fun advance(runner: VisualTapRunner, timestamp: Long, frame: GrayFrame = patternedFrame(timestamp)) =
        runner.update(frame, timestamp, targetActive = true, captureActive = true)

    private fun firstTap(runner: VisualTapRunner) {
        assertEquals(RoutineDecision.Wait, advance(runner, 100))
        assertEquals(RoutineDecision.Wait, advance(runner, 200))
        assertTrue(advance(runner, 300) is RoutineDecision.Tap)
    }

    @Test
    fun onlyDistinctStableFramesDispatchOnePendingTap() {
        val runner = VisualTapRunner(routine(), 0)
        assertEquals(RoutineDecision.Wait, advance(runner, 100))
        assertEquals(RoutineDecision.Wait, advance(runner, 200))
        assertEquals(RoutineDecision.Wait, runner.update(patternedFrame(150), 250, true, true))
        assertEquals(RoutineDecision.Wait, runner.update(patternedFrame(200), 260, true, true))
        assertTrue(advance(runner, 300) is RoutineDecision.Tap)
        assertEquals(RoutineDecision.Wait, advance(runner, 400))
        assertEquals(0, runner.completedTaps)
    }

    @Test
    fun successfulAcknowledgementCountsTheTouchAndEndsAtTheLimit() {
        val runner = VisualTapRunner(routine(), 0)
        firstTap(runner)
        runner.acknowledgeTap(true, 400)
        assertEquals(1, runner.completedTaps)
        assertTrue(runner.finished)
        assertEquals("Completed 1 tap", runner.message)
        assertTrue(advance(runner, 500) is RoutineDecision.Finished)
        runner.acknowledgeTap(true, 550)
        assertEquals(1, runner.completedTaps)
    }

    @Test
    fun matchingFramesMustBeConsecutive() {
        val runner = VisualTapRunner(routine(), 0)
        advance(runner, 100)
        advance(runner, 200, absentFrame(200))
        assertEquals(RoutineDecision.Wait, advance(runner, 300))
        assertEquals(RoutineDecision.Wait, advance(runner, 400))
        assertTrue(advance(runner, 500) is RoutineDecision.Tap)
    }

    @Test
    fun staleFutureAndMissingFramesCannotCompleteAStableSequence() {
        val runner = VisualTapRunner(routine(), 0)
        advance(runner, 100)
        advance(runner, 200)
        assertEquals(RoutineDecision.Wait, runner.update(patternedFrame(200), 1201, true, true))
        assertEquals(RoutineDecision.Wait, runner.update(patternedFrame(2000), 1202, true, true))
        assertEquals(RoutineDecision.Wait, runner.update(null, 1203, true, true))
        assertEquals(RoutineDecision.Wait, advance(runner, 1300))
        assertEquals(RoutineDecision.Wait, advance(runner, 1400))
        assertTrue(advance(runner, 1500) is RoutineDecision.Tap)
    }

    @Test
    fun stabilityDoesNotSurviveALongGapBetweenOtherwiseFreshFrames() {
        val runner = VisualTapRunner(routine(), 0)
        advance(runner, 100)
        advance(runner, 200)
        assertEquals(RoutineDecision.Wait, advance(runner, 5000))
        assertEquals(RoutineDecision.Wait, advance(runner, 5100))
        assertTrue(advance(runner, 5200) is RoutineDecision.Tap)
    }

    @Test
    fun unchangedAppearanceNeverTriggersAnotherTap() {
        val runner = VisualTapRunner(routine(maxTaps = 3), 0)
        firstTap(runner)
        runner.acknowledgeTap(true, 350)
        for (time in 400L..6000L step 100) assertEquals(RoutineDecision.Wait, advance(runner, time))
        assertEquals(1, runner.completedTaps)
        assertFalse(runner.finished)
    }

    @Test
    fun absenceDuringCooldownIsRememberedAndReappearanceMustBeStable() {
        val runner = VisualTapRunner(routine(maxTaps = 2), 0)
        firstTap(runner)
        runner.acknowledgeTap(true, 350)
        advance(runner, 400, absentFrame(400))
        advance(runner, 500, absentFrame(500))
        assertEquals(RoutineDecision.Wait, advance(runner, 600))
        assertEquals(RoutineDecision.Wait, advance(runner, 700))
        assertEquals(RoutineDecision.Wait, advance(runner, 800))
        assertEquals(RoutineDecision.Wait, advance(runner, 1800))
        assertTrue(advance(runner, 1900) is RoutineDecision.Tap)
        runner.acknowledgeTap(true, 2000)
        assertTrue(runner.finished)
        assertEquals(2, runner.completedTaps)
    }

    @Test
    fun preAcknowledgementAndDuplicateAbsentFramesCannotRearm() {
        val runner = VisualTapRunner(routine(maxTaps = 2), 0)
        firstTap(runner)
        runner.acknowledgeTap(true, 350)
        runner.update(absentFrame(340), 400, true, true)
        runner.update(absentFrame(400), 500, true, true)
        runner.update(absentFrame(400), 600, true, true)
        for (time in 700L..2500L step 100) assertEquals(RoutineDecision.Wait, advance(runner, time))
        assertEquals(1, runner.completedTaps)
    }

    @Test
    fun smallVisualMismatchDoesNotCountAsDisappearance() {
        val runner = VisualTapRunner(routine(maxTaps = 2), 0)
        firstTap(runner)
        runner.acknowledgeTap(true, 350)
        advance(runner, 400, patternedFrame(400, offset = 10))
        advance(runner, 500, patternedFrame(500, offset = 10))
        for (time in 600L..2500L step 100) assertEquals(RoutineDecision.Wait, advance(runner, time))
        assertEquals(1, runner.completedTaps)
    }

    @Test
    fun focusLossStopsEvenWhileGestureAcknowledgementIsPending() {
        val runner = VisualTapRunner(routine(maxTaps = 2), 0)
        firstTap(runner)
        assertTrue(runner.update(patternedFrame(400), 400, false, true) is RoutineDecision.Finished)
        runner.acknowledgeTap(true, 450)
        assertEquals(0, runner.completedTaps)
        assertTrue(advance(runner, 500) is RoutineDecision.Finished)
        assertTrue(runner.message.contains("no longer active"))
    }

    @Test
    fun captureLossStopsWithoutAutomaticRecovery() {
        val runner = VisualTapRunner(routine(), 0)
        advance(runner, 100)
        assertTrue(runner.update(null, 200, true, false) is RoutineDecision.Finished)
        assertTrue(advance(runner, 300) is RoutineDecision.Finished)
        assertEquals("Screen capture ended", runner.message)
    }

    @Test
    fun dimensionChangeStopsEvenWhileTapIsPending() {
        val runner = VisualTapRunner(routine(), 0)
        firstTap(runner)
        assertTrue(advance(runner, 400, patternedFrame(400, width = 192)) is RoutineDecision.Finished)
        runner.acknowledgeTap(true, 450)
        assertEquals(0, runner.completedTaps)
        assertTrue(runner.message.contains("dimensions changed"))
    }

    @Test
    fun timeoutIsTerminalEvenWithoutFreshFrames() {
        val runner = VisualTapRunner(routine().copy(timeoutMs = 1000), 0)
        assertTrue(runner.update(null, 1000, true, true) is RoutineDecision.Finished)
        assertEquals("Routine timed out", runner.message)
    }

    @Test
    fun missingOrLateGestureAcknowledgementStopsTheRoutine() {
        val missing = VisualTapRunner(routine(), 0)
        firstTap(missing)
        assertTrue(advance(missing, 2300) is RoutineDecision.Finished)
        assertEquals(0, missing.completedTaps)
        val late = VisualTapRunner(routine(), 0)
        firstTap(late)
        late.acknowledgeTap(true, 2300)
        assertTrue(late.finished)
        assertEquals(0, late.completedTaps)
    }

    @Test
    fun cancelledOrRefusedGestureIsNotCountedAsCompleted() {
        val runner = VisualTapRunner(routine(), 0)
        firstTap(runner)
        runner.acknowledgeTap(false, 350)
        assertTrue(runner.finished)
        assertEquals(0, runner.completedTaps)
        assertEquals("Gesture was cancelled or rejected", runner.message)
    }

    @Test
    fun cancelIgnoresLateCompletionAndCannotBeResumed() {
        val runner = VisualTapRunner(routine(maxTaps = 2), 0)
        firstTap(runner)
        runner.cancel("Screen locked")
        runner.acknowledgeTap(true, 400)
        runner.cancel("Later callback")
        assertEquals("Screen locked", runner.message)
        assertEquals(0, runner.completedTaps)
        assertTrue(advance(runner, 500) is RoutineDecision.Finished)
    }

    @Test
    fun unsolicitedAcknowledgementHasNoEffect() {
        val runner = VisualTapRunner(routine(), 0)
        runner.acknowledgeTap(true, 100)
        assertFalse(runner.finished)
        assertEquals(0, runner.completedTaps)
    }

    @Test
    fun clockRegressionCannotDispatchOrAcceptAnAcknowledgement() {
        val runner = VisualTapRunner(routine(), 1000)
        assertTrue(runner.update(patternedFrame(100), 100, true, true) is RoutineDecision.Finished)
        val pending = VisualTapRunner(routine(), 0)
        firstTap(pending)
        pending.acknowledgeTap(true, 299)
        assertTrue(pending.finished)
        assertEquals(0, pending.completedTaps)
    }

    @Test
    fun runningCalibrationIsIndependentOfTheCallersMutableBuffer() {
        val spec = routine()
        val runner = VisualTapRunner(spec, 0)
        spec.template.samples.fill(0)
        firstTap(runner)
    }

    @Test
    fun malformedOrUnboundedRoutinesAreRejected() {
        val valid = routine()
        rejects { valid.copy(name = " ") }
        rejects { valid.copy(name = "Line\nbreak") }
        rejects { valid.copy(targetPackage = "not a package") }
        rejects { valid.copy(targetPackage = "com.example;input") }
        rejects { valid.copy(maxTaps = 0) }
        rejects { valid.copy(maxTaps = 51) }
        rejects { valid.copy(timeoutMs = Long.MAX_VALUE) }
        rejects { valid.copy(timeoutMs = 999) }
        rejects { valid.copy(cooldownMs = 0) }
        rejects { valid.copy(cooldownMs = 60_001) }
        rejects { valid.copy(matchThreshold = Double.NaN) }
        rejects { valid.copy(matchThreshold = 0.1) }
        rejects { valid.copy(stableFrames = 1) }
        rejects { valid.copy(stableFrames = Int.MAX_VALUE) }
        rejects { VisualTapRunner(valid, -1) }
    }
}
