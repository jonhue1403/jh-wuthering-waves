package com.jh.wuwa.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class GeometryAndVisionTest {
    @Test
    fun normalizedCoordinatesRejectNonFiniteAndOffscreenValues() {
        for (invalid in listOf(Float.NaN, Float.POSITIVE_INFINITY, Float.NEGATIVE_INFINITY, -0.01f, 1.01f)) {
            rejects { NormalizedPoint(invalid, 0.5f) }
            rejects { NormalizedPoint(0.5f, invalid) }
        }
        assertEquals(NormalizedPoint(0f, 1f), NormalizedPoint(0f, 1f))
    }

    @Test
    fun rectanglesRequirePositiveFiniteDimensionsAndProvideCenter() {
        rejects { NormalizedRect(0.5f, 0f, 0.5f, 1f) }
        rejects { NormalizedRect(0f, 0.8f, 1f, 0.5f) }
        rejects { NormalizedRect(Float.NaN, 0f, 1f, 1f) }
        rejects { NormalizedRect(0f, 0f, 2f, 1f) }
        assertEquals(NormalizedPoint(0.5f, 0.5f), testRegion.center)
    }

    @Test
    fun frameRejectsIncompletePixelsNegativeTimeAndOversizedDimensions() {
        rejects { GrayFrame(0, 2, byteArrayOf(), 0) }
        rejects { GrayFrame(2, 2, byteArrayOf(1), 0) }
        rejects { GrayFrame(1, 1, byteArrayOf(1), -1) }
        rejects { GrayFrame(Int.MAX_VALUE, Int.MAX_VALUE, byteArrayOf(), 0) }
        rejects { GrayFrame(4097, 1, ByteArray(4097), 0) }
    }

    @Test
    fun identicalTargetScoresOneAndCaptureOwnsItsSampleBuffer() {
        val frame = patternedFrame(100)
        val template = TemplateMatcher.capture(frame, testRegion)
        assertEquals(1.0, TemplateMatcher.similarity(patternedFrame(200), template), 1e-9)
        frame.pixels.fill(0)
        assertEquals(1.0, TemplateMatcher.similarity(patternedFrame(300), template), 1e-9)
    }

    @Test
    fun matchingIgnoresPixelsOutsideTheSelectedRegion() {
        val original = patternedFrame(100)
        val template = TemplateMatcher.capture(original, testRegion)
        val changed = patternedFrame(200)
        for (y in 0 until changed.height) {
            for (x in 0 until changed.width) {
                if (x < 24 || x >= 72 || y < 16 || y >= 48) {
                    changed.pixels[y * changed.width + x] = 255.toByte()
                }
            }
        }
        assertEquals(1.0, TemplateMatcher.similarity(changed, template), 1e-9)
    }

    @Test
    fun flatInvertedAndDifferentPatternsDoNotPassAsTheTarget() {
        val template = TemplateMatcher.capture(patternedFrame(100), testRegion)
        assertEquals(0.0, TemplateMatcher.similarity(absentFrame(200), template), 0.0)
        val inverted = patternedFrame(200)
        for (index in inverted.pixels.indices) {
            inverted.pixels[index] = (255 - (inverted.pixels[index].toInt() and 0xff)).toByte()
        }
        assertTrue(TemplateMatcher.similarity(inverted, template) < 0.1)
        val stripes = GrayFrame(96, 64, ByteArray(96 * 64) {
            if ((it / 96 / 4) % 2 == 0) 40 else 210.toByte()
        }, 200)
        assertTrue(TemplateMatcher.similarity(stripes, template) < 0.9)
    }

    @Test
    fun smallLuminanceVariationIsToleratedButLargeChangesAreNot() {
        val template = TemplateMatcher.capture(patternedFrame(100), testRegion)
        assertTrue(TemplateMatcher.similarity(patternedFrame(200, offset = 2), template) > 0.97)
        assertTrue(TemplateMatcher.similarity(patternedFrame(200, offset = 20), template) < 0.97)
    }

    @Test
    fun flatOrTinyCalibrationIsRejectedIncludingImportedSamples() {
        rejects { TemplateMatcher.capture(absentFrame(0), testRegion) }
        rejects { TemplateMatcher.capture(patternedFrame(0), NormalizedRect(0f, 0f, 0.03f, 0.03f)) }
        rejects { VisualTemplate(testRegion, 96, 64, ByteArray(24 * 24) { 20 }) }
        rejects { VisualTemplate(testRegion, 96, 64, byteArrayOf(20)) }
        rejects { TemplateMatcher.capture(patternedFrame(0), testRegion, 65) }
        rejects { TemplateMatcher.capture(patternedFrame(0), testRegion, 0) }
    }

    @Test
    fun changedFrameGeometryRequiresNewCalibration() {
        val template = TemplateMatcher.capture(patternedFrame(0), testRegion)
        rejects { TemplateMatcher.similarity(patternedFrame(100, width = 192), template) }
        rejects { TemplateMatcher.similarity(patternedFrame(100, width = 64, height = 96), template) }
    }

    @Test
    fun similarityIsFiniteAndBoundedForUnsignedPixelValues() {
        val template = TemplateMatcher.capture(patternedFrame(0), testRegion)
        val noisy = GrayFrame(96, 64, ByteArray(96 * 64) { ((it * 73 + 19) % 256).toByte() }, 100)
        val result = TemplateMatcher.similarity(noisy, template)
        assertFalse(result.isNaN())
        assertTrue(result in 0.0..1.0)
    }
}
