package com.jh.wuwa

import android.graphics.Bitmap
import android.graphics.Canvas
import android.os.SystemClock
import android.view.MotionEvent
import android.view.View
import com.jh.wuwa.core.NormalizedRect
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.LooperMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
@LooperMode(LooperMode.Mode.PAUSED)
class SelectionViewTest : IsolatedAndroidTest() {
    private fun fittedSelection(): SelectionView {
        val view = SelectionView(application, Bitmap.createBitmap(200, 100, Bitmap.Config.ARGB_8888))
        view.measure(View.MeasureSpec.makeMeasureSpec(400, View.MeasureSpec.EXACTLY),
            View.MeasureSpec.makeMeasureSpec(400, View.MeasureSpec.EXACTLY))
        view.layout(0, 0, 400, 400)
        view.draw(Canvas(Bitmap.createBitmap(400, 400, Bitmap.Config.ARGB_8888)))
        return view
    }

    private fun touch(view: View, action: Int, x: Float, y: Float): Boolean {
        val time = SystemClock.uptimeMillis()
        val event = MotionEvent.obtain(time, time, action, x, y, 0)
        return try { view.onTouchEvent(event) } finally { event.recycle() }
    }

    @Test
    fun letterboxPaddingIsExcludedFromNormalizedTouchCoordinates() {
        val view = fittedSelection()
        assertTrue(touch(view, MotionEvent.ACTION_DOWN, 100f, 150f))
        assertTrue(touch(view, MotionEvent.ACTION_UP, 300f, 250f))
        assertEquals(NormalizedRect(0.25f, 0.25f, 0.75f, 0.75f), view.selection)
    }

    @Test
    fun gesturesStartingInLetterboxPaddingDoNotCreateASelection() {
        val view = fittedSelection()
        assertFalse(touch(view, MotionEvent.ACTION_DOWN, 100f, 20f))
        assertFalse(touch(view, MotionEvent.ACTION_UP, 300f, 250f))
        assertNull(view.selection)
    }

    @Test
    fun draggingOutsideTheImageClampsToItsBounds() {
        val view = fittedSelection()
        touch(view, MotionEvent.ACTION_DOWN, 100f, 150f)
        touch(view, MotionEvent.ACTION_UP, 500f, 390f)
        assertEquals(NormalizedRect(0.25f, 0.25f, 1f, 1f), view.selection)
    }

    @Test
    fun tinyTapsAndCancelledDragsDoNotCreateATarget() {
        val view = fittedSelection()
        touch(view, MotionEvent.ACTION_DOWN, 100f, 150f)
        touch(view, MotionEvent.ACTION_UP, 101f, 151f)
        assertNull(view.selection)
        touch(view, MotionEvent.ACTION_DOWN, 100f, 150f)
        touch(view, MotionEvent.ACTION_CANCEL, 100f, 150f)
        assertFalse(touch(view, MotionEvent.ACTION_UP, 300f, 250f))
        assertNull(view.selection)
    }
}
