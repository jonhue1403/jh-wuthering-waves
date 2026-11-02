package com.jh.wuwa

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.media.projection.MediaProjectionConfig
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.text.InputType
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import com.jh.wuwa.runtime.CaptureService
import com.jh.wuwa.runtime.SessionController

class MainActivity : Activity() {
    private lateinit var status: TextView
    private lateinit var metrics: TextView
    private lateinit var controls: TextView
    private lateinit var calibration: TextView
    private lateinit var target: EditText
    private lateinit var repetitions: EditText
    private val handler = Handler(Looper.getMainLooper())
    private val listener: () -> Unit = { refresh() }
    private val refreshTick = object : Runnable {
        override fun run() { refresh(); handler.postDelayed(this, 1000) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        SessionController.configure(this, RoutineStore.target(this))
        val scroll = ScrollView(this).apply { setBackgroundColor(Ui.background); isFillViewport = true }
        val page = Ui.column(this, 22)
        scroll.addView(page)
        page.addView(Ui.label(this, "JH  /  WUWA MOBILE", 12f, Ui.accent, true))
        Ui.gap(page, 14)
        page.addView(Ui.label(this, "Run on your phone", 30f, bold = true))
        Ui.gap(page, 8)
        page.addView(Ui.label(this, "Capture, calibrate, then test a routine. Your PC can stay off.", color = Ui.muted))
        Ui.gap(page, 18)

        val session = Ui.panel(this)
        session.addView(Ui.label(this, "SESSION", 11f, Ui.accent, true))
        status = Ui.label(this, "Ready for setup", 19f, bold = true)
        metrics = Ui.label(this, "", 13f, Ui.muted)
        session.addView(status); Ui.gap(session, 8); session.addView(metrics)
        session.addView(Ui.button(this, "Stop routine") { SessionController.stopRoutine() })
        page.addView(session)

        val setup = Ui.panel(this)
        setup.addView(Ui.label(this, "01  ·  Connect controls", 19f, bold = true))
        controls = Ui.label(this, "", 14f, Ui.muted)
        setup.addView(controls)
        setup.addView(Ui.button(this, "Enable touch control") {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        })
        setup.addView(Ui.label(this, "Touch control only runs the actions you start. Images and calibration stay on this phone.", 13f, Ui.muted))
        page.addView(setup)

        val capture = Ui.panel(this)
        capture.addView(Ui.label(this, "02  ·  Share the game screen", 19f, bold = true))
        capture.addView(Ui.label(this, "For Wuthering Waves, turn the phone to landscape before starting. Select the whole screen in Android’s prompt.", 14f, Ui.muted))
        capture.addView(Ui.button(this, "Start screen capture", true) { beginCapture() })
        capture.addView(Ui.button(this, "Open game") { openGame() })
        capture.addView(Ui.button(this, "Stop screen capture") { SessionController.stopCapture(this) })
        page.addView(capture)

        val learn = Ui.panel(this)
        learn.addView(Ui.label(this, "03  ·  Teach one visual action", 19f, bold = true))
        learn.addView(Ui.label(this, "Visit a game menu, then return here. Select a distinctive button from the last captured game image.", 14f, Ui.muted))
        calibration = Ui.label(this, "No calibration saved", 14f, Ui.accent)
        Ui.gap(learn); learn.addView(calibration)
        learn.addView(Ui.button(this, "Calibrate from game image") { calibrate() })
        repetitions = EditText(this).apply {
            hint = "Maximum taps (1–50)"
            setText("1")
            inputType = InputType.TYPE_CLASS_NUMBER
            setTextColor(Ui.text); setHintTextColor(Ui.muted)
            contentDescription = "Maximum taps"
        }
        learn.addView(repetitions)
        learn.addView(Ui.button(this, "Run saved routine", true) { runSaved() })
        learn.addView(Ui.label(this, "Repeats only after the learned image disappears and returns. Stops after 60 seconds or if you leave the game.", 13f, Ui.muted))
        page.addView(learn)

        val lab = Ui.panel(this)
        lab.addView(Ui.label(this, "Check your device first", 19f, bold = true))
        lab.addView(Ui.label(this, "The touch lab checks taps, swipes, two fingers and image-triggered actions without changing anything in your game.", 14f, Ui.muted))
        lab.addView(Ui.button(this, "Open touch lab") { startActivity(Intent(this, TouchLabActivity::class.java)) })
        lab.addView(Ui.button(this, "Export session report") { exportReport() })
        page.addView(lab)

        val advanced = Ui.panel(this)
        advanced.addView(Ui.label(this, "Game package", 16f, bold = true))
        advanced.addView(Ui.label(this, "Global version is selected by default. Change this only for another installed game variant.", 13f, Ui.muted))
        target = EditText(this).apply {
            setText(RoutineStore.target(this@MainActivity)); setTextColor(Ui.text)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
            textSize = 13f
            setSingleLine(true)
            contentDescription = "Target game package"
        }
        advanced.addView(target)
        advanced.addView(Ui.button(this, "Save game package") {
            runCatching {
                val value = target.text.toString().trim()
                RoutineStore.setTarget(this, value)
                SessionController.configure(this, value)
                toast("Game package saved")
            }.onFailure { showError(it.message ?: "Invalid package") }
        })
        page.addView(advanced)
        page.addView(Ui.label(this, "0.1 · Feasibility prototype\nDaily farming and character combat are not verified in this release. Keep the phone unlocked and the game visible.", 13f, Ui.warning))
        Ui.gap(page, 20)
        setContentView(scroll)
        Ui.insetRoot(this, scroll)
    }

    override fun onResume() {
        super.onResume()
        SessionController.addListener(listener)
        handler.post(refreshTick)
    }

    override fun onPause() {
        handler.removeCallbacks(refreshTick)
        SessionController.removeListener(listener)
        super.onPause()
    }

    private fun refresh() {
        if (!::status.isInitialized) return
        val s = SessionController.snapshot
        status.text = s.status
        metrics.text = "Capture ${if (s.captureActive) "on" else "off"}  ·  ${s.frameCount} frames  ·  ${s.taps} taps\n" +
            "Last frame: ${s.frameAgeMs?.let { "${it / 1000}s ago" } ?: "none"}"
        controls.text = if (s.accessibilityConnected) "Touch control connected" else "Enable JH WuWa touch control in Android Accessibility settings."
        calibration.text = RoutineStore.load(this)?.let { "Saved: ${it.name}\n${it.template.frameWidth} × ${it.template.frameHeight} · ${it.targetPackage}" }
            ?: "No calibration saved"
    }

    private fun beginCapture() {
        if (!SessionController.snapshot.accessibilityConnected) {
            showError("Enable touch control first so captured images can be limited to your selected game or the touch lab.")
            return
        }
        if (SessionController.snapshot.captureActive) { toast("Capture is already active"); return }
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), REQUEST_NOTIFICATIONS)
        } else requestCapture()
    }

    private fun requestCapture() {
        val manager = getSystemService(MediaProjectionManager::class.java)
        val intent = if (Build.VERSION.SDK_INT >= 34) {
            manager.createScreenCaptureIntent(MediaProjectionConfig.createConfigForDefaultDisplay())
        } else manager.createScreenCaptureIntent()
        @Suppress("DEPRECATION")
        startActivityForResult(intent, REQUEST_CAPTURE)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQUEST_NOTIFICATIONS) requestCapture()
    }

    @Deprecated("Activity result API retained to avoid a runtime UI dependency")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQUEST_CAPTURE) {
            if (resultCode == RESULT_OK && data != null) {
                CaptureService.start(this, resultCode, data)
                toast("Capture starting. Open the game or touch lab.")
            } else toast("Screen sharing was not started")
        } else if (requestCode == REQUEST_EXPORT && resultCode == RESULT_OK) {
            val uri = data?.data ?: return
            runCatching {
                contentResolver.openOutputStream(uri, "wt")?.use {
                    it.write(SessionController.exportReport().toByteArray(Charsets.UTF_8))
                } ?: error("The document could not be opened")
            }.onSuccess { toast("Session report saved") }
                .onFailure { showError(it.message ?: "Could not save report") }
        }
    }

    private fun calibrate() {
        val frame = SessionController.latestFrame
        if (frame == null || frame.sourcePackage != RoutineStore.target(this)) {
            showError("Start capture and open your selected game first. Return here after its menu is visible.")
            return
        }
        CalibrationActivity.pendingFrame = frame
        startActivity(Intent(this, CalibrationActivity::class.java))
    }

    private fun runSaved() {
        val routine = RoutineStore.load(this) ?: return showError("Calibrate a button first")
        val count = repetitions.text.toString().toIntOrNull()
        if (count == null || count !in 1..50) return showError("Choose between 1 and 50 taps")
        if (routine.targetPackage != RoutineStore.target(this)) return showError("This calibration belongs to a different game package. Calibrate this game again.")
        if (!SessionController.snapshot.captureActive) return showError("Start screen capture before running a routine")
        if (!SessionController.snapshot.accessibilityConnected) return showError("Enable touch control first")
        val launch = packageManager.getLaunchIntentForPackage(routine.targetPackage)
            ?: return showError("The selected game is not installed or cannot be opened")
        SessionController.startRoutine(this, routine.copy(maxTaps = count))
        runCatching { startActivity(launch) }.onFailure {
            SessionController.stopRoutine("Game could not be opened")
            showError("The game could not be opened")
        }
    }

    private fun openGame() {
        val launch = packageManager.getLaunchIntentForPackage(RoutineStore.target(this))
        if (launch == null) showError("Game not found. Check the installed variant’s package below.")
        else runCatching { startActivity(launch) }.onFailure { showError("The game could not be opened") }
    }

    private fun exportReport() {
        val intent = Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "application/json"
            putExtra(Intent.EXTRA_TITLE, "jh-wuwa-session.json")
        }
        @Suppress("DEPRECATION")
        startActivityForResult(intent, REQUEST_EXPORT)
    }

    private fun toast(message: String) = Toast.makeText(this, message, Toast.LENGTH_LONG).show()
    private fun showError(message: String) { AlertDialog.Builder(this).setTitle("One more step").setMessage(message).setPositiveButton("OK", null).show() }

    companion object {
        private const val REQUEST_CAPTURE = 10
        private const val REQUEST_EXPORT = 11
        private const val REQUEST_NOTIFICATIONS = 12
    }
}
