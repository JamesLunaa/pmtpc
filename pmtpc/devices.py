"""Pick the output device the receiver plays into, which the OS then exposes as a microphone."""

import logging
import sys
from typing import Any

import sounddevice as sd

# VB-Audio Virtual Cable: audio played into "CABLE Input" comes out of the "CABLE Output" recording device.
VB_CABLE_PLAYBACK = "CABLE Input"
VB_CABLE_URL = "https://vb-audio.com/Cable/"
WASAPI = "Windows WASAPI"

log = logging.getLogger(__name__)


def resolve_output(device: int | str | None) -> tuple[int | str | None, Any]:
    """Return (device, extra_settings) to pass to `sd.OutputStream`."""
    if sys.platform == "win32":
        return _resolve_windows(device)
    if sys.platform.startswith("linux") and device is None:
        return _linux_default(), None
    return device, None


def _resolve_windows(device: int | str | None) -> tuple[int | str | None, Any]:
    wasapi = _hostapi_index(WASAPI)
    if device is None:
        device = _find_output(VB_CABLE_PLAYBACK, wasapi)
        if device is None:
            log.warning(
                "VB-Cable not found, playing to the default output instead. "
                "Install it from %s to get a virtual microphone.",
                VB_CABLE_URL,
            )
            if wasapi is not None:
                device = sd.query_hostapis(wasapi)["default_output_device"]
    elif isinstance(device, str):
        found = _find_output(device, wasapi)
        device = device if found is None else found

    if wasapi is not None and isinstance(device, int) and sd.query_devices(device)["hostapi"] == wasapi:
        # Shared-mode WASAPI only accepts the device's mix format; let Windows resample if it isn't 48 kHz.
        return device, sd.WasapiSettings(auto_convert=True)
    return device, None


def _linux_default() -> str | None:
    # PortAudio's ALSA `default` may have no outputs, so prefer the PipeWire/Pulse plugs.
    names = {d["name"] for d in sd.query_devices() if d["max_output_channels"] > 0}
    for name in ("pipewire", "pulse"):
        if name in names:
            return name
    return None


def _hostapi_index(name: str) -> int | None:
    for i, api in enumerate(sd.query_hostapis()):
        if api["name"] == name:
            return i
    return None


def _find_output(name: str, preferred_hostapi: int | None) -> int | None:
    """Find an output device by case-insensitive substring, preferring the given host API.

    On Windows each device is listed once per host API (MME, DirectSound, WASAPI, ...), so a
    plain name lookup in sounddevice would be ambiguous.
    """
    needle = name.lower()
    matches = [
        i
        for i, d in enumerate(sd.query_devices())
        if d["max_output_channels"] > 0 and needle in d["name"].lower()
    ]
    if not matches:
        return None
    for i in matches:
        if sd.query_devices(i)["hostapi"] == preferred_hostapi:
            return i
    return matches[0]
