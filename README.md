# pmtpc — Phone Mic to PC

Use your phone as a wireless microphone for your PC. The phone streams uncompressed 48 kHz audio over Wi-Fi (UDP), and the PC exposes it as a microphone that any app (Discord, OBS, Zoom, ...) can select.

> Status: early development. The PC receiver (Windows/Linux) and the Android app both work at a basic level; you enter the PC's IP manually.

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

## Android app

Requires Android 8.0 or newer. Build it with JDK 17+ and the Android SDK:

```
cd android
./gradlew assembleDebug
adb install app/build/outputs/apk/debug/app-debug.apk
```

Or copy `android/app/build/outputs/apk/debug/app-debug.apk` to the phone and open it (allow installing unknown apps).

In the app, enter the PC's IP address (`ipconfig` on Windows), pick a microphone mode, and tap **Start**. Streaming continues with the screen off; stop it from the app or the notification. The phone and PC must be on the same Wi-Fi network.

Microphone modes:
- **Standard**: the phone's default mic processing.
- **Raw**: unprocessed audio, for the most natural sound (falls back to minimal processing if the phone doesn't support raw capture).
- **Voice**: noise suppression and echo cancellation, for calls in noisy rooms.

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

## License

Copyright (C) 2026 Jose Cynon Luna

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. See [LICENSE](LICENSE).
