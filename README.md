# pmtpc — Phone Mic to PC

Use your phone as a wireless microphone for your PC. The phone streams uncompressed 48 kHz audio over Wi-Fi (UDP), and the PC exposes it as a microphone that any app (Discord, OBS, Zoom, ...) can select.

> Status: the PC receiver works. The Android app is not built yet; use the test sender (below) in its place.

## Windows setup

1. Install [VB-Cable](https://vb-audio.com/Cable/) (free virtual audio driver): extract it, run `VBCABLE_Setup_x64.exe` as administrator, then reboot.
2. Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then in the project folder run:
   ```
   uv sync
   ```
3. Start the receiver:
   ```
   uv run python -m pmtpc receive
   ```
   It should print `output: CABLE Input (VB-Audio Virtual Cable)`. When Windows Firewall asks, allow access on **Private networks**, and make sure your Wi-Fi is set to Private, not Public.
4. In the app you want to use, select **CABLE Output (VB-Audio Virtual Cable)** as the microphone.

## Testing without the phone

Stream a test tone or a PC mic to the receiver, from the same machine or another one on the network:

```
uv run python -m pmtpc send --tone 440                          # same machine
uv run python -m pmtpc send --host 192.168.1.50 --tone 440      # receiver's IP
uv run python -m pmtpc send --host 192.168.1.50 --loss 0.05     # PC mic, 5% simulated packet loss
```

To hear it on Windows: Sound settings → More sound settings → Recording → CABLE Output → Properties → Listen → "Listen to this device".

## Commands

- `receive [--port 50005] [--device NAME|INDEX] [--buffer 3] [--max-buffer 12]`: receive and play into the virtual cable (or the given device). `--buffer` is in 10 ms frames.
- `send [--host IP] [--port 50005] [--tone HZ] [--device NAME|INDEX] [--loss RATIO]`: test sender.
- `devices`: list audio devices.
