"""Pick the output device the receiver plays into, which the OS then exposes as a microphone."""

import logging
import sys
from typing import Any

import sounddevice as sd

# VB-Audio Virtual Cable: audio played into "CABLE Input" comes out of the "CABLE Output" recording device.
VB_CABLE_PLAYBACK = "CABLE Input"
VB_CABLE_URL = "https://vb-audio.com/Cable/"
WASAPI = "Windows WASAPI"
# Host APIs to try, in order. WDM-KS is left out: it often fails with virtual drivers such as VB-Cable.
WINDOWS_HOSTAPIS = (WASAPI, "Windows DirectSound", "MME")

log = logging.getLogger(__name__)

# (device, extra_settings) as passed to `sd.OutputStream`.
Candidate = tuple[int | str | None, Any]


def output_candidates(device: int | str | None) -> list[Candidate]:
    """Output devices to try, best first; the receiver uses the first one that opens."""
    if sys.platform == "win32":
        return _windows_candidates(device)
    if sys.platform.startswith("linux") and device is None:
        return [(_linux_default(), None)]
    return [(device, None)]


def vb_cable_installed() -> bool:
    """True if VB-Cable shows up under any host API, even one we don't use (e.g. before a reboot)."""
    return bool(_find_outputs(VB_CABLE_PLAYBACK, any_hostapi=True))


def describe(device: int | str | None) -> str:
    if isinstance(device, int):
        d = sd.query_devices(device)
        return f"{d['name']} [{sd.query_hostapis(d['hostapi'])['name']}]"
    return "default output" if device is None else device


def log_output_devices() -> None:
    log.info("Output devices:")
    for i, d in enumerate(sd.query_devices()):
        if d["max_output_channels"] > 0:
            log.info("  #%d %s (%d ch)", i, describe(i), d["max_output_channels"])


def _windows_candidates(device: int | str | None) -> list[Candidate]:
    if isinstance(device, int):
        return [_with_settings(device)]
    if device is not None:
        return [_with_settings(i) for i in _find_outputs(device)] or [(device, None)]

    found = _find_outputs(VB_CABLE_PLAYBACK)
    if not found:
        if vb_cable_installed():
            log.warning(
                "VB-Cable is installed but not active yet. Restart Windows, or enable CABLE Input in "
                "Sound settings. Playing to the default output for now."
            )
        else:
            log.warning(
                "VB-Cable not found, playing to the default output instead. "
                "Install it from %s to get a virtual microphone.",
                VB_CABLE_URL,
            )
        found = _default_outputs()
    return [_with_settings(i) for i in found]


def _with_settings(device: int) -> Candidate:
    if _hostapi_name(device) == WASAPI:
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


def _hostapi_name(device: int) -> str:
    return sd.query_hostapis(sd.query_devices(device)["hostapi"])["name"]


def _rank(device: int) -> int:
    name = _hostapi_name(device)
    return WINDOWS_HOSTAPIS.index(name) if name in WINDOWS_HOSTAPIS else len(WINDOWS_HOSTAPIS)


def _find_outputs(name: str, any_hostapi: bool = False) -> list[int]:
    """Output devices whose name contains `name` (case-insensitive), best host API first.

    On Windows each device is listed once per host API (MME, DirectSound, WASAPI, ...), so a
    plain name lookup in sounddevice would be ambiguous.
    """
    needle = name.lower()
    found = [
        i
        for i, d in enumerate(sd.query_devices())
        if d["max_output_channels"] > 0
        and needle in d["name"].lower()
        and (any_hostapi or _hostapi_name(i) in WINDOWS_HOSTAPIS)
    ]
    return sorted(found, key=_rank)


def _default_outputs() -> list[int]:
    apis = [api["name"] for api in sd.query_hostapis()]
    defaults = []
    for name in WINDOWS_HOSTAPIS:
        if name in apis:
            device = sd.query_hostapis(apis.index(name))["default_output_device"]
            if device >= 0:
                defaults.append(device)
    return defaults
