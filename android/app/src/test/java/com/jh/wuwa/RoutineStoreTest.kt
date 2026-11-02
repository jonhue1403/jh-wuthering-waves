package com.jh.wuwa

import org.json.JSONObject
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.LooperMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
@LooperMode(LooperMode.Mode.PAUSED)
class RoutineStoreTest : IsolatedAndroidTest() {
    @Test
    fun encodeDecodePreservesCalibrationAndEveryExecutionLimit() {
        val before = calibratedRoutine()
        val after = RoutineStore.decode(RoutineStore.encode(before))
        assertEquals(before.name, after.name)
        assertEquals(before.targetPackage, after.targetPackage)
        assertEquals(before.tap, after.tap)
        assertEquals(before.maxTaps, after.maxTaps)
        assertEquals(before.timeoutMs, after.timeoutMs)
        assertEquals(before.cooldownMs, after.cooldownMs)
        assertEquals(before.matchThreshold, after.matchThreshold, 0.0)
        assertEquals(before.stableFrames, after.stableFrames)
        assertEquals(before.template.region, after.template.region)
        assertEquals(before.template.frameWidth, after.template.frameWidth)
        assertEquals(before.template.frameHeight, after.template.frameHeight)
        assertEquals(before.template.sampleSize, after.template.sampleSize)
        assertArrayEquals(before.template.samples, after.template.samples)
    }

    @Test
    fun preferenceSaveLoadAndClearPreserveTheSelectedGame() {
        assertNull(RoutineStore.load(application))
        assertEquals(RoutineStore.DEFAULT_TARGET, RoutineStore.target(application))
        RoutineStore.setTarget(application, "com.example.game")
        RoutineStore.save(application, calibratedRoutine("com.example.game"))
        assertNotNull(RoutineStore.load(application))
        assertEquals("com.example.game", RoutineStore.load(application)?.targetPackage)
        RoutineStore.clear(application)
        assertNull(RoutineStore.load(application))
        assertEquals("com.example.game", RoutineStore.target(application))
    }

    @Test
    fun invalidTargetIsRejectedWithoutReplacingTheExistingSelection() {
        RoutineStore.setTarget(application, "com.example.valid")
        for (invalid in listOf("", "oneword", "com.example;input", " com.example ", "com.1invalid")) {
            rejectsCalibration { RoutineStore.setTarget(application, invalid) }
        }
        assertEquals("com.example.valid", RoutineStore.target(application))
    }

    @Test
    fun malformedOrMissingFieldsAreRejectedAndCorruptPreferenceLoadsAsAbsent() {
        for (invalid in listOf("[", "{}", "null", "[]")) {
            rejectsCalibration { RoutineStore.decode(invalid) }
        }
        application.getSharedPreferences("mobile-prototype", 0).edit()
            .putString("routine", "{broken").commit()
        assertNull(RoutineStore.load(application))
    }

    @Test
    fun unknownSchemaVersionsAreRejected() {
        val json = JSONObject(RoutineStore.encode(calibratedRoutine()))
        for (schema in listOf(0, 2, 999)) {
            json.put("schema", schema)
            rejectsCalibration { RoutineStore.decode(json.toString()) }
        }
    }

    @Test
    fun fractionalSchemaIsNotSilentlyCoercedIntoVersionOne() {
        val json = JSONObject(RoutineStore.encode(calibratedRoutine())).put("schema", 1.5)
        rejectsCalibration { RoutineStore.decode(json.toString()) }
    }

    @Test
    fun fractionalAndOverflowingActionCountsAreRejected() {
        val json = JSONObject(RoutineStore.encode(calibratedRoutine()))
        for (invalid in listOf<Number>(1.5, 4_294_967_297L, -1, 51)) {
            json.put("maxTaps", invalid)
            rejectsCalibration { RoutineStore.decode(json.toString()) }
        }
    }

    @Test
    fun oversizedPayloadIsRejectedBeforeParsingItsContent() {
        rejectsCalibration { RoutineStore.decode(" ".repeat(16_385)) }
        val json = JSONObject(RoutineStore.encode(calibratedRoutine())).put("extra", "x".repeat(16_385))
        rejectsCalibration { RoutineStore.decode(json.toString()) }
    }

    @Test
    fun malformedSampleEncodingCountAndLowContrastCalibrationAreRejected() {
        for (sampleText in listOf("%%%", "AA==", java.util.Base64.getEncoder().encodeToString(ByteArray(24 * 24)))) {
            val json = JSONObject(RoutineStore.encode(calibratedRoutine()))
            json.getJSONObject("template").put("samples", sampleText)
            rejectsCalibration { RoutineStore.decode(json.toString()) }
        }
    }

    @Test
    fun invalidExecutionAndGeometryCannotBecomeAStoredRoutine() {
        val base = RoutineStore.encode(calibratedRoutine())
        val tooPermissive = JSONObject(base).put("matchThreshold", 0.1)
        val offscreen = JSONObject(base).put("tapX", 2.0)
        val unbounded = JSONObject(base).put("timeoutMs", Long.MAX_VALUE)
        val emptyArea = JSONObject(base).apply { getJSONObject("template").put("right", 0.25) }
        for (json in listOf(tooPermissive, offscreen, unbounded, emptyArea)) {
            rejectsCalibration { RoutineStore.decode(json.toString()) }
        }
    }
}
