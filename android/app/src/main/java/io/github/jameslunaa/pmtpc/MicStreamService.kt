package io.github.jameslunaa.pmtpc

import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioManager
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

sealed interface StreamState {
    data object Idle : StreamState
    data class Streaming(val host: String, val port: Int, val packetsSent: Long, val sendErrors: Long) : StreamState
    data class Failed(val message: String) : StreamState
}

/** Foreground service so streaming continues with the screen off or the app in the background. */
class MicStreamService : Service() {
    private val handler = Handler(Looper.getMainLooper())
    private var streamer: AudioStreamer? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private val wifiLocks = mutableListOf<WifiManager.WifiLock>()

    private val statsUpdater = object : Runnable {
        override fun run() {
            val s = streamer ?: return
            _state.value = (_state.value as? StreamState.Streaming)
                ?.copy(packetsSent = s.packetsSent, sendErrors = s.sendErrors) ?: return
            handler.postDelayed(this, 500)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> {
                val host = intent.getStringExtra(EXTRA_HOST).orEmpty()
                val port = intent.getIntExtra(EXTRA_PORT, Protocol.DEFAULT_PORT)
                val source = MicSource.valueOf(intent.getStringExtra(EXTRA_SOURCE) ?: MicSource.STANDARD.name)
                startStreaming(host, port, source)
            }
            else -> {
                stopStreaming()
                _state.value = StreamState.Idle
                stopSelf()
            }
        }
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        stopStreaming()
        if (_state.value is StreamState.Streaming) _state.value = StreamState.Idle
        super.onDestroy()
    }

    private fun startStreaming(host: String, port: Int, source: MicSource) {
        stopStreaming()
        ServiceCompat.startForeground(
            this,
            NOTIFICATION_ID,
            buildNotification("Streaming to $host:$port"),
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE else 0,
        )
        acquireLocks()

        val rawSupported = getSystemService(AudioManager::class.java)
            .getProperty(AudioManager.PROPERTY_SUPPORT_AUDIO_SOURCE_UNPROCESSED) == "true"
        streamer = AudioStreamer(host, port, AudioStreamer.audioSourceFor(source, rawSupported)) { message ->
            handler.post {
                stopStreaming()
                _state.value = StreamState.Failed(message)
                stopSelf()
            }
        }.also { it.start() }

        _state.value = StreamState.Streaming(host, port, 0, 0)
        handler.post(statsUpdater)
    }

    private fun stopStreaming() {
        handler.removeCallbacks(statsUpdater)
        streamer?.stop()
        streamer = null
        releaseLocks()
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
    }

    @Suppress("DEPRECATION")
    @SuppressLint("WakelockTimeout") // held for as long as the user streams; released in stopStreaming
    private fun acquireLocks() {
        // Without these, Wi-Fi power saving batches packets and causes large latency spikes,
        // and the CPU may sleep while the screen is off.
        val wifi = applicationContext.getSystemService(WifiManager::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            wifiLocks += wifi.createWifiLock(WifiManager.WIFI_MODE_FULL_LOW_LATENCY, "pmtpc:low-latency")
        }
        wifiLocks += wifi.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "pmtpc:high-perf")
        wifiLocks.forEach { it.setReferenceCounted(false); it.acquire() }

        wakeLock = getSystemService(PowerManager::class.java)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "pmtpc:stream")
            .apply { setReferenceCounted(false); acquire() }
    }

    private fun releaseLocks() {
        wifiLocks.forEach { if (it.isHeld) it.release() }
        wifiLocks.clear()
        wakeLock?.let { if (it.isHeld) it.release() }
        wakeLock = null
    }

    private fun buildNotification(text: String) = run {
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "Streaming", NotificationManager.IMPORTANCE_LOW),
        )
        val openApp = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE,
        )
        val stop = PendingIntent.getService(
            this, 0, Intent(this, MicStreamService::class.java).setAction(ACTION_STOP), PendingIntent.FLAG_IMMUTABLE,
        )
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_mic)
            .setContentTitle("Phone Mic")
            .setContentText(text)
            .setContentIntent(openApp)
            .addAction(0, "Stop", stop)
            .setOngoing(true)
            .build()
    }

    companion object {
        private const val ACTION_START = "io.github.jameslunaa.pmtpc.START"
        private const val ACTION_STOP = "io.github.jameslunaa.pmtpc.STOP"
        private const val EXTRA_HOST = "host"
        private const val EXTRA_PORT = "port"
        private const val EXTRA_SOURCE = "source"
        private const val CHANNEL_ID = "streaming"
        private const val NOTIFICATION_ID = 1

        private val _state = MutableStateFlow<StreamState>(StreamState.Idle)
        val state: StateFlow<StreamState> = _state

        fun start(context: Context, host: String, port: Int, source: MicSource) {
            val intent = Intent(context, MicStreamService::class.java)
                .setAction(ACTION_START)
                .putExtra(EXTRA_HOST, host)
                .putExtra(EXTRA_PORT, port)
                .putExtra(EXTRA_SOURCE, source.name)
            context.startForegroundService(intent)
        }

        fun stop(context: Context) {
            context.startService(Intent(context, MicStreamService::class.java).setAction(ACTION_STOP))
        }
    }
}
