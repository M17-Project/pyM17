"""Reflector client: M17 over UDP as in the M17 Internet Interface specification
(https://github.com/M17-Project/M17_inet), spoken by mrefd. Default port 17000.

Datagrams (big-endian, CRC = M17 CRC-16):

- ``M17 `` stream frame, 54 bytes: stream ID (2), LSF without CRC (28),
  frame number (2), payload (16), CRC over the preceding 52 bytes.
- ``M17P`` packet, 38 to 859 bytes: LSF with CRC (30), then the packet
  (protocol byte, data and CRC, as built by :func:`m17.packet.build_packet`).
- Control: ``CONN``/``LSTN`` + callsign + module, ``ACKN``, ``NACK``,
  ``PING``/``PONG`` + callsign, ``DISC`` (+ callsign).

>>> with ReflectorClient("m17-m17.example.org", "N0CALL", "A") as ref:
...     ref.send_packet(LSF(dst="@ALL", src="N0CALL", type=PACKET | DATA), sms("Hello"))
...     for item in ref.receive(timeout=30):
...         print(item)
"""

import random
import socket
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from .callsign import callsign_from_bytes, callsign_to_bytes
from .crc import crc16
from .lsf import LSF, crc_ok

PORT = 17000
KEEPALIVE = 10.0  # seconds between our own PONGs
LINK_TIMEOUT = 30.0  # seconds of silence after which the link is considered lost


@dataclass
class IPStreamFrame:
    stream_id: int
    lsf: LSF
    fn: int  # 0 to 0x7FFF
    last: bool
    payload: bytes  # 16 bytes


@dataclass
class IPPacket:
    lsf: LSF
    packet: bytes  # protocol byte, data, CRC
    crc_ok: bool  # both the LSF and the packet CRC

    @property
    def protocol(self) -> int:
        return self.packet[0]

    @property
    def data(self) -> bytes:
        return self.packet[1:-2]


def encode_stream_frame(stream_id: int, lsf: LSF, fn: int, payload: bytes, last: bool = False) -> bytes:
    """A 54-byte ``M17 `` datagram."""
    if len(payload) != 16:
        raise ValueError("stream payload must be 16 bytes")
    fn = (fn & 0x7FFF) | (0x8000 if last else 0)
    body = b"M17 " + (stream_id & 0xFFFF).to_bytes(2, "big") + lsf.to_bytes()[:28] + fn.to_bytes(2, "big") + payload
    return body + crc16(body).to_bytes(2, "big")


def encode_packet(lsf: LSF, packet: bytes) -> bytes:
    """An ``M17P`` datagram. ``packet`` is protocol byte, data and CRC.

    At least one byte of data is required: a 37-byte datagram would look like a
    reflector interlink packet.
    """
    if not 4 <= len(packet) <= 825:
        raise ValueError("packet must have 1 to 822 bytes of data besides the protocol byte and the CRC")
    return b"M17P" + lsf.to_bytes() + bytes(packet)


def decode(datagram: bytes) -> IPStreamFrame | IPPacket | None:
    """Parse a stream or packet datagram, None for anything else or a bad CRC (streams)."""
    if datagram[:4] == b"M17 " and len(datagram) >= 54 and crc16(datagram[:54]) == 0:
        fn = int.from_bytes(datagram[34:36], "big")
        return IPStreamFrame(
            stream_id=int.from_bytes(datagram[4:6], "big"),
            lsf=LSF.from_bytes(datagram[6:34]),
            fn=fn & 0x7FFF,
            last=bool(fn & 0x8000),
            payload=datagram[36:52],
        )
    if datagram[:4] == b"M17P" and 38 <= len(datagram) <= 859:
        lsf_bytes, packet = datagram[4:34], datagram[34:]
        return IPPacket(LSF.from_bytes(lsf_bytes), packet, crc_ok(lsf_bytes) and crc16(packet) == 0)
    return None


class ReflectorClient:
    """A client linked to one module of an M17 reflector."""

    def __init__(self, host: str, callsign: str, module: str = "A", port: int = PORT, listen_only: bool = False):
        if len(module) != 1 or not "A" <= module <= "Z":
            raise ValueError("module must be a letter A to Z")
        family, _, _, _, self.address = socket.getaddrinfo(host, port, type=socket.SOCK_DGRAM)[0]
        self.callsign = callsign
        self.module = module
        self.listen_only = listen_only
        self._sock = socket.socket(family, socket.SOCK_DGRAM)
        self._cs = callsign_to_bytes(callsign)
        self.last_heard = 0.0  # time.monotonic() of the last packet from the reflector
        self.reflector = ""  # the reflector's callsign, from its PINGs
        self._last_pong = 0.0

    def __enter__(self) -> "ReflectorClient":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def connect(self, timeout: float = 5.0) -> None:
        """Link to the module. Raises ConnectionError on NACK or no answer."""
        magic = b"LSTN" if self.listen_only else b"CONN"
        self._sock.sendto(magic + self._cs + self.module.encode(), self.address)
        deadline = time.monotonic() + timeout
        while (left := deadline - time.monotonic()) > 0:
            data = self._recv(left)
            if data is None:
                break
            if data[:4] == b"ACKN":
                self._pong()
                return
            if data[:4] == b"NACK":
                raise ConnectionError(f"reflector refused the link to module {self.module}")
        raise ConnectionError("no answer from the reflector")

    @property
    def link_lost(self) -> bool:
        """True after 30 seconds without anything from the reflector."""
        return time.monotonic() - self.last_heard > LINK_TIMEOUT

    def _pong(self) -> None:
        self._sock.sendto(b"PONG" + self._cs, self.address)
        self._last_pong = time.monotonic()

    def close(self) -> None:
        """Unlink and close the socket."""
        try:
            self._sock.sendto(b"DISC" + self._cs, self.address)
        finally:
            self._sock.close()

    def send_stream(self, lsf: LSF, payloads: Iterable[bytes], stream_id: int | None = None, pace: bool = True) -> None:
        """Send a stream, one datagram per 16-byte payload, paced at 40 ms per frame."""
        sid = random.randint(1, 0xFFFF) if stream_id is None else stream_id
        payloads = list(payloads)
        start = time.monotonic()
        for fn, payload in enumerate(payloads):
            if pace:
                time.sleep(max(0.0, start + fn * 0.04 - time.monotonic()))
            self._sock.sendto(encode_stream_frame(sid, lsf, fn, payload, fn == len(payloads) - 1), self.address)

    def send_packet(self, lsf: LSF, packet: bytes) -> None:
        """Send a packet, e.g. ``send_packet(lsf, sms("Hello"))``."""
        self._sock.sendto(encode_packet(lsf, packet), self.address)

    def receive(self, timeout: float | None = None) -> Iterator[IPStreamFrame | IPPacket]:
        """Yield stream frames and packets, keeping the link alive. Ends after ``timeout``
        seconds without stream or packet traffic (None: never), when the reflector unlinks
        us, or when the link is lost (see :attr:`link_lost`)."""
        while True:
            data = self._recv(timeout)
            if data is None or data[:4] == b"DISC" or self.link_lost:
                return
            item = decode(data)
            if item is not None:
                yield item

    def _recv(self, timeout: float | None) -> bytes | None:
        """Next datagram from the reflector, answering PINGs and sending a PONG at least
        every 10 seconds. None after ``timeout`` seconds or when the link is lost."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            now = time.monotonic()
            if self._last_pong and now - self._last_pong >= KEEPALIVE:
                self._pong()
            if self.last_heard and self.link_lost:
                return None
            if deadline is not None and deadline <= now:
                return None
            wait = KEEPALIVE - (now - self._last_pong) if self._last_pong else KEEPALIVE
            if deadline is not None:
                wait = min(wait, deadline - now)
            self._sock.settimeout(max(wait, 0.01))
            try:
                data, addr = self._sock.recvfrom(1024)
            except TimeoutError:
                continue
            if addr[:2] != self.address[:2]:  # not from the reflector
                continue
            self.last_heard = time.monotonic()
            if data[:4] in (b"PING", b"PONG") and len(data) >= 10:
                self.reflector = callsign_from_bytes(data[4:10])
                self._pong()
                continue
            return data
