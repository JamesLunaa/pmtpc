package io.github.jameslunaa.pmtpc

import org.junit.Assert.assertEquals
import org.junit.Test

class ProtocolTest {
    @Test
    fun headerMatchesPythonReceiver() {
        val packet = ByteArray(Protocol.PACKET_SIZE)
        Protocol.writeHeader(packet, seq = -1, timestampUs = 123_456_789)
        // Expected bytes come from pmtpc.protocol.Packet(seq=0xFFFFFFFF, timestamp_us=123456789).encode()
        val header = packet.copyOf(Protocol.HEADER_SIZE).joinToString("") { "%02x".format(it) }
        assertEquals("504d0100ffffffff00000000075bcd15", header)
    }

    @Test
    fun frameIs10msAt48kHz() {
        assertEquals(480, Protocol.FRAME_SAMPLES)
        assertEquals(976, Protocol.PACKET_SIZE)
    }
}
