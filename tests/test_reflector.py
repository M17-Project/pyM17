"""Reflector client against a fake mrefd that checks datagrams like mrefd does."""

import socket
import threading
import time

import pytest

import m17
from m17 import reflector
from m17.callsign import callsign_from_bytes, callsign_to_bytes
from m17.crc import crc16
from m17.lsf import DATA, LSF, PACKET, STREAM, VOICE


def test_stream_datagram_layout():
    lsf = LSF(dst="#M17", src="N0CALL", type=STREAM | VOICE)
    d = reflector.encode_stream_frame(0xBEEF, lsf, 0x123, bytes(range(16)), last=True)
    # offsets as in mrefd's CPacket
    assert len(d) == 54 and d[:4] == b"M17 " and d[4:6] == b"\xbe\xef"
    assert callsign_from_bytes(d[6:12]) == "#M17" and callsign_from_bytes(d[12:18]) == "N0CALL"
    assert d[18:20] == (STREAM | VOICE).to_bytes(2, "big") and d[34:36] == (0x8123).to_bytes(2, "big")
    assert d[36:52] == bytes(range(16)) and int.from_bytes(d[52:54], "big") == crc16(d[:52])
    item = reflector.decode(d)
    assert item == reflector.IPStreamFrame(0xBEEF, lsf, 0x123, True, bytes(range(16)))
    assert reflector.decode(d[:53] + bytes([d[53] ^ 1])) is None  # bad CRC


def test_packet_datagram_layout():
    lsf = LSF(dst="SP5WWP", src="N0CALL", type=PACKET | DATA)
    pkt = m17.sms("Hello reflector")
    d = reflector.encode_packet(lsf, pkt)
    assert d[:4] == b"M17P" and len(d) == 34 + len(pkt)
    # mrefd CalcCRC(): LSF CRC at 32 over bytes 4..31, packet CRC at the end over bytes 34..
    assert int.from_bytes(d[32:34], "big") == crc16(d[4:32])
    assert int.from_bytes(d[-2:], "big") == crc16(d[34:-2])
    item = reflector.decode(d)
    assert item.crc_ok and item.lsf == lsf and item.protocol == 5 and item.data == b"Hello reflector\0"


class FakeMrefd(threading.Thread):
    """Accepts module A, sends PINGs, records what it gets, then plays traffic back."""

    def __init__(self):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(5)
        self.port = self.sock.getsockname()[1]
        self.got: list[bytes] = []
        self.errors: list[str] = []
        self.client = None

    def check(self, d: bytes) -> None:
        if d[:4] == b"M17 ":
            if len(d) != 54 or not d[19] & 1 or crc16(d[:54]) != 0:
                self.errors.append("bad stream datagram")
        elif d[:4] == b"M17P":
            if d[17] & 1 or crc16(d[4:34]) != 0 or crc16(d[34:]) != 0:
                self.errors.append("bad packet datagram")

    def run(self):
        me = callsign_to_bytes("M17-TST")
        while True:
            try:
                d, addr = self.sock.recvfrom(1024)
            except TimeoutError:
                return
            self.got.append(d)
            self.check(d)
            if d[:4] in (b"CONN", b"LSTN") and len(d) == 11:
                if chr(d[10]) == "A":
                    self.client = addr
                    self.sock.sendto(b"ACKN", addr)
                    self.sock.sendto(b"PING" + me, addr)
                else:
                    self.sock.sendto(b"NACK", addr)
            elif d[:4] == b"M17P":  # play some traffic back to the client
                lsf = LSF(dst="@ALL", src="SP5WWP")
                for fn in range(3):
                    self.sock.sendto(reflector.encode_stream_frame(7, lsf, fn, bytes([fn]) * 16, fn == 2), addr)
                self.sock.sendto(b"PING" + me, addr)
                self.sock.sendto(d, addr)
                self.sock.sendto(b"DISC" + me, addr)
            elif d[:4] == b"DISC":
                self.sock.sendto(b"DISC", addr)
                return


def test_client_session():
    srv = FakeMrefd()
    srv.start()
    lsf = LSF(dst="@ALL", src="N0CALL", type=PACKET | DATA)
    with reflector.ReflectorClient("127.0.0.1", "N0CALL", "A", port=srv.port) as ref:
        ref.send_stream(LSF(dst="@ALL", src="N0CALL"), [bytes(16)] * 3, stream_id=42, pace=False)
        ref.send_packet(lsf, m17.sms("Hi"))
        items = list(ref.receive(timeout=2))
        assert ref.reflector == "M17-TST"
    srv.join(3)
    assert not srv.errors
    assert [i.fn for i in items if isinstance(i, reflector.IPStreamFrame)] == [0, 1, 2]
    assert items[2].last and items[-1] == reflector.IPPacket(lsf, m17.sms("Hi"), True)
    sent = srv.got
    assert sent[0] == b"CONN" + callsign_to_bytes("N0CALL") + b"A"
    assert b"PONG" + callsign_to_bytes("N0CALL") in sent  # answered the keep-alives
    streams = [d for d in sent if d[:4] == b"M17 "]
    assert len(streams) == 3 and streams[-1][34] & 0x80 and all(d[4:6] == b"\x00\x2a" for d in streams)
    assert sent[-1] == b"DISC" + callsign_to_bytes("N0CALL")


def test_client_refused():
    srv = FakeMrefd()
    srv.start()
    ref = reflector.ReflectorClient("127.0.0.1", "N0CALL", "B", port=srv.port)
    with pytest.raises(ConnectionError):
        ref.connect(timeout=2)
    ref.close()
    srv.join(3)


def test_packet_needs_data():
    # a 37-byte M17P datagram would look like a reflector interlink packet (M17_inet)
    lsf = LSF(dst="@ALL", src="N0CALL", type=PACKET | DATA)
    with pytest.raises(ValueError):
        reflector.encode_packet(lsf, m17.build_packet(5, b""))
    assert len(reflector.encode_packet(lsf, m17.build_packet(5, b"x"))) == 38


def test_keepalive_and_link_loss(monkeypatch):
    """With a silent reflector, the client sends its own PONGs, then reports the link lost."""
    monkeypatch.setattr(reflector, "KEEPALIVE", 0.2)
    monkeypatch.setattr(reflector, "LINK_TIMEOUT", 0.9)
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind(("127.0.0.1", 0))
    srv.settimeout(3)
    got = []

    def silent_reflector():
        d, addr = srv.recvfrom(64)  # CONN
        srv.sendto(b"ACKN", addr)
        srv.settimeout(1.5)
        try:
            while True:
                got.append(srv.recvfrom(64)[0])
        except TimeoutError:
            pass

    t = threading.Thread(target=silent_reflector, daemon=True)
    t.start()
    ref = reflector.ReflectorClient("127.0.0.1", "N0CALL", "A", port=srv.getsockname()[1])
    ref.connect(timeout=2)
    start = time.monotonic()
    assert list(ref.receive(timeout=10)) == []  # ends on link loss, long before the timeout
    assert ref.link_lost and time.monotonic() - start < 2
    ref._sock.close()
    t.join(3)
    srv.close()
    assert got.count(b"PONG" + callsign_to_bytes("N0CALL")) >= 3
