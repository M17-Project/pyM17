"""Encryption and signatures, against gr-m17's code (tests/crypto_vectors.json, see tools/gen_crypto_vectors.c)."""

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("cryptography")

import m17
from m17 import crypto
from m17.lsf import (
    AES_256,
    ENCR_AES,
    ENCR_SCRAMBLER,
    LSF,
    META_ECD,
    SCRAMBLER_16,
    SIGNED,
    STREAM,
    VOICE,
    meta_ecd,
    meta_nonce,
)

V = json.loads((Path(__file__).parent / "crypto_vectors.json").read_text())


@pytest.mark.parametrize("case", V["aes"], ids=lambda c: f"aes{len(c['key']) * 4}-fn{c['fn']}")
def test_aes_matches_tinier_aes(case):
    key, nonce = bytes.fromhex(case["key"]), bytes.fromhex(case["nonce"])
    plain, cipher = bytes.fromhex(case["plain"]), bytes.fromhex(case["cipher"])
    assert crypto.aes_crypt(key, nonce, case["fn"], plain) == cipher
    assert crypto.aes_crypt(key, nonce, case["fn"], cipher) == plain


@pytest.mark.parametrize("case", V["scrambler"], ids=lambda c: f"{len(c['seed']) * 4}-bit")
def test_scrambler_matches_gr_m17(case):
    s = crypto.Scrambler(bytes.fromhex(case["seed"]))
    expected = [bytes.fromhex(k) for k in case["keystream"]]
    assert [s.keystream(f) for f in range(4)] == expected
    assert s.keystream(2) == expected[2]  # out of order, e.g. after a lost frame
    assert s.keystream(1) == expected[1]


def test_stream_hash_and_ecdsa_match_gr_m17():
    e = V["ecdsa"]
    private, public = bytes.fromhex(e["private"]), bytes.fromhex(e["public"])
    digest, signature = bytes.fromhex(e["hash"]), bytes.fromhex(e["signature"])
    assert crypto.public_key(private) == public
    # the hash of the same 5 frames and Authentication Frame as in the generator (gr-m17's m17sig.c)
    auth = crypto.auth_payload(e["signer"], e["destination"], e["timestamp"])
    assert auth.hex() == e["auth"]
    assert crypto.parse_auth(auth) == (e["signer"], e["destination"], e["timestamp"])
    h = crypto.StreamHash()
    for f in range(5):
        h.update(f, bytes(f * 9 + i * 3 for i in range(16)))
    h.update(crypto.AUTH_FN, auth)
    assert h.digest == digest
    assert crypto.verify(public, digest, signature)  # signed by micro-ecc
    ours = crypto.sign(private, digest)
    assert crypto.verify(public, digest, ours)
    assert not crypto.verify(public, bytes(32), ours)
    assert not crypto.verify(public, digest, bytes(64))


def test_specification_2_1_test_vector():
    # M17 Specification 2.1.0, Digital Signatures, Test Vector
    h = crypto.StreamHash()
    for i in range(3):
        h.update(i, bytes(16 * i + j for j in range(16)))
    auth = crypto.auth_payload("N0CALL", "W1AW", 1794960000)  # 2026-11-18T00:00:00Z
    assert auth.hex() == "00004b13d1060000001680b70cf10980"
    h.update(0x7FFB, auth)
    assert h.digest.hex() == "2dd1bc7b5c017f100f9379f42eaa205ce90b8c7ea263f2f80e37ba6e6d6b588d"
    private = bytes.fromhex("3f9bc000fab83aed4551ec40a5f6a7c178b255ba654c0684d242bc8f59f8da18")
    public = bytes.fromhex(
        "b91931f4dc5efc54c23c0b8c87704c45585bd791046fef05bfbfd5a0ce9b53b3"
        "c55637387871bb5491a814c2344ec6f0696bf3e16fe8017fc08e3a6320eea070"
    )
    signature = bytes.fromhex(
        "e689788a5c2fbdd0fa2137429517b7c9dd5e3c2bffb9667d4edb9a8472f3cf31"
        "c45421ded7f7025608bfd928b06befd4a44526609b3dc54fc2b36944f6121d54"
    )
    assert crypto.public_key(private) == public
    assert crypto.verify(public, h.digest, signature)


def test_16_byte_digest_rejected():
    private, public = crypto.generate_key()
    with pytest.raises(ValueError):
        crypto.sign(private, bytes(16))
    with pytest.raises(ValueError):
        crypto.verify(public, bytes(16), bytes(64))


def _payloads(n):
    return [bytes([k] * 16) for k in range(n)]


def test_aes_signed_stream_round_trip():
    key = bytes(range(32))
    private, public = crypto.generate_key()
    lsf = LSF(
        dst="@ALL",
        src="SP5WWP",
        type=STREAM | VOICE | ENCR_AES | AES_256 | SIGNED,
        meta=meta_nonce(1763300000, bytes(range(10))),
    )
    tx = m17.encode_stream(lsf, _payloads(12), key=key, signing_key=private, timestamp=1794960000)
    assert len(tx) == 192 * (2 + 12 + 1 + 4 + 1)  # preamble, LSF, frames, Authentication Frame, signature, EOT

    events = m17.Receiver(key=key, public_keys=[bytes(64), public]).feed(tx)
    data = [e for e in events if isinstance(e, m17.StreamFrame) and e.fn < 0x7FFB]
    assert [f.payload for f in data] == _payloads(12) and all(f.decrypted for f in data)
    assert not any(f.last for f in data)  # in a signed stream the last signature frame is marked
    auth = [e for e in events if isinstance(e, m17.StreamFrame) and e.fn == 0x7FFB]
    assert len(auth) == 1 and not auth[0].decrypted  # sent in the clear
    signed_at = datetime(2026, 11, 18, tzinfo=timezone.utc)
    sig = [e for e in events if isinstance(e, m17.receiver.Signature)]
    assert sig == [m17.receiver.Signature(True, public, "SP5WWP", "@ALL", signed_at, True)]
    assert sig[0].fresh(now=signed_at + timedelta(seconds=299))
    assert not sig[0].fresh(now=signed_at + timedelta(seconds=301))

    # without the key the payloads stay encrypted, without public keys the signature is unchecked
    events = m17.Receiver().feed(tx)
    assert [e.payload for e in events if isinstance(e, m17.StreamFrame) and e.fn < 4] != _payloads(4)
    assert [e for e in events if isinstance(e, m17.receiver.Signature)] == [
        m17.receiver.Signature(None, None, "SP5WWP", "@ALL", signed_at, True)
    ]

    # a different signing key does not verify
    other, _ = crypto.generate_key()
    tx2 = m17.encode_stream(lsf, _payloads(12), key=key, signing_key=other, timestamp=1794960000)
    events = m17.Receiver(key=key, public_keys=[public]).feed(tx2)
    assert [e for e in events if isinstance(e, m17.receiver.Signature)][0].valid is False


def test_scrambled_stream_and_late_join():
    seed = bytes([0x12, 0x34])
    lsf = LSF(dst="@ALL", src="N0CALL", type=STREAM | VOICE | ENCR_SCRAMBLER | SCRAMBLER_16)
    tx = m17.encode_stream(lsf, _payloads(14), key=seed)
    # join after the LSF: the LSF is rebuilt from the LICH, then frames decrypt
    rx = m17.Receiver(key=seed)
    events = rx.feed(tx[192 * 2 :])
    frames = [e for e in events if isinstance(e, m17.StreamFrame)]
    assert rx.lsf == lsf
    # frames 0 to 5 carry the six LICH chunks, decryption starts with frame 5
    assert [f.payload for f in frames if f.decrypted] == _payloads(14)[5:]


def test_noisy_signed_stream():
    private, public = crypto.generate_key()
    lsf = LSF(dst="@ALL", src="N0CALL", type=STREAM | VOICE | SIGNED)
    tx = m17.encode_stream(lsf, _payloads(20), signing_key=private)
    rng = random.Random(3)
    events = m17.Receiver(public_keys=[public]).feed([s + rng.gauss(0, 0.4) for s in tx])
    sig = [e for e in events if isinstance(e, m17.receiver.Signature)]
    assert len(sig) == 1 and sig[0].valid is True and sig[0].public_key == public and sig[0].signer == "N0CALL"


def test_signed_stream_lost_frame_and_late_join():
    private, public = crypto.generate_key()
    lsf = LSF(dst="@ALL", src="N0CALL", type=STREAM | VOICE | SIGNED)
    tx = m17.encode_stream(lsf, _payloads(20), signing_key=private)
    # one frame lost: the hash cannot be rebuilt, the signature is not checked (not reported invalid)
    lost = tx[: 192 * 7] + tx[192 * 8 :]
    sig = [e for e in m17.Receiver(public_keys=[public]).feed(lost) if isinstance(e, m17.receiver.Signature)]
    assert len(sig) == 1 and sig[0].valid is None and sig[0].signer == "N0CALL"
    # joined late, after FN 0: also not checked
    sig = [e for e in m17.Receiver(public_keys=[public]).feed(tx[192 * 5 :]) if isinstance(e, m17.receiver.Signature)]
    assert len(sig) == 1 and sig[0].valid is None


def test_signer_not_the_originator():
    private, public = crypto.generate_key()
    # a repeater-style stream: Extended Callsign Data names SP5XYZ as the originator, N0CALL signs it
    lsf = LSF(dst="@ALL", src="N0CALL", type=STREAM | VOICE | META_ECD | SIGNED, meta=meta_ecd("SP5XYZ"))
    sig = [
        e
        for e in m17.Receiver(public_keys=[public]).feed(m17.encode_stream(lsf, _payloads(8), signing_key=private))
        if isinstance(e, m17.receiver.Signature)
    ]
    assert sig[0].valid is True and sig[0].signer == "N0CALL" and sig[0].signer_is_originator is False
    lsf = LSF(dst="@ALL", src="N0CALL", type=STREAM | VOICE | META_ECD | SIGNED, meta=meta_ecd("N0CALL"))
    sig = [
        e
        for e in m17.Receiver(public_keys=[public]).feed(m17.encode_stream(lsf, _payloads(8), signing_key=private))
        if isinstance(e, m17.receiver.Signature)
    ]
    assert sig[0].valid is True and sig[0].signer_is_originator is True
