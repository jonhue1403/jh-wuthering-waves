package com.jh.wuwa.core

internal val testRegion = NormalizedRect(0.25f, 0.25f, 0.75f, 0.75f)

internal fun patternedFrame(
    timestamp: Long,
    width: Int = 96,
    height: Int = 64,
    offset: Int = 0,
): GrayFrame = GrayFrame(
    width, height,
    ByteArray(width * height) { index ->
        val x = index % width
        val y = index / width
        (((if ((x / 4 + y / 4) % 2 == 0) 40 else 210) + offset).coerceIn(0, 255)).toByte()
    },
    timestamp,
)

internal fun absentFrame(timestamp: Long): GrayFrame =
    GrayFrame(96, 64, ByteArray(96 * 64) { 80 }, timestamp)

internal fun routine(maxTaps: Int = 1): TapRoutine = TapRoutine(
    name = "Calibrated test target",
    targetPackage = "com.jh.wuwa.mobile",
    template = TemplateMatcher.capture(patternedFrame(0), testRegion),
    maxTaps = maxTaps,
)

internal inline fun rejects(block: () -> Unit) {
    try {
        block()
        org.junit.Assert.fail("Expected invalid input to be rejected")
    } catch (_: IllegalArgumentException) {
        // Expected public input-validation failure.
    }
}
