"""PC side: receive audio packets over UDP and play them to an output device."""

import logging
import socket
import threading
import time
from typing import Any

import numpy as np
import sounddevice as sd

from pmtpc.devices import resolve_output
from pmtpc.jitter import JitterBuffer
from pmtpc.protocol import CHANNELS, FRAME_SAMPLES, SAMPLE_RATE, Packet, PacketError

log = logging.getLogger(__name__)

# The phone counts as disconnected after this long without packets.
CONNECTION_TIMEOUT = 3.0


class Receiver:
    def __init__(
        self,
        port: int,
        device: int | str | None = None,
        extra_settings: Any = None,
        target_frames: int = 3,
        max_frames: int = 12,
    ):
        self.port = port
        self.device = device
        self.extra_settings = extra_settings
        self.jitter = JitterBuffer(FRAME_SAMPLES, target_frames, max_frames)
        self.sender: tuple[str, int] | None = None
        self.output_name: str | None = None
        self.bad_packets = 0
        self._last_packet = 0.0
        self._stop = threading.Event()
        self._carry = np.zeros(0, dtype=np.int16)
        self._net: threading.Thread | None = None
        self._stream: sd.OutputStream | None = None
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self._sock.bind(("0.0.0.0", port))
        except OSError:
            self._sock.close()
            raise
        self._sock.settimeout(0.5)

    @property
    def connected(self) -> bool:
        return time.monotonic() - self._last_packet < CONNECTION_TIMEOUT

    def start(self) -> None:
        self._stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=FRAME_SAMPLES,
            latency="low",
            device=self.device,
            extra_settings=self.extra_settings,
            callback=self._audio_callback,
        )
        self.output_name = sd.query_devices(self._stream.device)["name"]
        self._net = threading.Thread(target=self._net_loop, name="pmtpc-net", daemon=True)
        self._net.start()
        self._stream.start()
        log.info("Listening on UDP :%d, output: %s", self.port, self.output_name)

    def stop(self) -> None:
        self._stop.set()
        if self._stream is not None:
            self._stream.close()
        if self._net is not None:
            self._net.join()
        self._sock.close()

    def run(self, stats_interval: float = 2.0) -> None:
        """Run until Ctrl+C, logging stats periodically."""
        self.start()
        try:
            while not self._stop.wait(stats_interval):
                log.info(self.stats_line())
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stats_line(self) -> str:
        s = self.jitter.stats
        return (
            f"recv={s.received} played={s.played} concealed={s.concealed} late={s.late} "
            f"dropped={s.dropped} underruns={s.underruns} resets={s.resets} bad={self.bad_packets} "
            f"depth={self.jitter.depth}"
        )

    def _net_loop(self) -> None:
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(4096)
            except TimeoutError:
                continue
            try:
                pkt = Packet.decode(data)
            except PacketError:
                self.bad_packets += 1
                continue
            if addr != self.sender:
                self.sender = addr
                log.info("Receiving from %s:%d", *addr)
            self._last_packet = time.monotonic()
            self.jitter.push(pkt.seq, np.frombuffer(pkt.payload, dtype="<i2"))

    def _audio_callback(self, outdata, frames, time_info, status) -> None:
        # PortAudio normally honors blocksize, but handle any callback size just in case.
        buf = self._carry
        while len(buf) < frames:
            buf = np.concatenate((buf, self.jitter.pop()))
        outdata[:, 0] = buf[:frames]
        self._carry = buf[frames:]


def create_receiver(
    port: int, device: int | str | None = None, target_frames: int = 3, max_frames: int = 12
) -> Receiver:
    device, extra_settings = resolve_output(device)
    return Receiver(port, device, extra_settings, target_frames, max_frames)


def receive(port: int, device: int | str | None = None, target_frames: int = 3, max_frames: int = 12) -> None:
    create_receiver(port, device, target_frames, max_frames).run()
