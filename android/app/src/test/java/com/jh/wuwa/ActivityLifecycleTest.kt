package com.jh.wuwa

import android.content.res.Configuration
import android.os.Bundle
import android.os.Looper
import com.jh.wuwa.core.NormalizedRect
import com.jh.wuwa.runtime.SessionController
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.annotation.LooperMode
import java.time.Duration

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
@LooperMode(LooperMode.Mode.PAUSED)
class ActivityLifecycleTest : IsolatedAndroidTest() {
    @Test
    @Config(qualifiers = "w411dp-h891dp-port")
    fun mainStartsInPortraitAndStopsRefreshingWhenPaused() {
        val controller = Robolectric.buildActivity(MainActivity::class.java).setup()
        var paused = false
        try {
            val activity = controller.get()
            assertEquals(Configuration.ORIENTATION_PORTRAIT, activity.resources.configuration.orientation)
            assertTrue(activityTexts(activity).contains("Run on your phone"))
            SessionController.stopRoutine("Visible session update")
            shadowOf(Looper.getMainLooper()).idle()
            assertTrue(activityTexts(activity).contains("Visible session update"))
            controller.pause()
            paused = true
            SessionController.stopRoutine("Paused activities must not refresh")
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(2))
            assertFalse(activityTexts(activity).contains("Paused activities must not refresh"))
        } finally {
            if (!paused) controller.pause()
            controller.stop().destroy()
        }
    }

    @Test
    @Config(qualifiers = "w891dp-h411dp-land")
    fun mainStartsInLandscapeAndNeverBecomesATouchTarget() {
        RoutineStore.setTarget(application, application.packageName)
        val controller = Robolectric.buildActivity(MainActivity::class.java).setup()
        try {
            val activity = controller.get()
            assertEquals(Configuration.ORIENTATION_LANDSCAPE, activity.resources.configuration.orientation)
            assertTrue(activityTexts(activity).contains("Start screen capture"))
            assertFalse(SessionController.isAllowedPackage(activity.packageName))
        } finally {
            controller.pause().stop().destroy()
        }
    }

    @Test
    @Config(qualifiers = "w411dp-h891dp-port")
    fun portraitLabEnablesOnlyItsResumedLifetimeAndCleansUpOnPause() {
        verifyLabLifecycle(Configuration.ORIENTATION_PORTRAIT)
    }

    @Test
    @Config(qualifiers = "w891dp-h411dp-land")
    fun landscapeLabStartsAndCleansUpOnPause() {
        verifyLabLifecycle(Configuration.ORIENTATION_LANDSCAPE)
    }

    private fun verifyLabLifecycle(expectedOrientation: Int) {
        val controller = Robolectric.buildActivity(TouchLabActivity::class.java).setup()
        var paused = false
        try {
            val activity = controller.get()
            assertEquals(expectedOrientation, activity.resources.configuration.orientation)
            assertTrue(activityTexts(activity).contains("Run 3 visual taps"))
            assertEquals(1, descendants(activity.window.decorView).filterIsInstance<TouchLabView>().count())
            assertTrue(SessionController.isAllowedPackage(activity.packageName))
            controller.pause()
            paused = true
            assertFalse(SessionController.isAllowedPackage(activity.packageName))
            assertFalse(SessionController.snapshot.routineRunning)
        } finally {
            if (!paused) controller.pause()
            controller.stop().destroy()
        }
        assertFalse(SessionController.isAllowedPackage(application.packageName))
    }

    @Test
    fun calibrationWithoutItsCapturedFrameFinishesInsteadOfInventingAnImage() {
        CalibrationActivity.pendingFrame = null
        val controller = Robolectric.buildActivity(CalibrationActivity::class.java).create()
        try {
            assertTrue(controller.get().isFinishing)
        } finally {
            controller.destroy()
        }
    }

    @Test
    fun calibrationRestoresSelectionAndReleasesPendingBitmapOnFinalDestroy() {
        CalibrationActivity.pendingFrame = sampleCapture(RoutineStore.DEFAULT_TARGET)
        val saved = Bundle().apply {
            putFloat("left", 0.2f); putFloat("top", 0.3f)
            putFloat("right", 0.6f); putFloat("bottom", 0.7f)
        }
        val controller = Robolectric.buildActivity(CalibrationActivity::class.java)
            .create(saved).start().resume().visible()
        try {
            val selection = descendants(controller.get().window.decorView).filterIsInstance<SelectionView>().single()
            assertEquals(NormalizedRect(0.2f, 0.3f, 0.6f, 0.7f), selection.selection)
        } finally {
            controller.pause().stop().destroy()
        }
        assertNull(CalibrationActivity.pendingFrame)
    }
}
