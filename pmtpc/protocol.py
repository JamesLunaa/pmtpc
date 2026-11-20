"""Wire format for audio packets sent from the phone to the PC over UDP.

Each datagram is a 16-byte header followed by the audio payload:

    offset  size  field
    0       2     magic          b"PM"
    2       1     version        PROTOCOL_VERSION
    3       1     codec          CODEC_PCM_S16LE
    4       4     seq            u32, increments by 1 per packet, wraps
    8       8     timestamp_us   u64, sender capture time in microseconds

The header is big-endian. The PCM payload is little-endian signed 16-bit mono,
which matches Android's native byte order.
"""

import struct
from dataclasses import dataclass

MAGIC = b"PM"
PROTOCOL_VERSION = 1
CODEC_PCM_S16LE = 0

SAMPLE_RATE = 48_000
CHANNELS = 1
FRAME_MS = 10
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
FRAME_BYTES = FRAME_SAMPLES * 2

DEFAULT_PORT = 50_005
SEQ_MASK = 0xFFFF_FFFF

_HEADER = struct.Struct("!2sBBIQ")
HEADER_SIZE = _HEADER.size


class PacketError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Packet:
    seq: int
    timestamp_us: int
    payload: bytes
    codec: int = CODEC_PCM_S16LE

    def encode(self) -> bytes:
        header = _HEADER.pack(MAGIC, PROTOCOL_VERSION, self.codec, self.seq & SEQ_MASK, self.timestamp_us)
        return header + self.payload

    @classmethod
    def decode(cls, data: bytes) -> "Packet":
        if len(data) < HEADER_SIZE:
            raise PacketError(f"datagram too short ({len(data)} bytes)")
        magic, version, codec, seq, timestamp_us = _HEADER.unpack_from(data)
        if magic != MAGIC:
            raise PacketError("bad magic")
        if version != PROTOCOL_VERSION:
            raise PacketError(f"unsupported protocol version {version}")
        if codec != CODEC_PCM_S16LE:
            raise PacketError(f"unsupported codec {codec}")
        payload = data[HEADER_SIZE:]
        if len(payload) != FRAME_BYTES:
            raise PacketError(f"expected {FRAME_BYTES} payload bytes, got {len(payload)}")
        return cls(seq=seq, timestamp_us=timestamp_us, payload=payload, codec=codec)
