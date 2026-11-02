package com.jh.wuwa

import android.app.Activity
import android.content.Context
import android.content.res.Configuration
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RectF
import android.os.Bundle
import android.os.SystemClock
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import com.jh.wuwa.core.GesturePresets
import com.jh.wuwa.core.NormalizedPoint
import com.jh.wuwa.core.NormalizedRect
import com.jh.wuwa.core.TapRoutine
import com.jh.wuwa.core.TemplateMatcher
import com.jh.wuwa.runtime.SessionController

class TouchLabActivity : Activity() {
    private lateinit var pad: TouchLabView
    private lateinit var status: TextView
    private val listener: () -> Unit = {
        if (::status.isInitialized) status.text = SessionController.snapshot.status
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        val wide = resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE
        val page = Ui.column(this, 16).apply {
            setBackgroundColor(Ui.background)
            if (wide) orientation = LinearLayout.HORIZONTAL
        }
        val information = Ui.column(this)
        information.addView(Ui.label(this, "TOUCH LAB", 13f, Ui.accent, true))
        information.addView(Ui.label(this, "Check the controls", 24f, bold = true))
        information.addView(Ui.label(this, "Start capture from the main screen first. These tests touch only this laboratory.", 13f, Ui.muted))
        status = Ui.label(this, "", 13f, Ui.warning).apply {
            minLines = 3
            maxLines = 3
            ellipsize = android.text.TextUtils.TruncateAt.END
        }
        information.addView(status)
        pad = TouchLabView(this)
        val actions = Ui.column(this)
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        fun add(title: String, action: () -> Unit) {
            row.addView(Ui.button(this, title, action = action), LinearLayout.LayoutParams(0, Ui.dp(this, 54), 1f))
        }
        add("Tap") { submit { GesturePresets.tap(pad.attackPoint()) } }
        add("Swipe") { submit { GesturePresets.swipe(pad.moveStart(), pad.moveEnd()) } }
        add("2 fingers") { submit { GesturePresets.moveAndTap(pad.moveStart(), pad.moveEnd(), pad.attackPoint()) } }
        actions.addView(row)
        actions.addView(Ui.button(this, "Run 3 visual taps", true) { runVisualTest() })
        actions.addView(Ui.button(this, "Stop and return") { SessionController.stopRoutine("Left touch lab"); finish() })
        if (wide) {
            val controls = Ui.column(this).apply { addView(information); addView(actions) }
            val scrollingControls = ScrollView(this).apply { addView(controls) }
            page.addView(scrollingControls, LinearLayout.LayoutParams(0, -1, 0.43f))
            page.addView(pad, LinearLayout.LayoutParams(0, -1, 0.57f))
        } else {
            page.addView(information)
            page.addView(pad, LinearLayout.LayoutParams(-1, 0, 1f))
            page.addView(actions)
        }
        val container = android.widget.FrameLayout(this).apply { addView(page); setBackgroundColor(Ui.background) }
        setContentView(container)
        Ui.insetRoot(this, container)
    }

    override fun onResume() {
        super.onResume()
        SessionController.setLabActive(true)
        SessionController.addListener(listener)
        listener()
    }

    override fun onPause() {
        SessionController.setLabActive(false)
        SessionController.removeListener(listener)
        super.onPause()
    }

    private fun submit(plan: () -> com.jh.wuwa.core.GesturePlan) {
        pad.postDelayed({
            if (!hasWindowFocus()) return@postDelayed
            runCatching { SessionController.requestGesture(plan()) }.onSuccess {
                if (!it) toast("Enable touch control and capture, then wait for a fresh lab frame")
            }.onFailure { toast(it.message ?: "Gesture could not be started") }
        }, 180)
    }

    private fun runVisualTest() {
        val frame = SessionController.latestFrame
        if (frame == null || frame.sourcePackage != packageName || SystemClock.elapsedRealtime() - frame.gray.capturedAtMs > 1000) {
            toast("Start capture and wait for a fresh lab frame"); return
        }
        if (!pad.targetVisible) { toast("Wait for the pattern to reappear"); return }
        runCatching {
            val region = pad.targetRegion()
            val template = TemplateMatcher.capture(frame.gray, region)
            TapRoutine("Touch lab visual test", packageName, template, maxTaps = 3)
        }.onSuccess { SessionController.startRoutine(this, it) }
            .onFailure { toast(it.message ?: "Wait for a complete lab frame") }
    }

    private fun toast(message: String) = Toast.makeText(this, message, Toast.LENGTH_LONG).show()
}

/** Native touch target with a stable high-contrast image and a visible absent state. */
class TouchLabView(context: Context) : View(context) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val target = RectF()
    private var targetTaps = 0
    private var maximumPointers = 0
    private var moveEvents = 0
    var targetVisible = true
        private set
    private val restoreTarget = Runnable { targetVisible = true; invalidate() }

    init {
        minimumHeight = Ui.dp(context, 130)
        contentDescription = "Touch test area with a movement circle and checkerboard tap target"
        isFocusable = true
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val radius = minOf(width * 0.13f, height * 0.22f)
        paint.style = Paint.Style.FILL; paint.color = Ui.surface
        canvas.drawCircle(width * 0.25f, height * 0.52f, radius, paint)
        paint.style = Paint.Style.STROKE; paint.color = Ui.accent; paint.strokeWidth = Ui.dp(context, 2).toFloat()
        canvas.drawCircle(width * 0.25f, height * 0.52f, radius, paint)
        paint.style = Paint.Style.FILL
        val side = minOf(width * 0.28f, height * 0.48f)
        target.set(width * 0.72f - side / 2, height * 0.52f - side / 2,
            width * 0.72f + side / 2, height * 0.52f + side / 2)
        if (targetVisible) {
            paint.isAntiAlias = false
            for (row in 0 until 6) for (column in 0 until 6) {
                paint.color = if ((row + column) % 2 == 0) Ui.accent else Ui.background
                canvas.drawRect(target.left + column * side / 6, target.top + row * side / 6,
                    target.left + (column + 1) * side / 6, target.top + (row + 1) * side / 6, paint)
            }
            paint.isAntiAlias = true
        } else {
            paint.color = Ui.surface; canvas.drawRect(target, paint)
        }
        paint.color = Ui.muted; paint.textSize = Ui.dp(context, 12).toFloat()
        canvas.drawText("MOVE", width * 0.15f, maxOf(Ui.dp(context, 16).toFloat(), height * 0.18f), paint)
        canvas.drawText("TAP", width * 0.66f, maxOf(Ui.dp(context, 16).toFloat(), height * 0.18f), paint)
        paint.color = Ui.text
        canvas.drawText("Target taps: $targetTaps   ·   Max fingers: $maximumPointers", Ui.dp(context, 4).toFloat(), height - Ui.dp(context, 22).toFloat(), paint)
        canvas.drawText("Movement events: $moveEvents", Ui.dp(context, 4).toFloat(), height - Ui.dp(context, 5).toFloat(), paint)
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        maximumPointers = maxOf(maximumPointers, event.pointerCount)
        if (event.actionMasked == MotionEvent.ACTION_MOVE) moveEvents++
        if (event.actionMasked == MotionEvent.ACTION_DOWN || event.actionMasked == MotionEvent.ACTION_POINTER_DOWN) {
            val index = event.actionIndex
            if (targetVisible && target.contains(event.getX(index), event.getY(index))) {
                targetTaps++
                targetVisible = false
                removeCallbacks(restoreTarget)
                postDelayed(restoreTarget, 1000)
            }
        }
        if (event.actionMasked == MotionEvent.ACTION_UP) performClick()
        invalidate()
        return true
    }

    override fun performClick(): Boolean { super.performClick(); return true }
    override fun onDetachedFromWindow() { removeCallbacks(restoreTarget); super.onDetachedFromWindow() }

    private fun displayPoint(x: Float, y: Float): NormalizedPoint {
        val frame = SessionController.latestFrame ?: error("Wait for a captured lab frame")
        val location = IntArray(2); getLocationOnScreen(location)
        return NormalizedPoint((location[0] + x) / frame.displayWidth, (location[1] + y) / frame.displayHeight)
    }

    fun attackPoint() = displayPoint(target.centerX(), target.centerY())
    fun moveStart() = displayPoint(width * 0.25f, height * 0.52f)
    fun moveEnd() = displayPoint(width * 0.33f, height * 0.38f)
    fun targetRegion(): NormalizedRect {
        check(!target.isEmpty) { "Wait for the laboratory to draw" }
        val inset = minOf(target.width(), target.height()) * 0.04f
        val a = displayPoint(target.left + inset, target.top + inset)
        val b = displayPoint(target.right - inset, target.bottom - inset)
        return NormalizedRect(a.x, a.y, b.x, b.y)
    }
}
