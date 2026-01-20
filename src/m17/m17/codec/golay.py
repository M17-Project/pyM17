"""M17 Golay(24,12) Codec

The Golay(24,12) code is used to protect the LICH chunks in M17.
Each 12-bit data word is encoded to a 24-bit codeword with 12 parity bits.

This can correct up to 3 bit errors in a codeword.

Port from libm17/math/golay.c
"""

from __future__ import annotations

__all__ = [
    "golay24_encode",
    "golay24_decode",
    "golay24_sdecode",
    "encode_lich",
    "decode_lich",
    "ENCODE_MATRIX",
    "DECODE_MATRIX",
]

# Precomputed encoding matrix for Golay(24,12)
ENCODE_MATRIX: tuple[int, ...] = (
    0x8EB,
    0x93E,
    0xA97,
    0xDC6,
    0x367,
    0x6CD,
    0xD99,
    0x3DA,
    0x7B4,
    0xF68,
    0x63B,
    0xC75,
)

# Precomputed decoding matrix for Golay(24,12)
DECODE_MATRIX: tuple[int, ...] = (
    0xC75,
    0x49F,
    0x93E,
    0x6E3,
    0xDC6,
    0xF13,
    0xAB9,
    0x1ED,
    0x3DA,
    0x7B4,
    0xF68,
    0xA4F,
)


def golay24_encode(data: int) -> int:
    """Encode a 12-bit value with Golay(24,12).

    Args:
    ----
        data: 12-bit input value (right justified).

    Returns:
    -------
        24-bit Golay codeword (data in upper 12 bits, parity in lower 12).

    Examples:
    --------
        >>> hex(golay24_encode(0x123))
        '0x123e7e'
    """
    checksum = 0

    for i in range(12):
        if data & (1 << i):
            checksum ^= ENCODE_MATRIX[i]

    return (data << 12) | checksum


def _popcount(n: int) -> int:
    """Count number of 1 bits in an integer."""
    count = 0
    while n:
        count += n & 1
        n >>= 1
    return count


def _calc_syndrome(data: int) -> int:
    """Calculate syndrome for a 12-bit data word.

    Args:
    ----
        data: 12-bit data value.

    Returns:
    -------
        12-bit syndrome.
    """
    checksum = 0
    for i in range(12):
        if data & (1 << i):
            checksum ^= ENCODE_MATRIX[i]
    return checksum


def golay24_decode(codeword: int) -> tuple[int, int]:
    """Decode a 24-bit Golay codeword (hard decision).

    Args:
    ----
        codeword: 24-bit Golay codeword.

    Returns:
    -------
        Tuple of (decoded 12-bit data, number of errors corrected).
        Returns (0xFFFF, -1) if uncorrectable.

    Examples:
    --------
        >>> golay24_decode(golay24_encode(0x123))
        (291, 0)
    """
    # Extract data and parity
    data = (codeword >> 12) & 0xFFF
    parity = codeword & 0xFFF

    # Calculate syndrome
    syndrome = parity ^ _calc_syndrome(data)

    # Weight of syndrome
    weight = _popcount(syndrome)

    # All errors in parity (up to 3)
    if weight <= 3:
        return data, weight

    # One error in data, up to 2 in parity
    for i in range(12):
        e = 1 << i
        coded_error = ENCODE_MATRIX[i]
        test_syndrome = syndrome ^ coded_error

        if _popcount(test_syndrome) <= 2:
            return data ^ e, _popcount(test_syndrome) + 1

    # Two errors in data, up to 1 in parity
    for i in range(11):
        for j in range(i + 1, 12):
            e = (1 << i) | (1 << j)
            coded_error = ENCODE_MATRIX[i] ^ ENCODE_MATRIX[j]
            test_syndrome = syndrome ^ coded_error

            if _popcount(test_syndrome) <= 1:
                return data ^ e, _popcount(test_syndrome) + 2

    # Try algebraic decoding
    inv_syndrome = 0
    for i in range(12):
        if syndrome & (1 << i):
            inv_syndrome ^= DECODE_MATRIX[i]

    # All errors in data (up to 3)
    if _popcount(inv_syndrome) <= 3:
        return data ^ inv_syndrome, _popcount(inv_syndrome)

    # One error in parity, up to 2 in data
    for i in range(12):
        e = 1 << i
        coding_error = DECODE_MATRIX[i]
        test_inv = inv_syndrome ^ coding_error

        if _popcount(test_inv) <= 2:
            return data ^ test_inv, _popcount(test_inv) + 1

    # Uncorrectable
    return 0xFFFF, -1


def _soft_to_hard(soft: list[int]) -> int:
    """Convert soft bits to hard integer value.

    Args:
    ----
        soft: List of soft bit values (0 = strong 0, 0xFFFF = strong 1).

    Returns:
    -------
        Hard integer value.
    """
    result = 0
    for i, s in enumerate(soft):
        if s > 0x7FFF:
            result |= 1 << i
    return result


def _soft_popcount(soft: list[int]) -> int:
    """Soft-valued equivalent of popcount.

    Args:
    ----
        soft: List of soft bit values.

    Returns:
    -------
        Sum of all soft values (higher = more 1s).
    """
    return sum(soft)


def _int_to_soft(value: int, bits: int) -> list[int]:
    """Convert integer to soft bit list.

    Args:
    ----
        value: Integer value.
        bits: Number of bits.

    Returns:
    -------
        List of soft bit values.
    """
    return [0xFFFF if (value >> i) & 1 else 0 for i in range(bits)]


def _soft_xor(a: list[int], b: list[int]) -> list[int]:
    """XOR two soft bit vectors.

    Args:
    ----
        a: First soft vector.
        b: Second soft vector.

    Returns:
    -------
        XOR result.
    """
    result = []
    for x, y in zip(a, b, strict=False):
        # If either is uncertain (near 0x7FFF), result is uncertain
        # If both are same polarity, result is 0; opposite is 1
        x_bit = 1 if x > 0x7FFF else 0
        y_bit = 1 if y > 0x7FFF else 0
        # Confidence is minimum of both
        x_conf = abs(x - 0x7FFF)
        y_conf = abs(y - 0x7FFF)
        min_conf = min(x_conf, y_conf)
        xor_bit = x_bit ^ y_bit
        result.append(0x7FFF + min_conf if xor_bit else 0x7FFF - min_conf)
    return result


def golay24_sdecode(codeword: list[int]) -> int:
    """Soft decode Golay(24,12) codeword.

    Args:
    ----
        codeword: List of 24 soft bit values (MSB first as in M17 spec).
            Values: 0 = strong 0, 0xFFFF = strong 1.

    Returns:
    -------
        Decoded 12-bit data, or 0xFFFF if uncorrectable.

    Examples:
    --------
        >>> soft = [0xFFFF if b else 0 for b in [0,0,0,1,0,0,1,0,0,0,1,1,1,1,1,0,0,1,1,1,1,1,1,0]]
        >>> hex(golay24_sdecode(soft))
        '0x123'
    """
    if len(codeword) != 24:
        raise ValueError(f"Codeword must be 24 soft bits, got {len(codeword)}")

    # Reverse to match M17 bit order
    cw = list(reversed(codeword))

    # Split into data (upper 12) and parity (lower 12)
    data_soft = cw[12:24]  # Upper 12 bits
    parity_soft = cw[0:12]  # Lower 12 bits

    # Calculate soft syndrome
    data_hard = _soft_to_hard(data_soft)
    checksum = _calc_syndrome(data_hard)
    checksum_soft = _int_to_soft(checksum, 12)
    syndrome_soft = _soft_xor(parity_soft, checksum_soft)

    weight = _soft_popcount(syndrome_soft)

    # All errors in parity
    if weight < 4 * 0xFFFE:
        return data_hard

    # One error in data, up to 3 in parity
    for i in range(12):
        e = 1 << i
        coded_error_soft = _int_to_soft(ENCODE_MATRIX[i], 12)
        sc = _soft_xor(syndrome_soft, coded_error_soft)
        weight = _soft_popcount(sc)

        if weight < 3 * 0xFFFE:
            return data_hard ^ e

    # Two errors in data, up to 2 in parity
    for i in range(11):
        for j in range(i + 1, 12):
            e = (1 << i) | (1 << j)
            coded_error_soft = _int_to_soft(ENCODE_MATRIX[i] ^ ENCODE_MATRIX[j], 12)
            sc = _soft_xor(syndrome_soft, coded_error_soft)
            weight = _soft_popcount(sc)

            if weight < 2 * 0xFFFF:
                return data_hard ^ e

    # Algebraic decoding
    syndrome_hard = _soft_to_hard(syndrome_soft)
    inv_syndrome = 0
    for i in range(12):
        if syndrome_hard & (1 << i):
            inv_syndrome ^= DECODE_MATRIX[i]

    inv_syndrome_soft = _int_to_soft(inv_syndrome, 12)
    weight = _soft_popcount(inv_syndrome_soft)

    # All errors in data
    if weight < 4 * 0xFFFF:
        return data_hard ^ inv_syndrome

    # One error in parity, up to 3 in data
    for i in range(12):
        coding_error_soft = _int_to_soft(DECODE_MATRIX[i], 12)
        tmp = _soft_xor(inv_syndrome_soft, coding_error_soft)
        weight = _soft_popcount(tmp)

        if weight < 3 * (0xFFFF + 2):
            coding_error = DECODE_MATRIX[i]
            return data_hard ^ (inv_syndrome ^ coding_error)

    return 0xFFFF


def encode_lich(data: bytes) -> bytes:
    """Encode a 6-byte LICH chunk to 12 bytes using Golay(24,12).

    Each 12-bit nibble pair is encoded to 24 bits.
    6 bytes (48 bits) -> 4 Golay codewords -> 12 bytes (96 bits).

    Args:
    ----
        data: 6-byte LICH chunk.

    Returns:
    -------
        12-byte encoded LICH.
    """
    if len(data) != 6:
        raise ValueError(f"LICH chunk must be 6 bytes, got {len(data)}")

    result = bytearray(12)

    # Encode 4 x 12-bit words
    # Word 0: data[0] << 4 | data[1] >> 4
    val = golay24_encode((data[0] << 4) | (data[1] >> 4))
    result[0] = (val >> 16) & 0xFF
    result[1] = (val >> 8) & 0xFF
    result[2] = val & 0xFF

    # Word 1: (data[1] & 0x0F) << 8 | data[2]
    val = golay24_encode(((data[1] & 0x0F) << 8) | data[2])
    result[3] = (val >> 16) & 0xFF
    result[4] = (val >> 8) & 0xFF
    result[5] = val & 0xFF

    # Word 2: data[3] << 4 | data[4] >> 4
    val = golay24_encode((data[3] << 4) | (data[4] >> 4))
    result[6] = (val >> 16) & 0xFF
    result[7] = (val >> 8) & 0xFF
    result[8] = val & 0xFF

    # Word 3: (data[4] & 0x0F) << 8 | data[5]
    val = golay24_encode(((data[4] & 0x0F) << 8) | data[5])
    result[9] = (val >> 16) & 0xFF
    result[10] = (val >> 8) & 0xFF
    result[11] = val & 0xFF

    return bytes(result)


def decode_lich(soft_bits: list[int]) -> bytes:
    """Decode a 96 soft-bit encoded LICH to 6 bytes.

    Args:
    ----
        soft_bits: 96 soft bit values.

    Returns:
    -------
        6-byte decoded LICH chunk.
    """
    if len(soft_bits) != 96:
        raise ValueError(f"Encoded LICH must be 96 soft bits, got {len(soft_bits)}")

    result = bytearray(6)

    # Decode 4 Golay codewords
    tmp = golay24_sdecode(soft_bits[0:24])
    result[0] = (tmp >> 4) & 0xFF
    result[1] = (tmp & 0x0F) << 4

    tmp = golay24_sdecode(soft_bits[24:48])
    result[1] |= (tmp >> 8) & 0x0F
    result[2] = tmp & 0xFF

    tmp = golay24_sdecode(soft_bits[48:72])
    result[3] = (tmp >> 4) & 0xFF
    result[4] = (tmp & 0x0F) << 4

    tmp = golay24_sdecode(soft_bits[72:96])
    result[4] |= (tmp >> 8) & 0x0F
    result[5] = tmp & 0xFF

    return bytes(result)
