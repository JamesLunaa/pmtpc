import numpy as np

from pmtpc.jitter import JitterBuffer, seq_delta
from pmtpc.protocol import FRAME_BYTES, Packet, SEQ_MASK

N = 4


def frame(value: int) -> np.ndarray:
    return np.full(N, value, dtype=np.int16)


def test_packet_roundtrip():
    pkt = Packet(seq=SEQ_MASK, timestamp_us=123, payload=bytes(FRAME_BYTES))
    assert Packet.decode(pkt.encode()) == pkt


def test_seq_delta_wraps():
    assert seq_delta(0, SEQ_MASK) == 1
    assert seq_delta(SEQ_MASK, 0) == -1


def test_prebuffers_then_plays_in_order():
    jb = JitterBuffer(N, target_frames=3, max_frames=10)
    jb.push(11, frame(11))
    jb.push(10, frame(10))
    assert not jb.pop().any()  # still prebuffering
    jb.push(12, frame(12))
    assert [jb.pop()[0] for _ in range(3)] == [10, 11, 12]


def test_conceals_gap_and_drops_late():
    jb = JitterBuffer(N, target_frames=2, max_frames=10)
    for s in (0, 1, 3):
        jb.push(s, frame(1000))
    jb.pop(), jb.pop()
    assert jb.pop()[0] == 500  # seq 2 missing: previous frame at half volume
    assert jb.stats.concealed == 1
    jb.push(2, frame(2))  # arrives too late
    assert jb.stats.late == 1
    assert jb.pop()[0] == 1000


def test_underrun_returns_to_prebuffering():
    jb = JitterBuffer(N, target_frames=2, max_frames=10)
    jb.push(0, frame(1)), jb.push(1, frame(1))
    jb.pop(), jb.pop()
    assert not jb.pop().any()
    assert jb.stats.underruns == 1
    jb.push(2, frame(2))
    assert not jb.pop().any()  # prebuffering again


def test_overflow_drops_oldest():
    jb = JitterBuffer(N, target_frames=2, max_frames=4)
    for s in range(7):
        jb.push(s, frame(s))
    assert jb.pop()[0] == 3
    assert jb.stats.dropped == 3


def test_sender_restart_resets():
    jb = JitterBuffer(N, target_frames=1, max_frames=4)
    jb.push(5000, frame(1))
    jb.pop()
    jb.push(7, frame(7))
    assert jb.stats.resets == 1
    assert jb.pop()[0] == 7


def test_wraparound_order():
    jb = JitterBuffer(N, target_frames=3, max_frames=10)
    for s in (0, SEQ_MASK, SEQ_MASK - 1):
        jb.push(s, frame(s & 0x7FFF))
    assert jb.pop()[0] == (SEQ_MASK - 1) & 0x7FFF
