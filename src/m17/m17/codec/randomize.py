"""M17 Randomizer

XOR the payload bits with a fixed pseudo-random sequence to
ensure DC balance and aid synchronization.

The 46-byte sequence produces 368 bits of randomization.

Port from libm17/phy/randomize.c
"""

from __future__ import annotations

from typing import Union

__all__ = [
    "randomize",
    "derandomize",
    "RAND_SEQ",
]

# 46-byte randomizing sequence
RAND_SEQ: bytes = bytes(
    [
        0xD6,
        0xB5,
        0xE2,
        0x30,
        0x82,
        0xFF,
        0x84,
        0x62,
        0xBA,
        0x4E,
        0x96,
        0x90,
        0xD8,
        0x98,
        0xDD,
        0x5D,
        0x0C,
        0xC8,
        0x52,
        0x43,
        0x91,
        0x1D,
        0xF8,
        0x6E,
        0x68,
        0x2F,
        0x35,
        0xDA,
        0x14,
        0xEA,
        0xCD,
        0x76,
        0x19,
        0x8D,
        0xD5,
        0x80,
        0xD1,
        0x33,
        0x87,
        0x13,
        0x57,
        0x18,
        0x2D,
        0x29,
        0x78,
        0xC3,
    ]
)

# Pre-compute bit sequence for faster access
_RAND_BITS: tuple[int, ...] = tuple((RAND_SEQ[i // 8] >> (7 - (i % 8))) & 1 for i in range(368))


def randomize(bits: Union[list[int], list[bool]]) -> list[int]:
    """Apply randomization to bits.

    XORs each bit with the corresponding bit in the random sequence.
    For hard bits (0/1), this flips bits where the random sequence is 1.

    Args:
    ----
        bits: 368-element sequence of bits (0/1).

    Returns:
    -------
        368-element randomized sequence.

    Examples:
    --------
        >>> inp = [0] * 368  # All zeros
        >>> out = randomize(inp)
        >>> out[0]  # First bit of RAND_SEQ[0] = 0xD6 = 0b11010110, bit 7 = 1
        1
    """
    if len(bits) != 368:
        raise ValueError(f"Input must be 368 bits, got {len(bits)}")

    out = list(bits)
    for i in range(368):
        if _RAND_BITS[i]:
            out[i] = 1 - out[i] if out[i] in (0, 1) else out[i] ^ 1

    return out


def derandomize(bits: Union[list[int], list[bool]]) -> list[int]:
    """Remove randomization from bits.

    Since XOR is its own inverse, this is identical to randomize().

    Args:
    ----
        bits: 368-element randomized sequence.

    Returns:
    -------
        368-element original sequence.
    """
    return randomize(bits)


def randomize_soft(soft_bits: list[int]) -> list[int]:
    """Apply randomization to soft bit values.

    For soft bits where values near 0 are strong 0 and near 0xFFFF are strong 1,
    randomization inverts the polarity where the random sequence is 1.

    Args:
    ----
        soft_bits: 368 soft bit values (0 = strong 0, 0xFFFF = strong 1).

    Returns:
    -------
        368 randomized soft bit values.

    Examples:
    --------
        >>> inp = [0] * 368  # All strong zeros
        >>> out = randomize_soft(inp)
        >>> out[0]  # First random bit is 1, so this becomes strong 1
        65535
    """
    if len(soft_bits) != 368:
        raise ValueError(f"Input must be 368 soft bits, got {len(soft_bits)}")

    out = list(soft_bits)
    for i in range(368):
        if _RAND_BITS[i]:
            # Invert soft bit: 0xFFFF - value
            out[i] = 0xFFFF - out[i]

    return out


def derandomize_soft(soft_bits: list[int]) -> list[int]:
    """Remove randomization from soft bit values.

    Since the operation is its own inverse, this is identical to randomize_soft().

    Args:
    ----
        soft_bits: 368 randomized soft bit values.

    Returns:
    -------
        368 derandomized soft bit values.
    """
    return randomize_soft(soft_bits)


def get_random_bit(index: int) -> int:
    """Get a single random bit at the specified index.

    Args:
    ----
        index: Bit index (0-367).

    Returns:
    -------
        Random bit value (0 or 1).
    """
    if not 0 <= index < 368:
        raise ValueError(f"Index must be 0-367, got {index}")
    return _RAND_BITS[index]
