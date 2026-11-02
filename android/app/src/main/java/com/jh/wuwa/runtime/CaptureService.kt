package com.jh.wuwa.runtime

import android.app.Activity
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.os.Looper
import android.os.SystemClock
import android.util.DisplayMetrics
import android.util.Log
import android.view.Display
import com.jh.wuwa.core.GrayFrame
import kotlin.math.min
import kotlin.math.roundToInt

/** One explicitly granted screen-capture session. Never restarted automatically. */
class CaptureService : Service() {
    private val main = Handler(Looper.getMainLooper())
    private var workerThread: HandlerThread? = null
    private var worker: Handler? = null
    private var projection: MediaProjection? = null
    private var display: VirtualDisplay? = null
    private var reader: ImageReader? = null
    private var initialGeometry: DisplayGeometry? = null
    private var receiverRegistered = false
    private var displayListenerRegistered = false
    @Volatile private var terminating = false
    private var stopReason = "Capture ended. Start again to grant a new session."
    private var lastProcessedAt = 0L
    private var lastImageTimestamp = -1L
    private val imageAccess = Any()
    private var cleanupScheduled = false

    private val projectionCallback = object : MediaProjection.Callback() {
        override fun onStop() {
            terminate("Android stopped screen capture. Start again to grant a new session.", stopProjection = false)
        }

        override fun onCapturedContentResize(width: Int, height: Int) {
            val expected = initialGeometry ?: return
            if (width != expected.width || height != expected.height) {
                terminate("Capture size changed. Restart in the desired orientation and select Entire screen.")
            }
        }

        override fun onCapturedContentVisibilityChanged(isVisible: Boolean) {
            if (!isVisible) SessionController.stopRoutine("Captured content is no longer visible.")
        }
    }

    private val screenReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action == Intent.ACTION_SCREEN_OFF) {
                terminate("Screen turned off. Unlock the phone and start a new capture session.")
            }
        }
    }

    private val displayListener = object : DisplayManager.DisplayListener {
        override fun onDisplayAdded(displayId: Int) = Unit
        override fun onDisplayRemoved(displayId: Int) {
            if (displayId == Display.DEFAULT_DISPLAY) terminate("Display disconnected.")
        }

        override fun onDisplayChanged(displayId: Int) {
            if (displayId != Display.DEFAULT_DISPLAY || terminating) return
            val expected = initialGeometry ?: return
            if (displayGeometry(this@CaptureService) != expected) {
                terminate("Display size or orientation changed. Restart capture and recalibrate.")
            }
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> terminate("Capture stopped by user.")
            ACTION_STOP_ROUTINE -> SessionController.stopRoutine()
            ACTION_START -> {
                // A second permission result cannot replace an existing projection silently.
                if (projection != null || terminating) return START_NOT_STICKY
                val resultCode = intent.getIntExtra(EXTRA_RESULT_CODE, Activity.RESULT_CANCELED)
                val data = readResultData(intent)
                if (resultCode != Activity.RESULT_OK || data == null) {
                    SessionController.captureFailed("Screen-capture permission was not granted.")
                    stopSelf()
                } else if (!SessionController.snapshot.accessibilityConnected) {
                    SessionController.captureFailed("Enable accessibility first so capture can be scoped to the selected app.")
                    stopSelf()
                } else {
                    begin(resultCode, data)
                }
            }
            else -> stopSelf()
        }
        return START_NOT_STICKY
    }

    private fun begin(resultCode: Int, data: Intent) {
        try {
            createNotificationChannel()
            val notification = buildNotification()
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
            } else startForeground(NOTIFICATION_ID, notification)
            if (SessionController.isLocked()) {
                terminate("Unlock the phone before starting capture.")
                return
            }
            val geometry = displayGeometry(this)
            require(geometry.width in 1..8192 && geometry.height in 1..8192) {
                "Unsupported display size."
            }
            initialGeometry = geometry
            val manager = getSystemService(MediaProjectionManager::class.java)
            val grantedProjection = manager.getMediaProjection(resultCode, data)
                ?: throw IllegalStateException("Android did not provide a capture session.")
            projection = grantedProjection
            grantedProjection.registerCallback(projectionCallback, main)
            workerThread = HandlerThread("JHWuwaCapture").also { it.start() }
            worker = Handler(requireNotNull(workerThread).looper)
            val imageReader = ImageReader.newInstance(geometry.width, geometry.height, PixelFormat.RGBA_8888, 2)
            reader = imageReader
            imageReader.setOnImageAvailableListener({ source -> processImage(source, geometry) }, worker)
            // Exactly one createVirtualDisplay call per consent token, including API 34+.
            display = grantedProjection.createVirtualDisplay(
                "JH Wuwa screen capture", geometry.width, geometry.height,
                resources.displayMetrics.densityDpi,
                DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                imageReader.surface, null, worker,
            ) ?: throw IllegalStateException("Android could not create the capture display.")
            registerInterruptionListeners()
            SessionController.captureStarted()
        } catch (error: SecurityException) {
            failAndStop("Capture permission expired or was refused. Start a new session.")
        } catch (error: RuntimeException) {
            failAndStop("Capture could not start: ${error.message ?: error.javaClass.simpleName}")
        }
    }

    private fun processImage(source: ImageReader, geometry: DisplayGeometry) {
        synchronized(imageAccess) { processImageLocked(source, geometry) }
    }

    private fun processImageLocked(source: ImageReader, geometry: DisplayGeometry) {
        // The worker may already have a callback queued when main requests stop.
        // Do not acquire another image once teardown begins.
        if (terminating) return
        val image = try { source.acquireLatestImage() } catch (_: IllegalStateException) { null } ?: return
        try {
            if (terminating) return
            val permit = SessionController.capturePermit() ?: return
            val now = SystemClock.elapsedRealtime()
            if (now - lastProcessedAt < FRAME_INTERVAL_MS || image.timestamp <= lastImageTimestamp) return
            if (SessionController.isLocked()) {
                main.post { terminate("Phone locked. Start a new capture session after unlocking.") }
                return
            }
            if (image.width != geometry.width || image.height != geometry.height) {
                main.post { terminate("Capture dimensions changed. Restart and recalibrate.") }
                return
            }
            lastProcessedAt = now
            lastImageTimestamp = image.timestamp
            val plane = image.planes.firstOrNull() ?: return
            if (plane.pixelStride < 4) return
            val width = min(MAX_ANALYSIS_WIDTH, geometry.width)
            val height = (geometry.height.toDouble() * width / geometry.width).roundToInt().coerceAtLeast(1)
            val colors = IntArray(width * height)
            val gray = ByteArray(colors.size)
            val buffer = plane.buffer
            for (y in 0 until height) {
                val sourceY = (y.toLong() * geometry.height / height).toInt().coerceAtMost(geometry.height - 1)
                val row = sourceY * plane.rowStride
                for (x in 0 until width) {
                    val sourceX = (x.toLong() * geometry.width / width).toInt().coerceAtMost(geometry.width - 1)
                    val offset = row + sourceX * plane.pixelStride
                    val red = buffer.get(offset).toInt() and 0xff
                    val green = buffer.get(offset + 1).toInt() and 0xff
                    val blue = buffer.get(offset + 2).toInt() and 0xff
                    val index = y * width + x
                    colors[index] = (0xff shl 24) or (red shl 16) or (green shl 8) or blue
                    gray[index] = ((77 * red + 150 * green + 29 * blue) shr 8).toByte()
                }
            }
            // This overload returns an immutable bitmap. Consumers may retain it safely.
            val bitmap = Bitmap.createBitmap(colors, width, height, Bitmap.Config.ARGB_8888)
            val captured = CapturedFrame(
                bitmap, GrayFrame(width, height, gray, now),
                geometry.width, geometry.height, geometry.rotation, permit.packageName,
            )
            SessionController.acceptFrame(captured, permit)
        } catch (error: RuntimeException) {
            if (!terminating) main.post {
                terminate("Screen frame could not be read: ${error.message ?: error.javaClass.simpleName}")
            }
        } finally {
            image.close()
        }
    }

    private fun registerInterruptionListeners() {
        val filter = IntentFilter(Intent.ACTION_SCREEN_OFF)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(screenReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            @Suppress("UnspecifiedRegisterReceiverFlag")
            registerReceiver(screenReceiver, filter)
        }
        receiverRegistered = true
        getSystemService(DisplayManager::class.java).registerDisplayListener(displayListener, main)
        displayListenerRegistered = true
    }

    private fun failAndStop(reason: String) {
        stopReason = reason
        terminating = true
        SessionController.captureFailed(reason)
        releaseCapture(stopProjection = true)
        stopSelf()
    }

    private fun terminate(reason: String, stopProjection: Boolean = true) {
        if (terminating) return
        terminating = true
        stopReason = reason
        SessionController.captureStopped(reason)
        releaseCapture(stopProjection)
        stopSelf()
    }

    private fun releaseCapture(stopProjection: Boolean) {
        if (cleanupScheduled) return
        cleanupScheduled = true
        val cleanupHandler = worker
        val cleanupThread = workerThread
        val capturedDisplay = display
        val capturedReader = reader
        val capturedProjection = projection
        display = null
        reader = null
        projection = null
        workerThread = null
        worker = null
        capturedProjection?.unregisterCallback(projectionCallback)
        if (receiverRegistered) {
            unregisterReceiver(screenReceiver)
            receiverRegistered = false
        }
        if (displayListenerRegistered) {
            getSystemService(DisplayManager::class.java).unregisterDisplayListener(displayListener)
            displayListenerRegistered = false
        }
        stopForeground(STOP_FOREGROUND_REMOVE)

        val cleanup = Runnable {
            try {
                // Closing an ImageReader invalidates acquired plane buffers.
                // Serialize this with acquisition, conversion and Image.close().
                synchronized(imageAccess) {
                    fun release(action: () -> Unit) {
                        try { action() } catch (error: RuntimeException) {
                            Log.w("JHWuwaCapture", "Capture resource cleanup failed", error)
                        }
                    }
                    release { capturedReader?.setOnImageAvailableListener(null, null) }
                    release { capturedDisplay?.release() }
                    release { capturedReader?.close() }
                    if (stopProjection) release { capturedProjection?.stop() }
                }
            } finally {
                cleanupThread?.quitSafely()
            }
        }
        if (cleanupHandler == null) {
            // Initialization failed before a reader/worker existed: no buffer is in use.
            cleanup.run()
        } else {
            cleanupHandler.removeCallbacksAndMessages(null)
            if (!cleanupHandler.post(cleanup)) {
                // An unexpectedly stopped looper must not make main wait for a
                // still-finishing conversion. The same lock protects this fallback.
                Thread(cleanup, "JHWuwaCaptureCleanup").apply { isDaemon = true }.start()
            }
        }
    }

    override fun onDestroy() {
        if (!terminating) {
            terminating = true
            SessionController.captureStopped(stopReason)
        }
        releaseCapture(stopProjection = true)
        super.onDestroy()
    }

    private fun createNotificationChannel() {
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "Active capture sessions", NotificationManager.IMPORTANCE_LOW).apply {
                description = "Shows when the mobile companion is capturing the selected game."
            },
        )
    }

    private fun buildNotification(): Notification {
        val open = Intent().setClassName(packageName, "com.jh.wuwa.MainActivity")
        val content = PendingIntent.getActivity(this, 0, open, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        fun serviceAction(action: String, requestCode: Int) = PendingIntent.getService(
            this, requestCode, Intent(this, CaptureService::class.java).setAction(action),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_view)
            .setContentTitle("JH Wuwa capture active")
            .setContentText("Keep the game visible. Stop any time from here.")
            .setContentIntent(content)
            .setOngoing(true)
            .setCategory(Notification.CATEGORY_SERVICE)
            .setVisibility(Notification.VISIBILITY_PRIVATE)
            .addAction(Notification.Action.Builder(
                android.R.drawable.ic_media_pause, "Stop routine", serviceAction(ACTION_STOP_ROUTINE, 1),
            ).build())
            .addAction(Notification.Action.Builder(
                android.R.drawable.ic_menu_close_clear_cancel, "Stop capture", serviceAction(ACTION_STOP, 2),
            ).build())
            .build()
    }

    @Suppress("DEPRECATION")
    private fun readResultData(intent: Intent): Intent? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            intent.getParcelableExtra(EXTRA_RESULT_DATA, Intent::class.java)
        } else intent.getParcelableExtra(EXTRA_RESULT_DATA)

    data class DisplayGeometry(val width: Int, val height: Int, val rotation: Int)

    companion object {
        private const val CHANNEL_ID = "capture"
        private const val NOTIFICATION_ID = 100
        private const val ACTION_START = "com.jh.wuwa.capture.START"
        private const val ACTION_STOP = "com.jh.wuwa.capture.STOP"
        private const val ACTION_STOP_ROUTINE = "com.jh.wuwa.capture.STOP_ROUTINE"
        private const val EXTRA_RESULT_CODE = "resultCode"
        private const val EXTRA_RESULT_DATA = "resultData"
        private const val FRAME_INTERVAL_MS = 200L
        private const val MAX_ANALYSIS_WIDTH = 720

        fun start(context: Context, resultCode: Int, resultData: Intent) {
            context.startForegroundService(Intent(context, CaptureService::class.java).apply {
                action = ACTION_START
                putExtra(EXTRA_RESULT_CODE, resultCode)
                putExtra(EXTRA_RESULT_DATA, resultData)
            })
        }

        @Suppress("DEPRECATION")
        internal fun displayGeometry(context: Context): DisplayGeometry {
            val screen = context.getSystemService(DisplayManager::class.java).getDisplay(Display.DEFAULT_DISPLAY)
                ?: throw IllegalStateException("No default display available.")
            val metrics = DisplayMetrics()
            screen.getRealMetrics(metrics)
            return DisplayGeometry(metrics.widthPixels, metrics.heightPixels, screen.rotation)
        }
    }
}
