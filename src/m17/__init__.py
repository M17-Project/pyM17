"""pyM17: the M17 digital radio protocol in Python.

Bit-exact with libm17, the reference C implementation. See the README for an
overview, the module docstrings for details.
"""

from .callsign import BROADCAST, decode_callsign, encode_callsign
from .crc import crc16
from .frames import (
    LSFFrame,
    PacketFrame,
    StreamFrame,
    bert_frame,
    decode_lsf,
    decode_packet,
    decode_stream,
    lsf_frame,
    packet_frame,
    stream_frame,
)
from .lsf import LSF, Position, meta_ecd, meta_nonce
from .packet import Packet, PacketAssembler, build_packet, sms, split_packet
from .receiver import EndOfTransmission, Receiver, Signature
from .transmission import encode_packet, encode_stream

__version__ = "0.2.0"

__all__ = [
    "BROADCAST", "LSF", "LSFFrame", "Packet", "PacketAssembler", "PacketFrame", "Position", "Receiver", "Signature",
    "EndOfTransmission", "StreamFrame", "bert_frame", "build_packet", "crc16", "decode_callsign",
    "decode_lsf", "decode_packet", "decode_stream", "encode_callsign", "encode_packet", "encode_stream",
    "lsf_frame", "meta_ecd", "meta_nonce", "packet_frame", "sms", "split_packet", "stream_frame",
]
