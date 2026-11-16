"""Whole transmissions as symbol lists: preamble, LSF, frames and EOT marker."""

from collections.abc import Iterable

from .frames import lsf_frame, packet_frame, stream_frame
from .lsf import ENCR_AES, ENCR_SCRAMBLER, LSF, SIGNED
from .packet import split_packet
from .phy import eot, preamble

SIGNATURE_FN = 0x7FFC  # the 4 signature frames are numbered 0x7FFC to 0x7FFF


def encode_stream(
    lsf: LSF, payloads: Iterable[bytes], key: bytes | None = None, signing_key: bytes | None = None
) -> list[int]:
    """A stream transmission: one frame per 16-byte payload (e.g. two Codec 2 3200 frames).

    Encryption and signing follow the LSF's TYPE field. With AES, META holds the
    nonce (see :func:`m17.lsf.meta_nonce`) and ``key`` is the AES key. With the
    scrambler, ``key`` is the 1 to 3-byte seed. A signed stream needs the
    32-byte ``signing_key`` and ends with 4 signature frames.
    """
    from . import crypto  # only needed for encrypted or signed streams

    encr = lsf.type & (3 << 3)
    signed = bool(lsf.type & SIGNED)
    if encr and key is None:
        raise ValueError("encrypted stream: key required")
    if signed and signing_key is None:
        raise ValueError("signed stream: signing_key required")
    scrambler = crypto.Scrambler(key) if encr == ENCR_SCRAMBLER else None
    digest = crypto.StreamDigest()

    payloads = list(payloads)
    out = preamble() + lsf_frame(lsf)
    for fn, payload in enumerate(payloads):
        if encr == ENCR_AES:
            payload = crypto.aes_crypt(key, lsf.meta, fn, payload)
        elif scrambler:
            payload = scrambler.crypt(fn, payload)
        digest.update(payload)
        out += stream_frame(lsf, fn, payload, last=not signed and fn == len(payloads) - 1, lich_counter=fn % 6)
    if signed:
        sig = crypto.sign(signing_key, digest.digest)
        for k in range(4):
            out += stream_frame(lsf, SIGNATURE_FN + k, sig[16 * k : 16 * k + 16], last=k == 3,
                                lich_counter=(len(payloads) + k) % 6)
    return out + eot()


def encode_packet(lsf: LSF, packet: bytes) -> list[int]:
    """A packet transmission, e.g. ``encode_packet(lsf, sms("Hello"))``.

    The LSF TYPE should be :data:`m17.lsf.PACKET` (with DATA and the CAN).
    """
    out = preamble() + lsf_frame(lsf)
    for chunk, counter, last in split_packet(packet):
        out += packet_frame(chunk, counter, last)
    return out + eot()
