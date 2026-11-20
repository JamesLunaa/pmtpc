package io.github.jameslunaa.pmtpc

import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Wire format shared with the PC receiver; see pmtpc/protocol.py. */
object Protocol {
    const val SAMPLE_RATE = 48_000
    const val FRAME_SAMPLES = SAMPLE_RATE / 100 // 10 ms
    const val FRAME_BYTES = FRAME_SAMPLES * 2
    const val HEADER_SIZE = 16
    const val PACKET_SIZE = HEADER_SIZE + FRAME_BYTES
    const val DEFAULT_PORT = 50_005

    private const val VERSION: Byte = 1
    private const val CODEC_PCM_S16LE: Byte = 0

    /** Writes the big-endian header into the first [HEADER_SIZE] bytes of [packet]. */
    fun writeHeader(packet: ByteArray, seq: Int, timestampUs: Long) {
        ByteBuffer.wrap(packet, 0, HEADER_SIZE).order(ByteOrder.BIG_ENDIAN)
            .put('P'.code.toByte())
            .put('M'.code.toByte())
            .put(VERSION)
            .put(CODEC_PCM_S16LE)
            .putInt(seq)
            .putLong(timestampUs)
    }
}
