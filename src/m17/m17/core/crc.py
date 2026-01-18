"""
M17 CRC-16 Implementation

CRC-16 with polynomial 0x5935, initial value 0xFFFF.
Port from libm17/payload/crc.c

Test vectors:
- b"" -> 0xFFFF
- b"A" -> 0x206E
- b"123456789" -> 0x772B
"""

from __future__ import annotations

__all__ = ["M17_CRC_POLY", "crc_m17", "crc_m17_bytes"]

# M17 CRC-16 polynomial
M17_CRC_POLY: int = 0x5935


def crc_m17(data: bytes | bytearray) -> int:
    """
    Calculate M17 CRC-16.

    Uses polynomial 0x5935 with initial value 0xFFFF.

    Args:
        data: Input byte array to calculate CRC over.

    Returns:
        16-bit CRC value.

    Examples:
        >>> crc_m17(b"")
        65535
        >>> hex(crc_m17(b""))
        '0xffff'
        >>> hex(crc_m17(b"A"))
        '0x206e'
        >>> hex(crc_m17(b"123456789"))
        '0x772b'
    """
    crc: int = 0xFFFF  # Initial value

    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc <<= 1
            if crc & 0x10000:
                crc = (crc ^ M17_CRC_POLY) & 0xFFFF

    return crc & 0xFFFF


def crc_m17_bytes(data: bytes | bytearray) -> bytes:
    """
    Calculate M17 CRC-16 and return as big-endian bytes.

    Args:
        data: Input byte array to calculate CRC over.

    Returns:
        2-byte CRC value in big-endian format.

    Examples:
        >>> crc_m17_bytes(b"123456789").hex()
        '772b'
    """
    return crc_m17(data).to_bytes(2, "big")


def verify_crc(data: bytes | bytearray) -> bool:
    """
    Verify that data with appended CRC has valid checksum.

    The data should include the 2-byte CRC at the end.
    Valid data will produce CRC of 0x0000.

    Args:
        data: Data with 2-byte CRC appended.

    Returns:
        True if CRC is valid, False otherwise.

    Examples:
        >>> data = b"123456789" + bytes([0x77, 0x2B])
        >>> verify_crc(data)
        True
    """
    return crc_m17(data) == 0x0000
