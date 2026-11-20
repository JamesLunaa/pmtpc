"""Jitter buffer: reorders incoming frames and feeds the audio callback at a steady pace."""

import threading
from dataclasses import dataclass

import numpy as np

from pmtpc.protocol import SEQ_MASK

_HALF_RANGE = 1 << 31


def seq_delta(a: int, b: int) -> int:
    """Signed distance from b to a, accounting for u32 wraparound."""
    d = (a - b) & SEQ_MASK
    return d - (1 << 32) if d >= _HALF_RANGE else d


@dataclass
class JitterStats:
    received: int = 0
    played: int = 0
    concealed: int = 0
    late: int = 0
    dropped: int = 0
    underruns: int = 0
    resets: int = 0


class JitterBuffer:
    """Thread-safe: `push` is called from the network thread, `pop` from the audio callback.

    Playback starts once `target_frames` are buffered. A missing frame is concealed by
    repeating the previous one at decreasing volume. If the buffer runs dry, it goes back to
    prebuffering. If it grows past `max_frames` (a burst of packets, or the phone's clock
    running faster than the PC's), the oldest frames are dropped to bring latency back down.
    """

    # A jump this large in either direction means the sender restarted.
    RESET_DISTANCE = 1000

    def __init__(self, frame_samples: int, target_frames: int = 3, max_frames: int = 12):
        if not 1 <= target_frames < max_frames:
            raise ValueError("need 1 <= target_frames < max_frames")
        self.frame_samples = frame_samples
        self.target_frames = target_frames
        self.max_frames = max_frames
        self.stats = JitterStats()
        self._lock = threading.Lock()
        self._frames: dict[int, np.ndarray] = {}
        self._next_seq: int | None = None
        self._buffering = True
        self._last: np.ndarray | None = None
        self._conceal_run = 0
        self._silence = np.zeros(frame_samples, dtype=np.int16)

    @property
    def depth(self) -> int:
        with self._lock:
            return len(self._frames)

    def push(self, seq: int, frame: np.ndarray) -> None:
        with self._lock:
            self.stats.received += 1
            if self._next_seq is not None:
                d = seq_delta(seq, self._next_seq)
                if abs(d) > self.RESET_DISTANCE:
                    self._reset()
                elif d < 0:
                    self.stats.late += 1
                    return
            self._frames[seq] = frame

    def pop(self) -> np.ndarray:
        with self._lock:
            if self._buffering:
                if len(self._frames) < self.target_frames:
                    return self._silence
                self._buffering = False
                if self._next_seq is None or self._next_seq not in self._frames:
                    self._next_seq = self._oldest_seq()

            while len(self._frames) > self.max_frames:
                if self._frames.pop(self._next_seq, None) is not None:
                    self.stats.dropped += 1
                self._next_seq = (self._next_seq + 1) & SEQ_MASK

            frame = self._frames.pop(self._next_seq, None)
            if frame is None:
                if not self._frames:
                    self.stats.underruns += 1
                    self._buffering = True
                    self._last = None
                    return self._silence
                frame = self._conceal()
            else:
                self._conceal_run = 0
                self._last = frame
            self.stats.played += 1
            self._next_seq = (self._next_seq + 1) & SEQ_MASK
            return frame

    def _conceal(self) -> np.ndarray:
        self.stats.concealed += 1
        self._conceal_run += 1
        if self._last is None or self._conceal_run > 3:
            return self._silence
        gain = 0.5 ** self._conceal_run
        return (self._last.astype(np.float32) * gain).astype(np.int16)

    def _oldest_seq(self) -> int:
        if self._next_seq is None:
            ref = next(iter(self._frames))
        else:
            ref = self._next_seq
        return min(self._frames, key=lambda s: seq_delta(s, ref))

    def _reset(self) -> None:
        self.stats.resets += 1
        self._frames.clear()
        self._next_seq = None
        self._buffering = True
        self._last = None
        self._conceal_run = 0
