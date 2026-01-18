"""
M17 Puncturing Patterns

Puncturing removes some bits from the convolutional encoder output
to achieve different code rates while maintaining error correction.

Patterns:
- P1: For LSF, removes every 3rd pair -> 488 bits to 368 bits
- P2: For stream/BERT, removes 1 of every 12 -> 296/402 bits to 272/368 bits
- P3: For packet, removes 1 of every 8 -> 420 bits to 368 bits

Port from libm17/encode/convol.c
"""

from __future__ import annotations

from typing import List, Tuple

__all__ = [
    "puncture",
    "depuncture",
    "PUNCTURE_P1",
    "PUNCTURE_P2",
    "PUNCTURE_P3",
]

# P1: Puncture pattern for Link Setup Frames (LSF)
# 61 elements, removes roughly 1 in 4 bits
PUNCTURE_P1: Tuple[int, ...] = (
    1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1,
    1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1,
    1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1,
    1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1,
)

# P2: Puncture pattern for stream frames and BERT
# 12 elements, removes 1 of every 12 bits
PUNCTURE_P2: Tuple[int, ...] = (1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0)

# P3: Puncture pattern for packet frames
# 8 elements, removes 1 of every 8 bits
PUNCTURE_P3: Tuple[int, ...] = (1, 1, 1, 1, 1, 1, 1, 0)


def puncture(bits: List[int], pattern: Tuple[int, ...]) -> List[int]:
    """
    Apply puncturing pattern to remove bits.

    Args:
        bits: Input bit list.
        pattern: Puncture pattern (1 = keep, 0 = remove).

    Returns:
        Punctured bit list.

    Examples:
        >>> puncture([0,1,0,1,0,1,0,1,0,1,0,1], PUNCTURE_P2)
        [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
    """
    output = []
    pattern_len = len(pattern)
    p = 0

    for bit in bits:
        if pattern[p]:
            output.append(bit)
        p = (p + 1) % pattern_len

    return output


def depuncture(
    bits: List[int], pattern: Tuple[int, ...], fill_value: int = 0x7FFF
) -> List[int]:
    """
    Reverse puncturing by inserting erasure values.

    For soft decoding, the fill_value should be 0x7FFF (uncertain).
    For hard decoding, use 0.

    Args:
        bits: Punctured bit list.
        pattern: Puncture pattern used.
        fill_value: Value to insert for punctured positions.

    Returns:
        Depunctured bit list with erasures.

    Examples:
        >>> depuncture([0,1,0,1,0,1,0,1,0,1,0], PUNCTURE_P2, fill_value=2)
        [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 2]
    """
    output = []
    pattern_len = len(pattern)
    p = 0
    bit_idx = 0

    while bit_idx < len(bits):
        if pattern[p]:
            output.append(bits[bit_idx])
            bit_idx += 1
        else:
            output.append(fill_value)
        p = (p + 1) % pattern_len

    # Continue adding fill values until pattern completes
    # (handles case where input doesn't align with pattern)
    while p != 0:
        if not pattern[p]:
            output.append(fill_value)
        p = (p + 1) % pattern_len

    return output


def puncture_lsf(bits: List[int]) -> List[int]:
    """
    Puncture LSF encoded bits using P1 pattern.

    Args:
        bits: 488 encoded bits.

    Returns:
        368 punctured bits.
    """
    if len(bits) != 488:
        raise ValueError(f"LSF must be 488 bits, got {len(bits)}")

    return puncture(bits, PUNCTURE_P1)


def puncture_stream(bits: List[int]) -> List[int]:
    """
    Puncture stream frame encoded bits using P2 pattern.

    Args:
        bits: 296 encoded bits.

    Returns:
        272 punctured bits.
    """
    if len(bits) != 296:
        raise ValueError(f"Stream frame must be 296 bits, got {len(bits)}")

    return puncture(bits, PUNCTURE_P2)


def puncture_packet(bits: List[int]) -> List[int]:
    """
    Puncture packet frame encoded bits using P3 pattern.

    Args:
        bits: 420 encoded bits.

    Returns:
        368 punctured bits.
    """
    if len(bits) != 420:
        raise ValueError(f"Packet frame must be 420 bits, got {len(bits)}")

    return puncture(bits, PUNCTURE_P3)


def puncture_bert(bits: List[int]) -> List[int]:
    """
    Puncture BERT frame encoded bits using P2 pattern.

    Args:
        bits: 402 encoded bits.

    Returns:
        368 punctured bits.
    """
    if len(bits) != 402:
        raise ValueError(f"BERT frame must be 402 bits, got {len(bits)}")

    return puncture(bits, PUNCTURE_P2)


def depuncture_lsf(bits: List[int], fill_value: int = 0x7FFF) -> List[int]:
    """
    Depuncture LSF bits for decoding.

    Args:
        bits: 368 punctured bits.
        fill_value: Value for erasure positions.

    Returns:
        488 depunctured bits.
    """
    return depuncture(bits, PUNCTURE_P1, fill_value)


def depuncture_stream(bits: List[int], fill_value: int = 0x7FFF) -> List[int]:
    """
    Depuncture stream frame bits for decoding.

    Args:
        bits: 272 punctured bits.
        fill_value: Value for erasure positions.

    Returns:
        296 depunctured bits.
    """
    return depuncture(bits, PUNCTURE_P2, fill_value)


def depuncture_packet(bits: List[int], fill_value: int = 0x7FFF) -> List[int]:
    """
    Depuncture packet frame bits for decoding.

    Args:
        bits: 368 punctured bits.
        fill_value: Value for erasure positions.

    Returns:
        420 depunctured bits.
    """
    return depuncture(bits, PUNCTURE_P3, fill_value)
