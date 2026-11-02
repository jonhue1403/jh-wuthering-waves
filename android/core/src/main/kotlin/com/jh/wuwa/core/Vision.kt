package com.jh.wuwa.core

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/** An immutable-by-convention unsigned 8-bit luminance image, timestamped using elapsed time. */
data class GrayFrame(
    val width: Int,
    val height: Int,
    val pixels: ByteArray,
    val capturedAtMs: Long,
) {
    init {
        requireFrameDimensions(width, height)
        require(pixels.size.toLong() == width.toLong() * height) { "Incomplete frame pixels" }
        require(capturedAtMs >= 0) { "Frame timestamp must be non-negative" }
    }
}

data class VisualTemplate(
    val region: NormalizedRect,
    val frameWidth: Int,
    val frameHeight: Int,
    val samples: ByteArray,
    val sampleSize: Int = 24,
) {
    init {
        requireFrameDimensions(frameWidth, frameHeight)
        region.requireUsableSize(frameWidth, frameHeight)
        require(sampleSize in 8..64) { "Template sample size must be between 8 and 64" }
        require(samples.size == sampleSize * sampleSize) { "Incomplete template samples" }
        val stats = statistics(samples)
        require(stats.standardDeviation >= 12.0 && stats.range >= 32) {
            "The selection has too little contrast; include a distinctive icon or text"
        }
    }
}

/**
 * Conservative matching at the user's calibrated position. This is an image
 * similarity measurement, not a probability or general-purpose game recognizer.
 */
object TemplateMatcher {
    fun capture(frame: GrayFrame, region: NormalizedRect, sampleSize: Int = 24): VisualTemplate {
        require(sampleSize in 8..64) { "Template sample size must be between 8 and 64" }
        region.requireUsableSize(frame.width, frame.height)
        return VisualTemplate(
            region, frame.width, frame.height,
            sample(frame, region, sampleSize), sampleSize,
        )
    }

    fun similarity(frame: GrayFrame, template: VisualTemplate): Double {
        require(frame.width == template.frameWidth && frame.height == template.frameHeight) {
            "Capture dimensions changed; calibrate the target again"
        }
        val observed = sample(frame, template.region, template.sampleSize)
        val referenceStats = statistics(template.samples)
        val observedStats = statistics(observed)
        // A flat image must not resemble a sparse, mostly-flat button template.
        if (observedStats.standardDeviation < 4.0 || referenceStats.standardDeviation < 12.0) return 0.0

        var absoluteDifference = 0.0
        var covariance = 0.0
        for (index in observed.indices) {
            val actual = observed[index].toInt() and 0xff
            val expected = template.samples[index].toInt() and 0xff
            absoluteDifference += abs(actual - expected)
            covariance += (actual - observedStats.mean) * (expected - referenceStats.mean)
        }
        val intensityAgreement = 1.0 - absoluteDifference / (observed.size * 255.0)
        val correlation = covariance / (
            observed.size * observedStats.standardDeviation * referenceStats.standardDeviation
        )
        val patternAgreement = (correlation.coerceIn(-1.0, 1.0) + 1.0) / 2.0
        return min(intensityAgreement, patternAgreement).coerceIn(0.0, 1.0)
    }

    private fun sample(frame: GrayFrame, region: NormalizedRect, size: Int): ByteArray {
        val result = ByteArray(size * size)
        for (row in 0 until size) {
            val y = ((region.top + (row + 0.5f) / size * (region.bottom - region.top)) * frame.height)
                .toInt().coerceIn(0, frame.height - 1)
            for (column in 0 until size) {
                val x = ((region.left + (column + 0.5f) / size * (region.right - region.left)) * frame.width)
                    .toInt().coerceIn(0, frame.width - 1)
                result[row * size + column] = frame.pixels[y * frame.width + x]
            }
        }
        return result
    }
}

private data class SampleStatistics(val mean: Double, val standardDeviation: Double, val range: Int)

private fun statistics(samples: ByteArray): SampleStatistics {
    var sum = 0.0
    var sumSquares = 0.0
    var minimum = 255
    var maximum = 0
    for (sample in samples) {
        val value = sample.toInt() and 0xff
        sum += value
        sumSquares += value * value
        minimum = min(minimum, value)
        maximum = max(maximum, value)
    }
    val mean = sum / samples.size
    val variance = max(0.0, sumSquares / samples.size - mean * mean)
    return SampleStatistics(mean, sqrt(variance), maximum - minimum)
}
