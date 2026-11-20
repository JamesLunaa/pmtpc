# pmtpc — Phone Mic to PC

Use your phone as a wireless microphone for your PC. The phone streams uncompressed 48 kHz audio over Wi-Fi (UDP), and the PC exposes it as a microphone that any app (Discord, OBS, Zoom, ...) can select.

> Status: early development. The PC receiver (Windows/Linux) and the Android app both work at a basic level; you enter the PC's IP manually.

## Windows setup

1. Install [VB-Cable](https://vb-audio.com/Cable/) (free virtual audio driver): extract it, run `VBCABLE_Setup_x64.exe` as administrator, click **Install Driver**, then reboot.
2. Download `pmtpc-setup-<version>.exe` from [Releases](https://github.com/JamesLunaa/pmtpc/releases) and run it. v0.1.0 is not code-signed: SmartScreen warns (click **More info → Run anyway**), and on PCs with **Smart App Control** turned on, Windows blocks it outright. Code signing is being set up for the next release (see [Code signing policy](#code-signing-policy)). Development builds are attached to each [Actions run](https://github.com/JamesLunaa/pmtpc/actions/workflows/windows.yml) as artifacts.
3. **Phone Mic to PC** starts in the system tray (check the `^` overflow area). Right-click it to see the status and the **PC address** to enter in the phone app.
4. In the app you want to use, select **CABLE Output (VB-Audio Virtual Cable)** as the microphone.

The installer allows the app through Windows Firewall on **private** networks only. If the phone can't connect, make sure your Wi-Fi is set to Private: Settings → Network & Internet → Wi-Fi → your network → Private network.

Tray icon colors: grey = waiting for the phone, blue = receiving, red = problem (hover or right-click for details). The log is at `%LOCALAPPDATA%\pmtpc\pmtpc.log` (tray menu → Open log).

### Running from source

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then in the project folder:

```
uv sync
uv run python -m pmtpc tray      # tray app
uv run python -m pmtpc receive   # console receiver with live stats
```

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

Run with `uv run python -m pmtpc <command>`.


- `tray [--port 50005]`: run the receiver as a system tray app (what the Windows installer launches).
- `receive [--port 50005] [--device NAME|INDEX] [--buffer 3] [--max-buffer 12]`: receive and play into the virtual cable (or the given device). `--buffer` is in 10 ms frames.
- `send [--host IP] [--port 50005] [--tone HZ] [--device NAME|INDEX] [--loss RATIO]`: test sender.
- `devices`: list audio devices.

## Code signing policy

Windows releases are signed. Free code signing provided by [SignPath.io](https://about.signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).

- Signed binaries are built by [GitHub Actions](.github/workflows/windows.yml) from this repository's source; nothing is signed from a local machine.
- Only this project's own files are signed (`pmtpc.exe` and the installer). Bundled third-party components (Python, numpy, Pillow, pystray, PortAudio) are shipped as published by their authors.
- VB-Cable is a separate third-party product and is not included.

Team roles:

- Committers and reviewers: [JamesLunaa](https://github.com/JamesLunaa)
- Approvers: [JamesLunaa](https://github.com/JamesLunaa)

## Privacy policy

This program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it. The phone app sends microphone audio only to the PC address you enter, and only while you are streaming. The PC app only receives that audio and plays it into the local virtual audio device. Neither app collects analytics or telemetry or contacts any other server.

## License

Copyright (C) 2026 Jose Cynon Luna

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. See [LICENSE](LICENSE).
