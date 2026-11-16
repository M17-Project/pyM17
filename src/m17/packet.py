"""Packet mode: building packets, splitting them into frames and reassembling them.

A packet is a protocol byte, the data and a CRC, at most 33 frames of 25 bytes.
"""

from dataclasses import dataclass

from .crc import crc16
from .frames import PacketFrame

PROTOCOL_RAW = 0x00
PROTOCOL_AX25 = 0x01
PROTOCOL_APRS = 0x02
PROTOCOL_6LOWPAN = 0x03
PROTOCOL_IPV4 = 0x04
PROTOCOL_SMS = 0x05
PROTOCOL_WINLINK = 0x06

MAX_PACKET = 33 * 25  # bytes, including the protocol byte and the CRC


def build_packet(protocol: int, data: bytes) -> bytes:
    """Protocol byte, data and CRC. Raises ValueError if it does not fit 33 frames."""
    body = bytes([protocol]) + bytes(data)
    if len(body) + 2 > MAX_PACKET:
        raise ValueError(f"packet too long: {len(body) + 2} > {MAX_PACKET} bytes")
    return body + crc16(body).to_bytes(2, "big")


def sms(text: str) -> bytes:
    """A text message packet (UTF-8, NUL-terminated)."""
    return build_packet(PROTOCOL_SMS, text.encode() + b"\0")


def split_packet(packet: bytes) -> list[tuple[bytes, int, bool]]:
    """Split a packet into (chunk, counter, last) for :func:`m17.frames.packet_frame`."""
    out = []
    for n, start in enumerate(range(0, len(packet), 25)):
        chunk = packet[start : start + 25]
        last = start + 25 >= len(packet)
        out.append((chunk, len(chunk) if last else n, last))
    return out


@dataclass
class Packet:
    protocol: int
    data: bytes  # without the protocol byte and the CRC
    crc_ok: bool

    @property
    def text(self) -> str:
        """The message of an SMS packet."""
        return self.data.split(b"\0", 1)[0].decode(errors="replace")


class PacketAssembler:
    """Collects packet frames, returns the packet when its last frame arrives."""

    def __init__(self) -> None:
        self._data = bytearray()
        self._next = 0

    def reset(self) -> None:
        self._data.clear()
        self._next = 0

    def add(self, frame: PacketFrame) -> Packet | None:
        if frame.last:
            if not 1 <= frame.counter <= 25:
                self.reset()
                return None
            raw = bytes(self._data) + frame.data[: frame.counter]
            self.reset()
            if len(raw) < 3:
                return None
            return Packet(raw[0], raw[1:-2], crc16(raw) == 0)
        if frame.counter != self._next:  # missed a frame: start over
            self.reset()
            if frame.counter != 0:
                return None
        self._data += frame.data
        self._next = frame.counter + 1
        if self._next > 32:
            self.reset()
        return None
