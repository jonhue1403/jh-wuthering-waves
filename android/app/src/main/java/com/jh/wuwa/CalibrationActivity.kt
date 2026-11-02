package com.jh.wuwa

import android.app.Activity
import android.content.Context
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RectF
import android.os.Bundle
import android.view.MotionEvent
import android.view.View
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Toast
import com.jh.wuwa.core.NormalizedRect
import com.jh.wuwa.core.TapRoutine
import com.jh.wuwa.core.TemplateMatcher
import com.jh.wuwa.runtime.CapturedFrame

class CalibrationActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val frame = pendingFrame
        if (frame == null) {
            Toast.makeText(this, "Capture the game again to calibrate", Toast.LENGTH_LONG).show()
            finish(); return
        }
        val wide = resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE
        val page = Ui.column(this, 18).apply {
            setBackgroundColor(Ui.background)
            if (wide) orientation = LinearLayout.HORIZONTAL
        }
        val information = Ui.column(this)
        information.addView(Ui.label(this, "Teach one visual action", 24f, bold = true))
        information.addView(Ui.label(this, "Drag a box around a distinctive button. The tap will land in its centre. Include text or an icon, not an empty colour patch.", 14f, Ui.muted))
        val selection = SelectionView(this, frame.bitmap)
        if (savedInstanceState?.containsKey("left") == true) {
            selection.selection = runCatching {
                NormalizedRect(savedInstanceState.getFloat("left"), savedInstanceState.getFloat("top"),
                    savedInstanceState.getFloat("right"), savedInstanceState.getFloat("bottom"))
            }.getOrNull()
        }
        selection.id = SELECTION_ID
        val actions = Ui.column(this)
        val name = EditText(this).apply {
            setText("Menu button"); setTextColor(Ui.text)
            hint = "Routine name"; setHintTextColor(Ui.muted)
            setSingleLine(true); contentDescription = "Routine name"
            filters = arrayOf(android.text.InputFilter.LengthFilter(64))
        }
        actions.addView(name)
        actions.addView(Ui.button(this, "Save calibration", true) {
            val region = selection.selection
            if (region == null) {
                Toast.makeText(this, "Drag a box on the image first", Toast.LENGTH_LONG).show()
                return@button
            }
            runCatching {
                val template = TemplateMatcher.capture(frame.gray, region)
                val routine = TapRoutine(name.text.toString().trim().ifEmpty { "Menu button" }, frame.sourcePackage, template)
                RoutineStore.save(this, routine)
            }.onSuccess {
                Toast.makeText(this, "Calibration saved. Test one tap first.", Toast.LENGTH_LONG).show()
                finish()
            }.onFailure { Toast.makeText(this, it.message ?: "Choose a more distinctive region", Toast.LENGTH_LONG).show() }
        })
        actions.addView(Ui.button(this, "Cancel") { finish() })
        if (wide) {
            val controls = Ui.column(this).apply { addView(information); addView(actions) }
            page.addView(selection, LinearLayout.LayoutParams(0, -1, 0.58f))
            page.addView(ScrollView(this).apply { addView(controls) }, LinearLayout.LayoutParams(0, -1, 0.42f))
        } else {
            page.addView(information)
            page.addView(selection, LinearLayout.LayoutParams(-1, 0, 1f))
            page.addView(actions)
        }
        val container = android.widget.FrameLayout(this).apply { addView(page); setBackgroundColor(Ui.background) }
        setContentView(container)
        Ui.insetRoot(this, container)
    }

    override fun onSaveInstanceState(outState: Bundle) {
        findViewById<SelectionView>(SELECTION_ID)?.selection?.let {
            outState.putFloat("left", it.left); outState.putFloat("top", it.top)
            outState.putFloat("right", it.right); outState.putFloat("bottom", it.bottom)
        }
        super.onSaveInstanceState(outState)
    }

    override fun onDestroy() {
        if (!isChangingConfigurations) pendingFrame = null
        super.onDestroy()
    }

    companion object {
        var pendingFrame: CapturedFrame? = null
        private const val SELECTION_ID = 4101
    }
}

/** Selection maps only the fitted bitmap; letterbox padding never becomes a tap. */
class SelectionView(context: Context, private val bitmap: Bitmap) : View(context) {
    var selection: NormalizedRect? = null
        set(value) { field = value; invalidate() }
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val imageBounds = RectF()
    private var startX = 0f
    private var startY = 0f
    private var selecting = false

    init {
        contentDescription = "Captured game image. Drag to select the button to recognise and tap."
        isFocusable = true
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val scale = minOf(width.toFloat() / bitmap.width, height.toFloat() / bitmap.height)
        val w = bitmap.width * scale
        val h = bitmap.height * scale
        imageBounds.set((width - w) / 2, (height - h) / 2, (width + w) / 2, (height + h) / 2)
        paint.style = Paint.Style.FILL; paint.alpha = 255
        canvas.drawBitmap(bitmap, null, imageBounds, paint)
        selection?.let {
            val r = RectF(imageBounds.left + it.left * w, imageBounds.top + it.top * h,
                imageBounds.left + it.right * w, imageBounds.top + it.bottom * h)
            paint.color = Ui.accent; paint.alpha = 45; canvas.drawRect(r, paint)
            paint.alpha = 255; paint.style = Paint.Style.STROKE; paint.strokeWidth = Ui.dp(context, 2).toFloat()
            canvas.drawRect(r, paint)
            paint.style = Paint.Style.FILL
            canvas.drawCircle(r.centerX(), r.centerY(), Ui.dp(context, 4).toFloat(), paint)
        }
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        if (imageBounds.isEmpty) return false
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                if (!imageBounds.contains(event.x, event.y)) return false
                startX = normalizedX(event.x); startY = normalizedY(event.y)
                selecting = true
                parent?.requestDisallowInterceptTouchEvent(true)
                return true
            }
            MotionEvent.ACTION_MOVE, MotionEvent.ACTION_UP -> {
                if (!selecting) return false
                val x = normalizedX(event.x); val y = normalizedY(event.y)
                if (kotlin.math.abs(x - startX) >= 0.01f && kotlin.math.abs(y - startY) >= 0.01f) {
                    selection = NormalizedRect(minOf(startX, x), minOf(startY, y), maxOf(startX, x), maxOf(startY, y))
                }
                if (event.actionMasked == MotionEvent.ACTION_UP) {
                    selecting = false
                    parent?.requestDisallowInterceptTouchEvent(false)
                    performClick()
                }
                return true
            }
            MotionEvent.ACTION_CANCEL -> {
                selecting = false; parent?.requestDisallowInterceptTouchEvent(false); return true
            }
        }
        return true
    }

    override fun performClick(): Boolean { super.performClick(); return true }
    private fun normalizedX(x: Float) = ((x - imageBounds.left) / imageBounds.width()).coerceIn(0f, 1f)
    private fun normalizedY(y: Float) = ((y - imageBounds.top) / imageBounds.height()).coerceIn(0f, 1f)
}
