"""System tray app that runs the receiver in the background. This is the Windows build's entry point."""

import errno
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pystray

from pmtpc.devices import VB_CABLE_PLAYBACK, VB_CABLE_URL
from pmtpc.icon import ACTIVE, PROBLEM, WAITING, make_icon
from pmtpc.protocol import DEFAULT_PORT
from pmtpc.receiver import Receiver, create_receiver

log = logging.getLogger(__name__)

APP_NAME = "Phone Mic to PC"
STATS_LOG_INTERVAL = 30.0
IP_REFRESH_INTERVAL = 10.0
_ADDR_IN_USE = {errno.EADDRINUSE, getattr(errno, "WSAEADDRINUSE", errno.EADDRINUSE)}


def log_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / "pmtpc" / "pmtpc.log"


def local_ip() -> str | None:
    """The address the phone should use to reach this PC."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            # Connecting a UDP socket sends nothing; it just picks the outgoing interface.
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            return None


class TrayApp:
    def __init__(self, port: int):
        self.port = port
        self.receiver: Receiver | None = None
        self.error: str | None = None
        self.ip = local_ip()
        self._connected = False
        self._stop = threading.Event()
        self.icon = pystray.Icon("pmtpc", make_icon(64, WAITING), APP_NAME, menu=self._menu())

    def run(self) -> None:
        self.icon.run(setup=self._setup)

    @property
    def status(self) -> str:
        if self.error:
            return f"Error: {self.error}"
        r = self.receiver
        if r is None:
            return "Starting..."
        if r.connected and r.sender:
            return f"Receiving from {r.sender[0]}"
        return "Waiting for phone..."

    @property
    def vb_cable_missing(self) -> bool:
        return (
            sys.platform == "win32"
            and self.receiver is not None
            and VB_CABLE_PLAYBACK not in (self.receiver.output_name or "")
        )

    def _menu(self) -> pystray.Menu:
        item = pystray.MenuItem
        return pystray.Menu(
            item(lambda _: self.status, None, enabled=False),
            item(lambda _: f"PC address: {self.ip or 'unknown'}  (port {self.port})", None, enabled=False),
            item(
                lambda _: f"Output: {self.receiver.output_name}",
                None,
                enabled=False,
                visible=lambda _: self.receiver is not None,
            ),
            pystray.Menu.SEPARATOR,
            item("Install VB-Cable...", lambda: webbrowser.open(VB_CABLE_URL), visible=lambda _: self.vb_cable_missing),
            item("Open recording devices", self._open_recording_devices, visible=sys.platform == "win32"),
            item("Open log", self._open_log),
            item("Quit", self._quit),
        )

    def _setup(self, icon: pystray.Icon) -> None:
        icon.visible = True
        try:
            receiver = create_receiver(self.port)
        except OSError as e:
            self.error = (
                f"port {self.port} is in use. Is {APP_NAME} already running?"
                if e.errno in _ADDR_IN_USE
                else str(e)
            )
            log.error("Could not open UDP port %d: %s", self.port, e)
        else:
            try:
                receiver.start()
                self.receiver = receiver
            except Exception as e:
                receiver.stop()
                self.error = f"could not open audio output ({e})"
                log.exception("Could not start audio output")

        if self.vb_cable_missing:
            self._notify("VB-Cable is not installed, so no virtual microphone is available. "
                         "Right-click the tray icon and choose Install VB-Cable.")
        elif self.error:
            self._notify(self.error[0].upper() + self.error[1:])
        threading.Thread(target=self._watch, name="pmtpc-tray", daemon=True).start()

    def _watch(self) -> None:
        """Keep the icon, tooltip and menu in sync with the receiver."""
        shown = None
        last_stats = last_ip = time.monotonic()
        while not self._stop.wait(1.0):
            try:
                now = time.monotonic()
                r = self.receiver
                connected = bool(r and r.connected)
                if connected and not self._connected and r.sender:
                    self._notify(f"Phone connected ({r.sender[0]})")
                self._connected = connected

                if now - last_ip >= IP_REFRESH_INTERVAL:
                    self.ip, last_ip = local_ip(), now
                if r and connected and now - last_stats >= STATS_LOG_INTERVAL:
                    log.info(r.stats_line())
                    last_stats = now

                state = (self.status, self.ip, self.vb_cable_missing)
                if state != shown:
                    shown = state
                    color = PROBLEM if self.error or self.vb_cable_missing else ACTIVE if connected else WAITING
                    self.icon.icon = make_icon(64, color)
                    self.icon.title = f"{APP_NAME}: {self.status}"[:127]  # Windows tooltip limit
                    self.icon.update_menu()
            except Exception:
                log.exception("Tray update failed")

    def _notify(self, message: str) -> None:
        try:
            self.icon.notify(message, APP_NAME)
        except Exception:
            log.debug("Notifications are not supported here", exc_info=True)

    def _open_recording_devices(self) -> None:
        subprocess.Popen(["control", "mmsys.cpl,,1"])

    def _open_log(self) -> None:
        path = str(log_path())
        if sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])

    def _quit(self) -> None:
        self._stop.set()
        if self.receiver is not None:
            self.receiver.stop()
        self.icon.stop()


def main(port: int = DEFAULT_PORT) -> None:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=1, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    sys.excepthook = lambda *exc: log.critical("Unhandled error", exc_info=exc)
    threading.excepthook = lambda a: log.critical(
        "Unhandled error in thread %s", a.thread.name if a.thread else "?",
        exc_info=(a.exc_type, a.exc_value, a.exc_traceback),
    )
    log.info("Starting %s on port %d", APP_NAME, port)
    TrayApp(port).run()
