"""pyM17 against reference values from libm17 (tests/vectors.json, see tools/gen_vectors.c)."""

import json
from pathlib import Path

import pytest

from m17 import fec, frames, phy
from m17.callsign import callsign_from_bytes, callsign_to_bytes
from m17.crc import crc16
from m17.lsf import LSF, Position, meta_ecd, meta_nonce

V = json.loads((Path(__file__).parent / "vectors.json").read_text())


@pytest.mark.parametrize("case", V["callsigns"], ids=lambda c: c["text"])
def test_callsigns(case):
    assert callsign_to_bytes(case["text"]).hex() == case["bytes"]
    assert callsign_from_bytes(bytes.fromhex(case["bytes"])) == case["decoded"]


def test_crc():
    for case in V["crc"]:
        data = bytes.fromhex(case["hex"]) if "hex" in case else case["data"].encode()
        assert crc16(data) == case["crc"]


def test_golay_all_codewords():
    assert [fec.golay24_encode(d) for d in range(4096)] == V["golay"]


def test_tables():
    assert list(phy.INTERLEAVER) == V["interleaver"]
    assert phy.RANDOMIZER.hex() == V["randomizer"]
    for sps in (10, 5):
        assert phy.rrc_taps(sps) == pytest.approx(V[f"rrc_taps_{sps}"], abs=1e-7)


def test_preamble_and_eot():
    assert phy.preamble() == V["preamble_lsf"]
    assert phy.preamble(bert=True) == V["preamble_bert"]
    assert phy.eot() == V["eot"]


@pytest.mark.parametrize("case", V["meta_position"], ids=lambda c: f"{c['lat']},{c['lon']}")
def test_meta_position(case):
    pos = Position(
        lat=case["lat"],
        lon=case["lon"],
        altitude=case["altitude"],
        bearing=case["bearing"],
        speed=case["speed"],
        radius=case["radius"],
        validity=case["validity"],
        source=1,
        station=2,
    )
    assert pos.to_meta().hex() == case["meta"]


def test_meta_ecd_and_nonce():
    assert meta_ecd("SP5WWP", "M17-M17").hex() == V["meta_ecd"]
    assert meta_nonce(1763300000, bytes(range(1, 11))).hex() == V["meta_nonce"]


@pytest.mark.parametrize("case", V["lsf_frames"])
def test_lsf_frames(case):
    lsf = LSF.from_bytes(bytes.fromhex(case["lsf"]))
    assert lsf.to_bytes().hex() == case["lsf"]
    assert frames.lsf_frame(lsf) == case["symbols"]
    decoded = frames.decode_lsf(case["symbols"][8:])
    assert decoded.data.hex() == case["lsf"] and decoded.crc_ok and decoded.metric < 0xFFFF


@pytest.mark.parametrize("case", V["stream_frames"])
def test_stream_frames(case):
    lsf = LSF.from_bytes(bytes.fromhex(case["lsf"]))
    payload, fn = bytes.fromhex(case["payload"]), case["fn"]
    symbols = frames.stream_frame(lsf, fn, payload, last=bool(fn & 0x8000), lich_counter=case["lich_cnt"])
    assert symbols == case["symbols"]
    d = frames.decode_stream(case["symbols"][8:])
    assert (d.fn, d.last, d.payload, d.lich_counter) == (fn & 0x7FFF, bool(fn & 0x8000), payload, case["lich_cnt"])
    assert d.metric < 0xFFFF  # punctured bits leave a small residual, below one bit error
    assert d.lich == lsf.lich(case["lich_cnt"])[:5]


@pytest.mark.parametrize("case", V["packet_frames"])
def test_packet_frames(case):
    chunk = bytes.fromhex(case["chunk"])
    last, counter = bool(chunk[25] & 0x80), (chunk[25] >> 2) & 0x1F
    assert frames.packet_frame(chunk[:25], counter, last) == case["symbols"]
    d = frames.decode_packet(case["symbols"][8:])
    assert (d.data, d.last, d.counter) == (chunk[:25], last, counter) and d.metric < 0xFFFF


def test_bert_frame():
    assert frames.bert_frame(bytes.fromhex(V["bert_frame"]["data"])) == V["bert_frame"]["symbols"]


@pytest.mark.parametrize("case", V["noisy"], ids=lambda c: c["kind"])
def test_noisy_frames_match_libm17(case):
    """Same decoded bits and the same Viterbi metric as libm17, even with errors."""
    if case["kind"] == "lsf":
        d = frames.decode_lsf(case["symbols"])
        assert (d.data.hex(), d.metric) == (case["lsf"], case["metric"])
    elif case["kind"] == "stream":
        d = frames.decode_stream(case["symbols"])
        fn = d.fn | (0x8000 if d.last else 0)
        lich_cnt = 0xFF if d.lich_counter is None else d.lich_counter
        assert (d.payload.hex(), fn, d.lich.hex(), lich_cnt, d.metric) == (
            case["payload"],
            case["fn"],
            case["lich"],
            case["lich_cnt"],
            case["metric"],
        )
    else:
        d = frames.decode_packet(case["symbols"])
        assert (d.data.hex(), int(d.last), d.counter, d.metric) == (
            case["data"],
            case["eof"],
            case["counter"],
            case["metric"],
        )
