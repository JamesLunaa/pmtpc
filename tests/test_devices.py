import pytest

from pmtpc import devices, receiver

HOSTAPIS = [
    {"name": "MME", "default_output_device": 1},
    {"name": "Windows DirectSound", "default_output_device": 3},
    {"name": "Windows WASAPI", "default_output_device": 5},
    {"name": "Windows WDM-KS", "default_output_device": -1},
]
SPEAKERS = "Speakers (Realtek)"
CABLE = "CABLE Input (VB-Audio Virtual Cable)"
DEVICES = [
    {"name": "Microphone (Realtek)", "hostapi": 0, "max_output_channels": 0},
    {"name": SPEAKERS, "hostapi": 0, "max_output_channels": 2},
    {"name": CABLE, "hostapi": 0, "max_output_channels": 2},
    {"name": SPEAKERS, "hostapi": 1, "max_output_channels": 2},
    {"name": CABLE, "hostapi": 1, "max_output_channels": 2},
    {"name": SPEAKERS, "hostapi": 2, "max_output_channels": 2},
    {"name": CABLE, "hostapi": 2, "max_output_channels": 2},
    {"name": "CABLE Output (VB-Audio Virtual Cable)", "hostapi": 2, "max_output_channels": 0},
    {"name": SPEAKERS, "hostapi": 3, "max_output_channels": 2},
    {"name": CABLE, "hostapi": 3, "max_output_channels": 2},
]


class FakeWasapiSettings:
    def __init__(self, auto_convert=False):
        self.auto_convert = auto_convert


def use_devices(monkeypatch, device_list):
    monkeypatch.setattr(devices.sd, "query_devices", lambda i=None: device_list if i is None else device_list[i])


@pytest.fixture
def windows(monkeypatch):
    monkeypatch.setattr(devices.sys, "platform", "win32")
    monkeypatch.setattr(devices.sd, "query_hostapis", lambda i=None: HOSTAPIS if i is None else HOSTAPIS[i])
    monkeypatch.setattr(devices.sd, "WasapiSettings", FakeWasapiSettings)
    use_devices(monkeypatch, DEVICES)


def test_vb_cable_tried_on_wasapi_then_directsound_then_mme_never_wdm_ks(windows):
    candidates = devices.output_candidates(None)
    assert [d for d, _ in candidates] == [6, 4, 2]
    assert candidates[0][1].auto_convert
    assert candidates[1][1] is None


def test_name_lookup_is_ranked_by_host_api(windows):
    assert [d for d, _ in devices.output_candidates("speakers")] == [5, 3, 1]


def test_explicit_index_is_used_as_is(windows):
    assert devices.output_candidates(1) == [(1, None)]


def test_vb_cable_only_on_wdm_ks_means_restart_needed(windows, monkeypatch, caplog):
    # Seen right after installing VB-Cable, before rebooting Windows.
    use_devices(monkeypatch, [d for d in DEVICES if d["name"] != CABLE or d["hostapi"] == 3])
    candidates = devices.output_candidates(None)
    assert [devices.sd.query_devices(d)["name"] for d, _ in candidates] == [SPEAKERS] * 3
    assert devices.vb_cable_installed()
    assert "not active yet" in caplog.text


def test_vb_cable_missing_falls_back_to_defaults(windows, monkeypatch, caplog):
    no_cable = [d for d in DEVICES if "CABLE" not in d["name"]]
    use_devices(monkeypatch, no_cable)
    hostapis = [{**api, "default_output_device": -1} for api in HOSTAPIS]
    hostapis[2]["default_output_device"] = 3  # WASAPI speakers in the filtered list
    monkeypatch.setattr(devices.sd, "query_hostapis", lambda i=None: hostapis if i is None else hostapis[i])
    assert [d for d, _ in devices.output_candidates(None)] == [3]
    assert not devices.vb_cable_installed()
    assert "VB-Cable not found" in caplog.text


def test_receiver_falls_through_to_next_device(windows, monkeypatch):
    opened = []

    class FakeStream:
        def __init__(self, device, **kwargs):
            self.device = device

        def start(self):
            if self.device == 6:
                raise devices.sd.PortAudioError("Error starting stream")
            opened.append(self.device)

        def close(self):
            pass

    monkeypatch.setattr(receiver.sd, "OutputStream", FakeStream)
    r = receiver.Receiver(0, devices.output_candidates(None))
    try:
        r.start()
        assert opened == [4]
        assert r.output_name == f"{CABLE} [Windows DirectSound]"
    finally:
        r.stop()
