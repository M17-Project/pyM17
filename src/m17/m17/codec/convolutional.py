"""
M17 Convolutional Encoder

K=5 constraint length, rate 1/2 convolutional encoder.
Generator polynomials: G1=0x19 (25), G2=0x17 (23)

Port from libm17/encode/convol.c
"""

from __future__ import annotations

from typing import List, Optional

__all__ = [
    "conv_encode",
    "conv_encode_lsf",
    "conv_encode_stream",
    "conv_encode_packet",
    "conv_encode_bert",
    "POLY_G1",
    "POLY_G2",
]

# Generator polynomials for K=5 rate 1/2 convolutional code
# G1 = 1 + D^3 + D^4 = 0x19 (bits 0, 3, 4)
# G2 = 1 + D + D^2 + D^4 = 0x17 (bits 0, 1, 2, 4)
POLY_G1: int = 0x19  # x^4 + x^3 + 1
POLY_G2: int = 0x17  # x^4 + x^2 + x + 1


def _unpack_bits(data: bytes, num_bits: Optional[int] = None) -> List[int]:
    """
    Unpack bytes to a list of bits (MSB first).

    Args:
        data: Input bytes.
        num_bits: Number of bits to unpack (default: all).

    Returns:
        List of bit values (0 or 1).
    """
    if num_bits is None:
        num_bits = len(data) * 8

    bits = []
    for i in range(num_bits):
        byte_idx = i // 8
        bit_idx = 7 - (i % 8)
        if byte_idx < len(data):
            bits.append((data[byte_idx] >> bit_idx) & 1)
        else:
            bits.append(0)

    return bits


def conv_encode(data: List[int], flush: bool = True) -> List[int]:
    """
    Convolutional encode a bit stream.

    Uses K=5 constraint length, rate 1/2 encoder.
    Output is 2 bits per input bit.

    Args:
        data: List of input bits (0 or 1).
        flush: If True, append 4 zero bits to flush encoder state.

    Returns:
        List of encoded bits (twice the length of input + 8 if flushed).
    """
    # Prepend 4 zeros for initial state
    ud = [0, 0, 0, 0] + data

    # Append 4 zeros to flush if requested
    if flush:
        ud = ud + [0, 0, 0, 0]

    output = []

    # Encode using shift register
    for i in range(len(ud) - 4):
        # G1 = ud[i+4] + ud[i+1] + ud[i+0]
        g1 = (ud[i + 4] + ud[i + 1] + ud[i + 0]) & 1

        # G2 = ud[i+4] + ud[i+3] + ud[i+2] + ud[i+0]
        g2 = (ud[i + 4] + ud[i + 3] + ud[i + 2] + ud[i + 0]) & 1

        output.append(g1)
        output.append(g2)

    return output


def conv_encode_lsf(lsf_data: bytes) -> List[int]:
    """
    Convolutional encode an LSF (240 bits -> 488 bits, pre-puncture).

    The LSF is 30 bytes (240 bits) with CRC.
    After encoding with K=5 rate 1/2 + flush: (240+4)*2 = 488 bits.
    After P1 puncturing: 368 bits.

    Args:
        lsf_data: 30-byte LSF with CRC.

    Returns:
        List of 488 encoded bits (before puncturing).
    """
    if len(lsf_data) != 30:
        raise ValueError(f"LSF must be 30 bytes, got {len(lsf_data)}")

    bits = _unpack_bits(lsf_data, 240)
    return conv_encode(bits, flush=True)


def conv_encode_stream(frame_number: int, payload: bytes) -> List[int]:
    """
    Convolutional encode a stream frame (144 bits -> 296 bits, pre-puncture).

    Stream frame: 16-bit frame number + 128-bit payload = 144 bits.
    After encoding with K=5 rate 1/2 + flush: (144+4)*2 = 296 bits.
    After P2 puncturing: 272 bits.

    Args:
        frame_number: 16-bit frame number.
        payload: 16-byte payload.

    Returns:
        List of 296 encoded bits (before puncturing).
    """
    if len(payload) != 16:
        raise ValueError(f"Payload must be 16 bytes, got {len(payload)}")

    # Unpack frame number (16 bits, MSB first)
    fn_bits = [(frame_number >> (15 - i)) & 1 for i in range(16)]

    # Unpack payload (128 bits)
    payload_bits = _unpack_bits(payload, 128)

    # Combine: frame_number + payload
    bits = fn_bits + payload_bits

    return conv_encode(bits, flush=True)


def conv_encode_packet(packet_chunk: bytes) -> List[int]:
    """
    Convolutional encode a packet frame (206 bits -> 420 bits, pre-puncture).

    Packet chunk: 25 bytes data + 1 byte control = 26 bytes.
    Only 206 bits are significant (200 data + 1 EOP + 5 counter).
    After encoding with K=5 rate 1/2 + flush: (206+4)*2 = 420 bits.
    After P3 puncturing: 368 bits.

    Args:
        packet_chunk: 26-byte packet chunk.

    Returns:
        List of 420 encoded bits (before puncturing).
    """
    if len(packet_chunk) != 26:
        raise ValueError(f"Packet chunk must be 26 bytes, got {len(packet_chunk)}")

    # Unpack 206 bits
    bits = []
    for i in range(206):
        byte_idx = i // 8
        bit_idx = 7 - (i % 8)
        bits.append((packet_chunk[byte_idx] >> bit_idx) & 1)

    return conv_encode(bits, flush=True)


def conv_encode_bert(bert_data: bytes) -> List[int]:
    """
    Convolutional encode a BERT frame (197 bits -> 402 bits, pre-puncture).

    BERT: 25 bytes = 200 bits, but only 197 are used.
    After encoding with K=5 rate 1/2 + flush: (197+4)*2 = 402 bits.
    After P2 puncturing: 368 bits.

    Args:
        bert_data: 25-byte BERT data.

    Returns:
        List of 402 encoded bits (before puncturing).
    """
    if len(bert_data) != 25:
        raise ValueError(f"BERT data must be 25 bytes, got {len(bert_data)}")

    # Unpack 197 bits
    bits = []
    for i in range(197):
        byte_idx = i // 8
        bit_idx = 7 - (i % 8)
        bits.append((bert_data[byte_idx] >> bit_idx) & 1)

    return conv_encode(bits, flush=True)


def conv_encode_bytes(data: bytes) -> List[int]:
    """
    Convolutional encode arbitrary bytes.

    Args:
        data: Input bytes.

    Returns:
        List of encoded bits.
    """
    bits = _unpack_bits(data)
    return conv_encode(bits, flush=True)
