"""PC side: receive audio packets over UDP and play them to an output device."""

import socket
import sys
import threading

import numpy as np
import sounddevice as sd

from pmtpc.jitter import JitterBuffer
from pmtpc.protocol import CHANNELS, FRAME_SAMPLES, SAMPLE_RATE, Packet, PacketError


class Receiver:
    def __init__(self, port: int, device: int | str | None = None, target_frames: int = 3, max_frames: int = 12):
        self.port = port
        self.device = device
        self.jitter = JitterBuffer(FRAME_SAMPLES, target_frames, max_frames)
        self.sender: tuple[str, int] | None = None
        self.bad_packets = 0
        self._stop = threading.Event()
        self._carry = np.zeros(0, dtype=np.int16)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(("0.0.0.0", port))
        self._sock.settimeout(0.5)

    def run(self, stats_interval: float = 2.0) -> None:
        net = threading.Thread(target=self._net_loop, name="pmtpc-net", daemon=True)
        net.start()
        stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=FRAME_SAMPLES,
            latency="low",
            device=self.device,
            callback=self._audio_callback,
        )
        print(f"Listening on UDP :{self.port}, output: {sd.query_devices(stream.device)['name']}")
        try:
            with stream:
                while not self._stop.wait(stats_interval):
                    self._print_stats()
        except KeyboardInterrupt:
            pass
        finally:
            self._stop.set()
            net.join()
            self._sock.close()

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
                print(f"Receiving from {addr[0]}:{addr[1]}")
            self.jitter.push(pkt.seq, np.frombuffer(pkt.payload, dtype="<i2"))

    def _audio_callback(self, outdata, frames, time_info, status) -> None:
        # PortAudio normally honors blocksize, but handle any callback size just in case.
        buf = self._carry
        while len(buf) < frames:
            buf = np.concatenate((buf, self.jitter.pop()))
        outdata[:, 0] = buf[:frames]
        self._carry = buf[frames:]

    def _print_stats(self) -> None:
        s = self.jitter.stats
        print(
            f"recv={s.received} played={s.played} concealed={s.concealed} late={s.late} "
            f"dropped={s.dropped} underruns={s.underruns} resets={s.resets} bad={self.bad_packets} "
            f"depth={self.jitter.depth}",
            flush=True,
        )


def default_output_device() -> int | str | None:
    """On Linux, PortAudio's ALSA `default` may have no outputs, so prefer the PipeWire/Pulse plugs."""
    if sys.platform.startswith("linux"):
        names = {d["name"] for d in sd.query_devices() if d["max_output_channels"] > 0}
        for name in ("pipewire", "pulse"):
            if name in names:
                return name
    return None


def receive(port: int, device: int | str | None = None, target_frames: int = 3, max_frames: int = 12) -> None:
    if device is None:
        device = default_output_device()
    Receiver(port, device, target_frames, max_frames).run()
