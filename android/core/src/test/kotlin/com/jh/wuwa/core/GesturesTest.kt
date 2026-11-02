package com.jh.wuwa.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class GesturesTest {
    private val from = NormalizedPoint(0.2f, 0.7f)
    private val to = NormalizedPoint(0.2f, 0.5f)
    private val attack = NormalizedPoint(0.8f, 0.7f)

    @Test
    fun tapAndSwipeAreBoundedFiniteGestures() {
        val tap = GesturePresets.tap(attack)
        assertEquals(1, tap.strokes.size)
        assertEquals(listOf(attack), tap.strokes.single().points)
        assertTrue(tap.strokes.single().durationMs in 1L..750L)
        val swipe = GesturePresets.swipe(from, to)
        assertEquals(listOf(from, to), swipe.strokes.single().points)
        assertEquals(500L, swipe.strokes.single().durationMs)
    }

    @Test
    fun simultaneousMovementAndAttackAreOnePlanWithOverlappingStrokes() {
        val plan = GesturePresets.moveAndTap(from, to, attack)
        assertEquals(2, plan.strokes.size)
        val movement = plan.strokes[0]
        val tap = plan.strokes[1]
        assertTrue(tap.startMs > movement.startMs)
        assertTrue(tap.startMs + tap.durationMs < movement.startMs + movement.durationMs)
        assertTrue(plan.strokes.all { it.startMs + it.durationMs <= 750 })
    }

    @Test
    fun invalidOrOverflowingStrokeTimingIsRejected() {
        rejects { TouchStroke(listOf(from), -1, 10) }
        rejects { TouchStroke(listOf(from), 0, 0) }
        rejects { TouchStroke(listOf(from), 0, 751) }
        rejects { TouchStroke(listOf(from), 749, 2) }
        rejects { TouchStroke(listOf(from), Long.MAX_VALUE, Long.MAX_VALUE) }
        rejects { GesturePresets.swipe(from, to, Long.MAX_VALUE) }
        assertEquals(750L, TouchStroke(listOf(from), 749, 1).let { it.startMs + it.durationMs })
    }

    @Test
    fun emptyAndOversizedPointerPlansAreRejected() {
        rejects { TouchStroke(emptyList(), 0, 1) }
        rejects { TouchStroke(List(33) { from }, 0, 1) }
        rejects { GesturePlan(emptyList()) }
        rejects { GesturePlan(List(6) { TouchStroke(listOf(from), 0, 1) }) }
        rejects { GesturePlan(List(3) { TouchStroke(List(32) { from }, 0, 1) }) }
    }
}
