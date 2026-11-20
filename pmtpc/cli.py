import argparse

from pmtpc.protocol import DEFAULT_PORT


def _device(value: str) -> int | str:
    return int(value) if value.isdigit() else value


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="pmtpc", description="Phone mic to PC")
    sub = parser.add_subparsers(dest="command", required=True)

    recv = sub.add_parser("receive", help="receive audio and play it to an output device")
    recv.add_argument("--port", type=int, default=DEFAULT_PORT)
    recv.add_argument("--device", type=_device, help="output device index or name (see `devices`)")
    recv.add_argument("--buffer", type=int, default=3, help="frames (10 ms each) to buffer before playback")
    recv.add_argument("--max-buffer", type=int, default=12, help="drop frames beyond this depth")

    send = sub.add_parser("send", help="test sender: stream a PC mic or tone instead of the phone")
    send.add_argument("--host", default="127.0.0.1")
    send.add_argument("--port", type=int, default=DEFAULT_PORT)
    send.add_argument("--device", type=_device, help="input device index or name (see `devices`)")
    send.add_argument("--tone", type=float, metavar="HZ", help="send a sine tone instead of the mic")
    send.add_argument("--loss", type=float, default=0.0, help="simulated packet loss ratio, e.g. 0.05")

    sub.add_parser("devices", help="list audio devices")

    args = parser.parse_args(argv)

    if args.command == "receive":
        from pmtpc.receiver import receive

        receive(args.port, args.device, args.buffer, args.max_buffer)
    elif args.command == "send":
        from pmtpc.sender import Sender

        sender = Sender(args.host, args.port, args.loss)
        if args.tone:
            sender.stream_tone(args.tone)
        else:
            sender.stream_mic(args.device)
    elif args.command == "devices":
        import sounddevice as sd

        print(sd.query_devices())
