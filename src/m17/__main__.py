"""Command line tools.

  python -m m17 sms --src N0CALL --dst @ALL "Hello" > msg.sym
  python -m m17 decode msg.sym

Symbol files hold 32-bit little-endian floats, one per symbol, as written by
``m17-packet-encode -f`` and read by ``m17-packet-decode`` (M17_Implementations).
"""

import argparse
import struct
import sys

from .frames import LSFFrame, PacketFrame, StreamFrame
from .lsf import DATA, LSF, PACKET, can
from .packet import PROTOCOL_SMS, Packet, sms
from .receiver import EndOfTransmission, Receiver
from .transmission import encode_packet


def _write_symbols(symbols, path: str) -> None:
    data = struct.pack(f"<{len(symbols)}f", *symbols)
    if path == "-":
        sys.stdout.buffer.write(data)
    else:
        with open(path, "wb") as f:
            f.write(data)


def _read_symbols(path: str):
    data = sys.stdin.buffer.read() if path == "-" else open(path, "rb").read()
    n = len(data) // 4
    return struct.unpack(f"<{n}f", data[: 4 * n])


def _cmd_sms(args) -> None:
    lsf = LSF(dst=args.dst, src=args.src, type=PACKET | DATA | can(args.can))
    _write_symbols(encode_packet(lsf, sms(args.text)), args.output)


def _cmd_decode(args) -> None:
    rx = Receiver(threshold=args.threshold)
    for event in rx.feed(_read_symbols(args.input)):
        if isinstance(event, LSFFrame):
            lsf = event.lsf
            crc = "OK" if event.crc_ok else "error"
            print(f"LSF {lsf.src} -> {lsf.dst}, TYPE {lsf.type:04X}, CAN {lsf.can}, META {lsf.meta.hex()}, CRC {crc}")
        elif isinstance(event, StreamFrame):
            last = " (last)" if event.last else ""
            print(f"Stream frame {event.fn}{last}: {event.payload.hex()}, errors ~{event.metric / 0xFFFF:.1f}")
        elif isinstance(event, PacketFrame) and args.verbose:
            print(f"Packet frame {event.counter}{' (last)' if event.last else ''}, errors ~{event.metric / 0xFFFF:.1f}")
        elif isinstance(event, Packet):
            crc = "OK" if event.crc_ok else "error"
            body = repr(event.text) if event.protocol == PROTOCOL_SMS else event.data.hex()
            print(f"Packet, protocol {event.protocol}, CRC {crc}: {body}")
        elif isinstance(event, EndOfTransmission):
            print("End of transmission")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m m17", description="M17 encoder and decoder")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("sms", help="encode a text message to symbols")
    p.add_argument("text")
    p.add_argument("--src", required=True, help="source callsign")
    p.add_argument("--dst", default="@ALL", help="destination callsign (default @ALL)")
    p.add_argument("--can", type=int, default=0, help="Channel Access Number (default 0)")
    p.add_argument("-o", "--output", default="-", help="symbol file (default stdout)")
    p.set_defaults(func=_cmd_sms)

    p = sub.add_parser("decode", help="decode a symbol file")
    p.add_argument("input", nargs="?", default="-", help="symbol file (default stdin)")
    p.add_argument("-t", "--threshold", type=float, default=2.0, help="syncword distance threshold")
    p.add_argument("-v", "--verbose", action="store_true", help="also show individual packet frames")
    p.set_defaults(func=_cmd_decode)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
