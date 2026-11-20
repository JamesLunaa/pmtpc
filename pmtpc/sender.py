"""Test sender: stands in for the phone by streaming a PC mic or a test tone over UDP."""

import random
import socket
import time

import numpy as np
import sounddevice as sd

from pmtpc.protocol import CHANNELS, FRAME_SAMPLES, SAMPLE_RATE, SEQ_MASK, Packet


class Sender:
    def __init__(self, host: str, port: int, loss: float = 0.0):
        self.addr = (host, port)
        self.loss = loss
        self.seq = random.getrandbits(32)
        self.sent = 0
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send_frame(self, frame: np.ndarray) -> None:
        pkt = Packet(seq=self.seq, timestamp_us=time.monotonic_ns() // 1000, payload=frame.astype("<i2").tobytes())
        self.seq = (self.seq + 1) & SEQ_MASK
        if self.loss and random.random() < self.loss:
            return
        self._sock.sendto(pkt.encode(), self.addr)
        self.sent += 1

    def stream_mic(self, device: int | str | None = None) -> None:
        def callback(indata, frames, time_info, status):
            self.send_frame(indata[:, 0])

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=FRAME_SAMPLES,
            latency="low",
            device=device,
            callback=callback,
        ) as stream:
            print(f"Streaming mic '{sd.query_devices(stream.device)['name']}' to {self.addr[0]}:{self.addr[1]}")
            self._wait()

    def stream_tone(self, freq: float = 440.0, amplitude: float = 0.3) -> None:
        print(f"Streaming {freq:g} Hz tone to {self.addr[0]}:{self.addr[1]}")
        phase = 0
        period = FRAME_SAMPLES / SAMPLE_RATE
        deadline = time.perf_counter()
        try:
            while True:
                t = (np.arange(FRAME_SAMPLES) + phase) / SAMPLE_RATE
                self.send_frame((np.sin(2 * np.pi * freq * t) * amplitude * 32767).astype(np.int16))
                phase += FRAME_SAMPLES
                deadline += period
                time.sleep(max(0.0, deadline - time.perf_counter()))
        except KeyboardInterrupt:
            pass

    def _wait(self) -> None:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
