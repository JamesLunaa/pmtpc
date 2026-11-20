package io.github.jameslunaa.pmtpc

import android.annotation.SuppressLint
import android.media.AudioDeviceInfo
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Process
import android.os.SystemClock
import java.io.IOException
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import kotlin.random.Random

enum class MicSource(val label: String, val description: String) {
    STANDARD("Standard", "Phone's default mic processing"),
    RAW("Raw", "No processing, if the phone supports it"),
    VOICE("Voice", "Noise suppression and echo cancellation"),
}

/** Captures the mic in 10 ms frames and sends each one as a UDP packet. */
class AudioStreamer(
    private val host: String,
    private val port: Int,
    private val audioSource: Int,
    private val preferredDevice: AudioDeviceInfo?,
    private val onError: (String) -> Unit,
) {
    @Volatile var packetsSent = 0L
        private set

    @Volatile var sendErrors = 0L
        private set

    /** The mic actually being recorded from, which can differ from the preferred one (e.g. after unplugging). */
    val inputName: String?
        get() = record?.runCatching { routedDevice?.label }?.getOrNull()

    @Volatile private var record: AudioRecord? = null
    @Volatile private var running = false
    private var thread: Thread? = null

    fun start() {
        running = true
        thread = Thread(::run, "pmtpc-capture").apply { start() }
    }

    fun stop() {
        running = false
        thread?.join(1000)
        thread = null
    }

    @SuppressLint("MissingPermission") // MainActivity requests RECORD_AUDIO before starting the service
    private fun run() {
        Process.setThreadPriority(Process.THREAD_PRIORITY_URGENT_AUDIO)
        var socket: DatagramSocket? = null
        try {
            val address = InetAddress.getByName(host)
            socket = DatagramSocket()

            val minBuffer = AudioRecord.getMinBufferSize(
                Protocol.SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
            )
            val record = AudioRecord(
                audioSource,
                Protocol.SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                maxOf(minBuffer, Protocol.FRAME_BYTES * 4),
            )
            this.record = record
            check(record.state == AudioRecord.STATE_INITIALIZED) { "Microphone is unavailable" }
            preferredDevice?.let(record::setPreferredDevice)

            // AudioRecord writes PCM in native (little-endian) order, which is what the protocol expects,
            // so it can read straight into the packet after the header.
            val packet = ByteArray(Protocol.PACKET_SIZE)
            val datagram = DatagramPacket(packet, packet.size, address, port)
            var seq = Random.nextInt()

            record.startRecording()
            while (running) {
                var read = 0
                while (read < Protocol.FRAME_BYTES && running) {
                    val n = record.read(packet, Protocol.HEADER_SIZE + read, Protocol.FRAME_BYTES - read)
                    check(n >= 0) { "Microphone read failed ($n)" }
                    read += n
                }
                if (!running) break

                Protocol.writeHeader(packet, seq++, SystemClock.elapsedRealtimeNanos() / 1000)
                try {
                    socket.send(datagram)
                    packetsSent++
                } catch (e: IOException) {
                    // Wi-Fi blips (e.g. roaming) shouldn't end the stream; the receiver conceals the gap.
                    sendErrors++
                }
            }
        } catch (e: Exception) {
            if (running) onError(e.message ?: e.toString())
        } finally {
            record?.let {
                record = null
                it.runCatching { stop() }
                it.release()
            }
            socket?.close()
        }
    }

    companion object {
        fun audioSourceFor(source: MicSource, rawSupported: Boolean): Int = when (source) {
            MicSource.STANDARD -> MediaRecorder.AudioSource.MIC
            MicSource.RAW ->
                if (rawSupported) MediaRecorder.AudioSource.UNPROCESSED
                else MediaRecorder.AudioSource.VOICE_RECOGNITION
            MicSource.VOICE -> MediaRecorder.AudioSource.VOICE_COMMUNICATION
        }
    }
}
