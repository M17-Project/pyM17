"""Encryption and signatures, against gr-m17's code (tests/crypto_vectors.json, see tools/gen_crypto_vectors.c)."""

import json
import random
from pathlib import Path

import pytest

pytest.importorskip("cryptography")

import m17
from m17 import crypto
from m17.lsf import AES_256, ENCR_AES, ENCR_SCRAMBLER, LSF, SCRAMBLER_16, SIGNED, STREAM, VOICE, meta_nonce

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


def test_ecdsa_matches_micro_ecc():
    e = V["ecdsa"]
    private, public = bytes.fromhex(e["private"]), bytes.fromhex(e["public"])
    digest, signature = bytes.fromhex(e["digest"]), bytes.fromhex(e["signature"])
    assert crypto.public_key(private) == public
    # the digest of the same 5 payloads as in the generator
    d = crypto.StreamDigest()
    for f in range(5):
        d.update(bytes(f * 9 + i * 3 for i in range(16)))
    assert d.digest == digest
    assert crypto.verify(public, digest, signature)  # signed by micro-ecc
    ours = crypto.sign(private, digest)
    assert crypto.verify(public, digest, ours)
    assert not crypto.verify(public, bytes(16), ours)
    assert not crypto.verify(public, digest, bytes(64))


def _payloads(n):
    return [bytes([k] * 16) for k in range(n)]


def test_aes_signed_stream_round_trip():
    key = bytes(range(32))
    private, public = crypto.generate_key()
    lsf = LSF(dst="@ALL", src="SP5WWP", type=STREAM | VOICE | ENCR_AES | AES_256 | SIGNED,
              meta=meta_nonce(1763300000, bytes(range(10))))
    tx = m17.encode_stream(lsf, _payloads(12), key=key, signing_key=private)
    assert len(tx) == 192 * (2 + 12 + 4 + 1)

    events = m17.Receiver(key=key, public_keys=[bytes(64), public]).feed(tx)
    data = [e for e in events if isinstance(e, m17.StreamFrame) and e.fn < 0x7FFC]
    assert [f.payload for f in data] == _payloads(12) and all(f.decrypted for f in data)
    assert not any(f.last for f in data)  # in a signed stream the last signature frame is marked
    sig = [e for e in events if isinstance(e, m17.receiver.Signature)]
    assert sig == [m17.receiver.Signature(True, public)]

    # without the key the payloads stay encrypted, without public keys the signature is unchecked
    events = m17.Receiver().feed(tx)
    assert [e.payload for e in events if isinstance(e, m17.StreamFrame) and e.fn < 4] != _payloads(4)
    assert [e for e in events if isinstance(e, m17.receiver.Signature)] == [m17.receiver.Signature(None, None)]

    # a different signing key does not verify
    other, _ = crypto.generate_key()
    tx2 = m17.encode_stream(lsf, _payloads(12), key=key, signing_key=other)
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
    assert [e for e in events if isinstance(e, m17.receiver.Signature)] == [m17.receiver.Signature(True, public)]
