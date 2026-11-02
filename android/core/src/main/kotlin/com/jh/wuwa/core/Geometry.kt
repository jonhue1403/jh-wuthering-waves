package com.jh.wuwa.core

import kotlin.math.ceil
import kotlin.math.floor

/** Coordinates are relative to the complete captured display, including its insets. */
data class NormalizedPoint(val x: Float, val y: Float) {
    init {
        require(x.isFinite() && y.isFinite() && x in 0f..1f && y in 0f..1f) {
            "Touch coordinates must be finite and within the display"
        }
    }
}

data class NormalizedRect(
    val left: Float,
    val top: Float,
    val right: Float,
    val bottom: Float,
) {
    init {
        require(listOf(left, top, right, bottom).all { it.isFinite() && it in 0f..1f }) {
            "Selection coordinates must be finite and within the display"
        }
        require(left < right && top < bottom) { "Select an area with positive width and height" }
    }

    val center: NormalizedPoint
        get() = NormalizedPoint((left + right) / 2f, (top + bottom) / 2f)

    internal fun requireUsableSize(width: Int, height: Int) {
        val pixelsWide = ceil(right * width).toInt() - floor(left * width).toInt()
        val pixelsHigh = ceil(bottom * height).toInt() - floor(top * height).toInt()
        require(pixelsWide >= 8 && pixelsHigh >= 8) {
            "Select a larger target (at least 8 by 8 analysis pixels)"
        }
    }
}

internal fun requireFrameDimensions(width: Int, height: Int) {
    require(width in 1..4096 && height in 1..4096 && width.toLong() * height <= 16_777_216) {
        "Frame dimensions are outside the supported range"
    }
}
