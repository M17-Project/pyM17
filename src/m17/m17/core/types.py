"""
M17 TYPE Field Definitions

The TYPE field is a 16-bit value in the Link Setup Frame that describes
the stream characteristics.

Per M17 spec v2.0.3:
- Bit 0: Packet/Stream indicator (0=packet, 1=stream)
- Bits 1-2: Data type (00=reserved, 01=data, 10=voice, 11=voice+data)
- Bits 3-4: Encryption type
- Bits 5-6: Encryption subtype
- Bits 7-10: Channel Access Number (CAN)
- Bits 11-15: Reserved
"""

from __future__ import annotations

from enum import IntEnum, IntFlag
from typing import NamedTuple

__all__ = [
    "M17Type",
    "M17DataType",
    "M17EncryptionType",
    "M17EncryptionSubtype",
    "M17MetaType",
    "ChannelAccessNumber",
    "TypeField",
    "parse_type_field",
    "build_type_field",
]


class M17Type(IntFlag):
    """M17 stream/packet type indicator (bit 0)."""

    PACKET = 0  # Packet mode
    STREAM = 1  # Stream mode


class M17DataType(IntEnum):
    """M17 data type field (bits 1-2)."""

    RESERVED = 0b00
    DATA = 0b01
    VOICE = 0b10
    VOICE_DATA = 0b11


class M17EncryptionType(IntEnum):
    """M17 encryption type field (bits 3-4)."""

    NONE = 0b00
    SCRAMBLER = 0b01
    AES = 0b10
    RESERVED = 0b11


class M17EncryptionSubtype(IntEnum):
    """M17 encryption subtype field (bits 5-6)."""

    TEXT = 0b00  # When encryption is NONE: META contains text
    GNSS = 0b01  # When encryption is NONE: META contains GNSS position
    EXT_CALL = 0b10  # When encryption is NONE: META contains extended callsign data
    RESERVED = 0b11


class M17MetaType(IntEnum):
    """META field interpretation based on encryption subtype."""

    TEXT = 0b00  # UTF-8 text data
    GNSS_POSITION = 0b01  # GNSS position data
    EXTENDED_CALLSIGN = 0b10  # Extended Callsign Data (ECD)
    RESERVED = 0b11


class ChannelAccessNumber(IntEnum):
    """Channel Access Number (CAN) values (bits 7-10)."""

    CAN_0 = 0
    CAN_1 = 1
    CAN_2 = 2
    CAN_3 = 3
    CAN_4 = 4
    CAN_5 = 5
    CAN_6 = 6
    CAN_7 = 7
    CAN_8 = 8
    CAN_9 = 9
    CAN_10 = 10
    CAN_11 = 11
    CAN_12 = 12
    CAN_13 = 13
    CAN_14 = 14
    CAN_15 = 15


class TypeField(NamedTuple):
    """Parsed TYPE field components."""

    stream_type: M17Type
    data_type: M17DataType
    encryption_type: M17EncryptionType
    encryption_subtype: M17EncryptionSubtype
    can: int
    reserved: int


def parse_type_field(type_value: int) -> TypeField:
    """
    Parse a 16-bit TYPE field value into components.

    Args:
        type_value: 16-bit TYPE field value.

    Returns:
        TypeField with parsed components.

    Examples:
        >>> tf = parse_type_field(0x0005)  # Voice stream
        >>> tf.stream_type == M17Type.STREAM
        True
        >>> tf.data_type == M17DataType.VOICE
        True
    """
    return TypeField(
        stream_type=M17Type(type_value & 0x01),
        data_type=M17DataType((type_value >> 1) & 0x03),
        encryption_type=M17EncryptionType((type_value >> 3) & 0x03),
        encryption_subtype=M17EncryptionSubtype((type_value >> 5) & 0x03),
        can=(type_value >> 7) & 0x0F,
        reserved=(type_value >> 11) & 0x1F,
    )


def build_type_field(
    stream_type: M17Type = M17Type.STREAM,
    data_type: M17DataType = M17DataType.VOICE,
    encryption_type: M17EncryptionType = M17EncryptionType.NONE,
    encryption_subtype: M17EncryptionSubtype = M17EncryptionSubtype.TEXT,
    can: int = 0,
    reserved: int = 0,
) -> int:
    """
    Build a 16-bit TYPE field from components.

    Args:
        stream_type: Packet or stream mode.
        data_type: Data, voice, or voice+data.
        encryption_type: Encryption method.
        encryption_subtype: Encryption subtype / META interpretation.
        can: Channel Access Number (0-15).
        reserved: Reserved bits (should be 0).

    Returns:
        16-bit TYPE field value.

    Examples:
        >>> hex(build_type_field(M17Type.STREAM, M17DataType.VOICE))
        '0x5'
        >>> hex(build_type_field(M17Type.STREAM, M17DataType.VOICE_DATA))
        '0x7'
    """
    if not 0 <= can <= 15:
        raise ValueError(f"CAN must be 0-15, got {can}")
    if not 0 <= reserved <= 31:
        raise ValueError(f"Reserved must be 0-31, got {reserved}")

    return (
        (stream_type & 0x01)
        | ((data_type & 0x03) << 1)
        | ((encryption_type & 0x03) << 3)
        | ((encryption_subtype & 0x03) << 5)
        | ((can & 0x0F) << 7)
        | ((reserved & 0x1F) << 11)
    )


# Common pre-built TYPE field values
TYPE_VOICE_STREAM: int = build_type_field(M17Type.STREAM, M17DataType.VOICE)
TYPE_DATA_STREAM: int = build_type_field(M17Type.STREAM, M17DataType.DATA)
TYPE_VOICE_DATA_STREAM: int = build_type_field(M17Type.STREAM, M17DataType.VOICE_DATA)
TYPE_DATA_PACKET: int = build_type_field(M17Type.PACKET, M17DataType.DATA)
