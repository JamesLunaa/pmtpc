import pytest

from pmtpc import devices

HOSTAPIS = [
    {"name": "MME", "default_output_device": 1},
    {"name": "Windows WASAPI", "default_output_device": 4},
]
DEVICES = [
    {"name": "Microphone (Realtek)", "hostapi": 0, "max_output_channels": 0},
    {"name": "Speakers (Realtek)", "hostapi": 0, "max_output_channels": 2},
    {"name": "CABLE Input (VB-Audio Virtual Cable)", "hostapi": 0, "max_output_channels": 2},
    {"name": "CABLE Output (VB-Audio Virtual Cable)", "hostapi": 1, "max_output_channels": 0},
    {"name": "Speakers (Realtek)", "hostapi": 1, "max_output_channels": 2},
    {"name": "CABLE Input (VB-Audio Virtual Cable)", "hostapi": 1, "max_output_channels": 2},
]


class FakeWasapiSettings:
    def __init__(self, auto_convert=False):
        self.auto_convert = auto_convert


@pytest.fixture
def windows(monkeypatch):
    def query_devices(i=None):
        return DEVICES if i is None else DEVICES[i]

    monkeypatch.setattr(devices.sys, "platform", "win32")
    monkeypatch.setattr(devices.sd, "query_devices", query_devices)
    monkeypatch.setattr(devices.sd, "query_hostapis", lambda i=None: HOSTAPIS if i is None else HOSTAPIS[i])
    monkeypatch.setattr(devices.sd, "WasapiSettings", FakeWasapiSettings)


def test_windows_prefers_vb_cable_on_wasapi(windows):
    device, extra = devices.resolve_output(None)
    assert device == 5
    assert extra.auto_convert


def test_windows_name_lookup_prefers_wasapi(windows):
    device, extra = devices.resolve_output("speakers")
    assert device == 4
    assert extra.auto_convert


def test_windows_mme_index_gets_no_wasapi_settings(windows):
    assert devices.resolve_output(1) == (1, None)


def test_windows_without_vb_cable_falls_back_to_wasapi_default(windows, monkeypatch, caplog):
    no_cable = [d for d in DEVICES if "CABLE" not in d["name"]]
    monkeypatch.setattr(devices.sd, "query_devices", lambda i=None: no_cable if i is None else no_cable[i])
    hostapis = [HOSTAPIS[0], {**HOSTAPIS[1], "default_output_device": 2}]
    monkeypatch.setattr(devices.sd, "query_hostapis", lambda i=None: hostapis if i is None else hostapis[i])
    device, _ = devices.resolve_output(None)
    assert device == 2
    assert "VB-Cable not found" in caplog.text
