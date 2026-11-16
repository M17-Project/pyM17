"""Whole transmissions as symbol lists: preamble, LSF, frames and EOT marker."""

from collections.abc import Iterable

from .frames import lsf_frame, packet_frame, stream_frame
from .lsf import LSF
from .packet import split_packet
from .phy import eot, preamble


def encode_stream(lsf: LSF, payloads: Iterable[bytes]) -> list[int]:
    """A stream transmission: one frame per 16-byte payload (e.g. two Codec 2 3200 frames)."""
    payloads = list(payloads)
    out = preamble() + lsf_frame(lsf)
    for fn, payload in enumerate(payloads):
        out += stream_frame(lsf, fn, payload, last=fn == len(payloads) - 1)
    return out + eot()


def encode_packet(lsf: LSF, packet: bytes) -> list[int]:
    """A packet transmission, e.g. ``encode_packet(lsf, sms("Hello"))``."""
    out = preamble() + lsf_frame(lsf)
    for chunk, counter, last in split_packet(packet):
        out += packet_frame(chunk, counter, last)
    return out + eot()
