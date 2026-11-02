package com.jh.wuwa

import android.app.Activity
import android.app.Application
import android.graphics.Bitmap
import android.os.Looper
import android.os.SystemClock
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import com.jh.wuwa.core.GrayFrame
import com.jh.wuwa.core.NormalizedPoint
import com.jh.wuwa.core.NormalizedRect
import com.jh.wuwa.core.TapRoutine
import com.jh.wuwa.core.TemplateMatcher
import com.jh.wuwa.runtime.CapturedFrame
import com.jh.wuwa.runtime.SessionController
import org.junit.After
import org.junit.Assert.assertFalse
import org.junit.Before
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import java.time.Duration

/** Each test clears preference and coordinator state rather than depending on test order. */
abstract class IsolatedAndroidTest {
    protected val application: Application get() = RuntimeEnvironment.getApplication()

    @Before
    fun clearBeforeTest() {
        clearSession()
        application.getSharedPreferences("mobile-prototype", 0).edit().clear().commit()
        CalibrationActivity.pendingFrame = null
    }

    @After
    fun clearAfterTest() {
        clearSession()
        application.getSharedPreferences("mobile-prototype", 0).edit().clear().commit()
        CalibrationActivity.pendingFrame = null
    }

    private fun clearSession() {
        SessionController.setLabActive(false)
        SessionController.configure(application, SessionController.DEFAULT_TARGET)
        // Reset the published frame through the production capture lifecycle. No
        // real projection or service is started by these coordinator unit tests.
        SessionController.captureStarted()
        SessionController.captureStopped("Test session reset")
        SessionController.foregroundChanged(null)
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(200))
        assertFalse("A previous test left accessibility connected", SessionController.snapshot.accessibilityConnected)
        assertFalse(SessionController.snapshot.captureActive)
        assertFalse(SessionController.snapshot.routineRunning)
    }
}

internal fun calibratedRoutine(target: String = RoutineStore.DEFAULT_TARGET): TapRoutine {
    val image = sampleFrame()
    return TapRoutine(
        name = "领取 · Menu button",
        targetPackage = target,
        template = TemplateMatcher.capture(image, NormalizedRect(0.25f, 0.25f, 0.75f, 0.75f)),
        tap = NormalizedPoint(0.52f, 0.49f),
        maxTaps = 7,
        timeoutMs = 123_000,
        cooldownMs = 2750,
        matchThreshold = 0.985,
        stableFrames = 4,
    )
}

internal fun sampleFrame(): GrayFrame = GrayFrame(
    96, 64,
    ByteArray(96 * 64) { if ((it % 96 / 4 + it / 96 / 4) % 2 == 0) 40 else 210.toByte() },
    SystemClock.elapsedRealtime(),
)

internal fun sampleCapture(target: String): CapturedFrame {
    val gray = sampleFrame()
    val bitmap = Bitmap.createBitmap(gray.width, gray.height, Bitmap.Config.ARGB_8888)
    for (y in 0 until gray.height) for (x in 0 until gray.width) {
        val value = gray.pixels[y * gray.width + x].toInt() and 255
        bitmap.setPixel(x, y, android.graphics.Color.rgb(value, value, value))
    }
    return CapturedFrame(bitmap, gray, 960, 640, 0, target)
}

internal fun descendants(view: View): Sequence<View> = sequence {
    yield(view)
    if (view is ViewGroup) {
        for (index in 0 until view.childCount) yieldAll(descendants(view.getChildAt(index)))
    }
}

internal fun activityTexts(activity: Activity): List<String> =
    descendants(activity.window.decorView).filterIsInstance<TextView>().map { it.text.toString() }.toList()

internal inline fun rejectsCalibration(block: () -> Unit) {
    try {
        block()
        org.junit.Assert.fail("Malformed calibration must be rejected")
    } catch (_: IllegalArgumentException) {
        // Bounds or format validation.
    } catch (_: org.json.JSONException) {
        // Invalid JSON, a missing field, or an incompatible field type.
    }
}
