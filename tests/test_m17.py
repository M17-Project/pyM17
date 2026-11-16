"""Behaviour tests: round trips, packets, the receiver and the command line tool."""

import json
import random
import struct
import subprocess
import sys
from pathlib import Path

import pytest

import m17
from m17 import phy
from m17.callsign import BROADCAST, decode_callsign, encode_callsign
from m17.crc import crc16
from m17.lsf import DATA, LSF, PACKET, Position, can

ROOT = Path(__file__).parent


# ---- callsigns


@pytest.mark.parametrize("text", ["N0CALL", "SP5WWP", "#M17", "@ALL", "A1B2C3D4E", "#ABCDEFGH", "-/."])
def test_callsign_round_trip(text):
    assert decode_callsign(encode_callsign(text)) == text


def test_callsign_rules():
    assert encode_callsign("sp5wwp") == encode_callsign("SP5WWP")
    assert decode_callsign(encode_callsign("A*B")) == "A B"  # invalid characters become spaces
    assert encode_callsign("@ALL") == BROADCAST
    assert decode_callsign(0) == ""
    assert decode_callsign(40**9 + 40**8) == ""  # reserved space
    with pytest.raises(ValueError):
        encode_callsign("TOOLONGCALL")


# ---- LSF


def test_lsf_bytes_and_lich():
    lsf = LSF(dst="@ALL", src="SP5WWP", type=PACKET | DATA | can(9), meta=bytes(range(14)))
    data = lsf.to_bytes()
    assert len(data) == 30 and crc16(data) == 0 and m17.lsf.crc_ok(data)
    assert LSF.from_bytes(data) == lsf and lsf.can == 9
    assert b"".join(lsf.lich(n)[:5] for n in range(6)) == data
    assert [lsf.lich(n)[5] for n in range(6)] == [n << 5 for n in range(6)]
    with pytest.raises(ValueError):
        lsf.lich(6)


def test_position_round_trip():
    pos = Position(lat=52.2297, lon=21.0122, altitude=110.5, bearing=270, speed=12.5, radius=4.0, source=1, station=2)
    back = Position.from_meta(pos.to_meta())
    assert back.lat == pytest.approx(pos.lat, abs=1e-5) and back.lon == pytest.approx(pos.lon, abs=1e-5)
    assert (back.altitude, back.bearing, back.speed, back.radius) == (110.5, 270, 12.5, 4.0)
    assert (back.validity, back.source, back.station) == (0xF, 1, 2)


def test_position_fields_masked():
    meta = Position(lat=0, lon=0, source=0x1F, station=0x13, validity=0x1A).to_meta()
    back = Position.from_meta(meta)
    assert (back.source, back.station, back.validity) == (0xF, 0x3, 0xA)


# ---- packets


@pytest.mark.parametrize("size", [1, 21, 22, 23, 48, 821])
def test_packet_split_and_assemble(size):
    packet = m17.sms("x" * size)
    parts = m17.split_packet(packet)
    assert b"".join(c for c, _, _ in parts) == packet and parts[-1][2] and parts[-1][1] == len(parts[-1][0])
    asm = m17.PacketAssembler()
    results = [asm.add(m17.PacketFrame(c.ljust(25, b"\0"), last, n, 0)) for c, n, last in parts]
    assert results[:-1] == [None] * (len(parts) - 1)
    assert results[-1].crc_ok and results[-1].protocol == 5 and results[-1].text == "x" * size


def test_packet_limits_and_errors():
    with pytest.raises(ValueError):
        m17.sms("x" * 822)
    asm = m17.PacketAssembler()
    parts = m17.split_packet(m17.sms("y" * 60))  # 3 frames
    # a missing middle frame drops the packet
    assert asm.add(m17.PacketFrame(parts[0][0], False, 0, 0)) is None
    assert asm.add(m17.PacketFrame(parts[2][0].ljust(25, b"\0"), True, parts[2][1], 0)) is not None
    # a damaged byte fails the CRC
    bad = bytearray(m17.sms("z")); bad[1] ^= 1
    p = asm.add(m17.PacketFrame(bytes(bad).ljust(25, b"\0"), True, len(bad), 0))
    assert p is not None and not p.crc_ok


def test_packet_transmissions_match_m17_packet_encode():
    for case in json.loads((ROOT / "packet_vectors.json").read_text()):
        lsf = LSF(dst=case["dst"], src=case["src"], type=can(case["can"]))
        assert m17.encode_packet(lsf, m17.sms(case["text"])) == case["symbols"]


# ---- receiver


def _noisy(symbols, sigma, seed=1):
    rng = random.Random(seed)
    return [s + rng.gauss(0, sigma) for s in symbols]


def test_receiver_stream():
    lsf = LSF(dst="@ALL", src="N0CALL")
    payloads = [bytes([n] * 16) for n in range(30)]
    tx = m17.encode_stream(lsf, payloads)
    rx = m17.Receiver()
    events = rx.feed(_noisy([0.0] * 37 + tx, 0.5))  # unaligned start, noise
    lsfs = [e for e in events if isinstance(e, m17.LSFFrame)]
    frames = [e for e in events if isinstance(e, m17.StreamFrame)]
    assert len(lsfs) == 1 and lsfs[0].crc_ok and lsfs[0].lsf == lsf
    assert [f.payload for f in frames] == payloads and [f.fn for f in frames] == list(range(30))
    assert frames[-1].last and not any(f.last for f in frames[:-1])
    assert isinstance(events[-1], m17.EndOfTransmission)


def test_receiver_packet_in_chunks():
    lsf = LSF(dst="SP5WWP", src="N0CALL", type=PACKET | DATA)
    tx = m17.encode_packet(lsf, m17.sms("Hello, M17!"))
    rx = m17.Receiver()
    events = []
    for i in range(0, len(tx), 100):  # arbitrary chunk boundaries
        events += rx.feed(tx[i : i + 100])
    packets = [e for e in events if isinstance(e, m17.Packet)]
    assert len(packets) == 1 and packets[0].crc_ok and packets[0].text == "Hello, M17!"


def test_modulate_and_matched_filter():
    pytest.importorskip("numpy")
    tx = m17.encode_packet(LSF(src="N0CALL", type=PACKET | DATA), m17.sms("RRC round trip"))
    samples = phy.modulate(tx, sps=10)
    rx_samples = phy.matched_filter(samples, sps=10)
    delay = 80  # 2 x 4 symbols of filter delay, 10 samples each
    symbols = rx_samples[delay : delay + len(tx) * 10 : 10]
    assert max(abs(a - b) for a, b in zip(symbols, tx)) < 0.2
    packets = [e for e in m17.Receiver().feed(symbols) if isinstance(e, m17.Packet)]
    assert packets and packets[0].text == "RRC round trip"


# ---- command line


def test_cli_round_trip(tmp_path):
    sym = tmp_path / "msg.sym"
    run = [sys.executable, "-m", "m17"]
    subprocess.run(run + ["sms", "--src", "N0CALL", "--dst", "#M17", "--can", "2", "Hello CLI", "-o", str(sym)], check=True)
    assert len(sym.read_bytes()) == 4 * 768
    out = subprocess.run(run + ["decode", str(sym)], check=True, capture_output=True, text=True).stdout
    assert "LSF N0CALL -> #M17" in out and "CAN 2" in out and "'Hello CLI'" in out and "End of transmission" in out
    struct.unpack("<768f", sym.read_bytes())
