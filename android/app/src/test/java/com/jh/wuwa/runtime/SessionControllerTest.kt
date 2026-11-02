package com.jh.wuwa.runtime

import android.os.Looper
import com.jh.wuwa.IsolatedAndroidTest
import com.jh.wuwa.calibratedRoutine
import com.jh.wuwa.core.GesturePresets
import com.jh.wuwa.core.NormalizedPoint
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.annotation.LooperMode
import java.time.Duration

/** Coordinator tests simulate availability states; they do not attest to OS touch injection. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
@LooperMode(LooperMode.Mode.PAUSED)
class SessionControllerTest : IsolatedAndroidTest() {
    @Test
    fun routineAndManualTouchRequireUserGrantedCapture() {
        SessionController.startRoutine(application, calibratedRoutine())
        assertFalse(SessionController.snapshot.routineRunning)
        assertTrue(SessionController.snapshot.status.contains("Start screen capture"))
        assertFalse(SessionController.requestGesture(GesturePresets.tap(NormalizedPoint(0.5f, 0.5f))))
        assertEquals(0, SessionController.snapshot.taps)
    }

    @Test
    fun captureAloneCannotRunATaskWithoutAccessibility() {
        SessionController.captureStarted()
        SessionController.startRoutine(application, calibratedRoutine())
        assertFalse(SessionController.snapshot.routineRunning)
        assertTrue(SessionController.snapshot.status.contains("accessibility"))
        assertFalse(SessionController.requestGesture(GesturePresets.tap(NormalizedPoint(0.5f, 0.5f))))
        assertEquals(0, SessionController.snapshot.taps)
    }

    @Test
    fun choosingTheCompanionPackageNeverAllowsItsMainScreen() {
        SessionController.configure(application, application.packageName)
        SessionController.foregroundChanged(application.packageName)
        assertFalse(SessionController.isAllowedPackage(application.packageName))
        assertFalse(SessionController.snapshot.targetActive)
        SessionController.setLabActive(true)
        assertTrue(SessionController.isAllowedPackage(application.packageName))
        SessionController.setLabActive(false)
        assertFalse(SessionController.isAllowedPackage(application.packageName))
        assertFalse(SessionController.snapshot.targetActive)
    }

    @Test
    fun unrelatedAppsAndMissingWindowsAreNeverAllowedTargets() {
        SessionController.configure(application, "com.example.game")
        assertTrue(SessionController.isAllowedPackage("com.example.game"))
        assertFalse(SessionController.isAllowedPackage("com.example.other"))
        assertFalse(SessionController.isAllowedPackage(null))
        assertFalse(SessionController.isAllowedPackage(application.packageName))
    }

    @Test
    fun aConnectedServiceWithoutAnActiveWindowCannotProduceInput() {
        val service = Robolectric.buildService(AutomationAccessibilityService::class.java).create()
        try {
            SessionController.connectAccessibility(service.get())
            SessionController.captureStarted()
            assertTrue(SessionController.snapshot.accessibilityConnected)
            assertFalse(SessionController.requestGesture(GesturePresets.tap(NormalizedPoint(0.5f, 0.5f))))
            SessionController.startRoutine(application, calibratedRoutine())
            assertTrue(SessionController.snapshot.routineRunning)
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(11))
            assertFalse(SessionController.snapshot.routineRunning)
            assertEquals(0, SessionController.snapshot.taps)
            assertFalse(service.get().isGestureInFlight)
            assertTrue(SessionController.snapshot.status.contains("10 seconds"))
        } finally {
            service.destroy()
        }
        assertFalse(SessionController.snapshot.accessibilityConnected)
    }

    @Test
    fun captureRevocationStopsAnArmedRoutineAndDoesNotAutoResume() {
        val service = Robolectric.buildService(AutomationAccessibilityService::class.java).create()
        try {
            SessionController.connectAccessibility(service.get())
            SessionController.captureStarted()
            SessionController.startRoutine(application, calibratedRoutine())
            assertTrue(SessionController.snapshot.routineRunning)
            SessionController.captureStopped("User revoked screen sharing")
            assertFalse(SessionController.snapshot.routineRunning)
            SessionController.captureStarted()
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(500))
            assertFalse(SessionController.snapshot.routineRunning)
            assertEquals(0, SessionController.snapshot.taps)
        } finally {
            service.destroy()
        }
    }

    @Test
    fun leavingLabCancelsAnArmedRoutineBeforeItsFirstFrameAndReentryDoesNotResume() {
        val service = Robolectric.buildService(AutomationAccessibilityService::class.java).create()
        try {
            SessionController.connectAccessibility(service.get())
            SessionController.captureStarted()
            SessionController.setLabActive(true)
            SessionController.startRoutine(application, calibratedRoutine(application.packageName))
            assertTrue("The lab routine should be waiting for its first frame", SessionController.snapshot.routineRunning)
            assertEquals(0L, SessionController.snapshot.frameCount)

            SessionController.setLabActive(false)
            assertFalse("Leaving the lab must cancel even an armed routine", SessionController.snapshot.routineRunning)
            assertTrue(SessionController.snapshot.status.contains("left the foreground"))

            SessionController.setLabActive(true)
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(500))
            assertFalse("Reentering the lab needs a new explicit start", SessionController.snapshot.routineRunning)
            assertFalse(service.get().isGestureInFlight)
            assertEquals(0, SessionController.snapshot.taps)
        } finally {
            SessionController.setLabActive(false)
            service.destroy()
        }
    }

    @Test
    fun reportExplicitlySeparatesDiagnosticsFromGameplayEvidence() {
        val report = JSONObject(SessionController.exportReport())
        assertEquals(1, report.getInt("schemaVersion"))
        assertEquals("NOT_ATTESTED", report.getString("physicalGameValidation"))
        assertFalse(report.getBoolean("containsScreenshots"))
        assertFalse(report.getJSONObject("session").getBoolean("routineRunning"))
        assertTrue(report.getString("evidenceScope").contains("not proof"))
    }
}
