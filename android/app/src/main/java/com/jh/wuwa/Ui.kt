package com.jh.wuwa

import android.app.Activity
import android.content.Context
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.view.View
import android.view.ViewGroup
import android.view.WindowInsets
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

object Ui {
    val background = Color.rgb(16, 27, 32)
    val surface = Color.rgb(27, 42, 48)
    val border = Color.rgb(48, 69, 76)
    val text = Color.rgb(241, 245, 239)
    val muted = Color.rgb(175, 193, 195)
    val accent = Color.rgb(198, 237, 137)
    val warning = Color.rgb(255, 199, 127)

    fun dp(context: Context, value: Int): Int = (value * context.resources.displayMetrics.density).toInt()

    fun label(context: Context, value: String, size: Float = 15f, color: Int = text, bold: Boolean = false) =
        TextView(context).apply {
            this.text = value
            textSize = size
            setTextColor(color)
            if (bold) setTypeface(typeface, Typeface.BOLD)
            setLineSpacing(dp(context, 3).toFloat(), 1f)
        }

    fun column(context: Context, padding: Int = 0) = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        val p = dp(context, padding)
        setPadding(p, p, p, p)
    }

    fun panel(context: Context) = column(context, 18).apply {
        background = GradientDrawable().also {
            it.setColor(surface)
            it.cornerRadius = dp(context, 18).toFloat()
            it.setStroke(dp(context, 1), border)
        }
        layoutParams = LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = dp(context, 14) }
    }

    fun button(context: Context, title: String, primary: Boolean = false, action: () -> Unit) = Button(context).apply {
        text = title
        isAllCaps = false
        textSize = 15f
        minHeight = dp(context, 52)
        setTextColor(if (primary) Ui.background else Ui.text)
        backgroundTintList = android.content.res.ColorStateList.valueOf(if (primary) accent else border)
        layoutParams = LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(context, 8) }
        setOnClickListener { action() }
    }

    fun gap(parent: LinearLayout, height: Int = 10) {
        parent.addView(View(parent.context), LinearLayout.LayoutParams(1, dp(parent.context, height)))
    }

    fun insetRoot(activity: Activity, root: View) {
        root.setOnApplyWindowInsetsListener { view, insets ->
            if (android.os.Build.VERSION.SDK_INT >= 30) {
                val bars = insets.getInsets(WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout())
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            } else {
                @Suppress("DEPRECATION")
                view.setPadding(insets.systemWindowInsetLeft, insets.systemWindowInsetTop,
                    insets.systemWindowInsetRight, insets.systemWindowInsetBottom)
            }
            insets
        }
        root.requestApplyInsets()
    }
}
