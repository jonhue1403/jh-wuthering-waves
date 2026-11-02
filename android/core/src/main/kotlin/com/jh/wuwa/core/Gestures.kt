package com.jh.wuwa.core

data class TouchStroke(
    val points: List<NormalizedPoint>,
    val startMs: Long,
    val durationMs: Long,
) {
    init {
        require(points.size in 1..32) { "A touch stroke must have between 1 and 32 points" }
        require(startMs in 0L..749L && durationMs in 1L..750L && durationMs <= 750L - startMs) {
            "Every gesture must finish within 750 ms"
        }
    }
}

/** All strokes are submitted together so a tap does not cancel a simultaneous drag. */
data class GesturePlan(val strokes: List<TouchStroke>) {
    init {
        require(strokes.size in 1..5) { "A gesture must contain between 1 and 5 touch strokes" }
        require(strokes.sumOf { it.points.size } <= 64) { "Gesture contains too many path points" }
    }
}

object GesturePresets {
    fun tap(point: NormalizedPoint): GesturePlan =
        GesturePlan(listOf(TouchStroke(listOf(point), startMs = 0, durationMs = 80)))

    fun swipe(
        from: NormalizedPoint,
        to: NormalizedPoint,
        durationMs: Long = 500,
    ): GesturePlan = GesturePlan(listOf(TouchStroke(listOf(from, to), 0, durationMs)))

    fun moveAndTap(
        from: NormalizedPoint,
        to: NormalizedPoint,
        attack: NormalizedPoint,
    ): GesturePlan = GesturePlan(
        listOf(
            TouchStroke(listOf(from, to), startMs = 0, durationMs = 600),
            TouchStroke(listOf(attack), startMs = 250, durationMs = 80),
        ),
    )
}
