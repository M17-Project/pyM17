"""
M17 TYPE Field Definitions

Supports both M17 v2.0.3 and v3.0.0 TYPE field formats.

v3.0.0 TYPE Field (16 bits):
  Byte 0 (bits 7-0):
    - Bits 7-4: PAYLOAD (4 bits) - payload/codec type
    - Bits 3-1: ENCRYPTION (3 bits) - encryption method
    - Bit 0: SIGNED (1 bit) - digital signature flag

  Byte 1 (bits 15-8):
    - Bits 15-12: META (4 bits) - META field type
    - Bits 11-8: CAN (4 bits) - Channel Access Number

v2.0.3 TYPE Field (16 bits) - Legacy:
    - Bit 0: Packet/Stream indicator
    - Bits 1-2: Data type
    - Bits 3-4: Encryption type
    - Bits 5-6: Encryption subtype
    - Bits 7-10: CAN
    - Bits 11-15: Reserved
"""

from __future__ import annotations

from enum import IntEnum, IntFlag
from typing import NamedTuple, Optional

__all__ = [
    # Version enum
    "M17Version",
    # v3.0.0 enums
    "M17Payload",
    "M17Encryption",
    "M17Meta",
    # v3.0.0 TypeField
    "TypeFieldV3",
    "parse_type_field_v3",
    "build_type_field_v3",
    # v2.0.3 legacy enums (deprecated but kept for compatibility)
    "M17Type",
    "M17DataType",
    "M17EncryptionType",
    "M17EncryptionSubtype",
    "M17MetaType",
    "ChannelAccessNumber",
    # v2.0.3 legacy TypeField
    "TypeField",
    "parse_type_field",
    "build_type_field",
    # Version detection
    "detect_type_field_version",
    # Common constants
    "TYPE_VOICE_STREAM",
    "TYPE_DATA_STREAM",
    "TYPE_VOICE_DATA_STREAM",
    "TYPE_DATA_PACKET",
]


# =============================================================================
# M17 Version Enum
# =============================================================================


class M17Version(IntEnum):
    """M17 specification version."""

    V2 = 2  # v2.0.3 (legacy)
    V3 = 3  # v3.0.0


# =============================================================================
# M17 v3.0.0 TYPE Field Enums
# =============================================================================


class M17Payload(IntEnum):
    """
    M17 v3.0.0 PAYLOAD field (bits 7-4 of byte 0).

    Specifies the payload/codec type.
    """

    VERSION_DETECT = 0x0  # Reserved for v2 detection (v2 always had 0 here)
    DATA_ONLY = 0x1  # Data only, no voice
    VOICE_3200 = 0x2  # 3200 bps Codec2 voice only
    VOICE_1600_DATA = 0x3  # 1600 bps Codec2 voice + data
    # 0x4 - 0xE: Reserved for future expansion
    PACKET = 0xF  # Packet data mode


class M17Encryption(IntEnum):
    """
    M17 v3.0.0 ENCRYPTION field (bits 3-1 of byte 0).

    Specifies the encryption method.
    """

    NONE = 0x0  # No encryption
    SCRAMBLER_8 = 0x1  # 8-bit scrambler
    SCRAMBLER_16 = 0x2  # 16-bit scrambler
    SCRAMBLER_24 = 0x3  # 24-bit scrambler
    AES_128 = 0x4  # 128-bit AES
    AES_192 = 0x5  # 192-bit AES
    AES_256 = 0x6  # 256-bit AES
    RESERVED = 0x7  # Reserved


class M17Meta(IntEnum):
    """
    M17 v3.0.0 META field type (bits 15-12 / bits 7-4 of byte 1).

    Specifies what the META field contains.
    """

    NONE = 0x0  # META is empty/unused
    GNSS_POSITION = 0x1  # GNSS position data (1 block)
    EXTENDED_CALLSIGN = 0x2  # Extended callsign data (1 block)
    TEXT_DATA = 0x3  # Text data (1-15 blocks in stream mode)
    # 0x4 - 0xE: Reserved for future expansion
    AES_IV = 0xF  # AES encryption IV (1 block)


class TypeFieldV3(NamedTuple):
    """
    Parsed M17 v3.0.0 TYPE field components.

    Attributes:
        payload: Payload/codec type (4 bits)
        encryption: Encryption method (3 bits)
        signed: Digital signature flag (1 bit)
        meta: META field type (4 bits)
        can: Channel Access Number (4 bits)
    """

    payload: M17Payload
    encryption: M17Encryption
    signed: bool
    meta: M17Meta
    can: int


def parse_type_field_v3(type_value: int) -> TypeFieldV3:
    """
    Parse a 16-bit TYPE field value into v3.0.0 components.

    Args:
        type_value: 16-bit TYPE field value.

    Returns:
        TypeFieldV3 with parsed components.

    Examples:
        >>> tf = parse_type_field_v3(0x1020)  # Voice 3200, no encryption, GNSS meta
        >>> tf.payload == M17Payload.VOICE_3200
        True
    """
    # Byte 0 (bits 7-0)
    payload_raw = (type_value >> 4) & 0x0F
    encryption_raw = (type_value >> 1) & 0x07
    signed = bool(type_value & 0x01)

    # Byte 1 (bits 15-8)
    meta_raw = (type_value >> 12) & 0x0F
    can = (type_value >> 8) & 0x0F

    # Convert to enums with fallback for reserved values
    try:
        payload = M17Payload(payload_raw)
    except ValueError:
        payload = M17Payload.VERSION_DETECT  # Unknown, treat as reserved

    try:
        encryption = M17Encryption(encryption_raw)
    except ValueError:
        encryption = M17Encryption.RESERVED

    try:
        meta = M17Meta(meta_raw)
    except ValueError:
        meta = M17Meta.NONE  # Unknown, treat as empty

    return TypeFieldV3(
        payload=payload,
        encryption=encryption,
        signed=signed,
        meta=meta,
        can=can,
    )


def build_type_field_v3(
    payload: M17Payload = M17Payload.VOICE_3200,
    encryption: M17Encryption = M17Encryption.NONE,
    signed: bool = False,
    meta: M17Meta = M17Meta.NONE,
    can: int = 0,
) -> int:
    """
    Build a 16-bit TYPE field from v3.0.0 components.

    Args:
        payload: Payload/codec type.
        encryption: Encryption method.
        signed: Digital signature flag (stream mode only).
        meta: META field type.
        can: Channel Access Number (0-15).

    Returns:
        16-bit TYPE field value.

    Raises:
        ValueError: If CAN is out of range.
        ValueError: If packet mode has encryption or signing enabled.

    Examples:
        >>> hex(build_type_field_v3(M17Payload.VOICE_3200, M17Encryption.NONE))
        '0x20'
    """
    if not 0 <= can <= 15:
        raise ValueError(f"CAN must be 0-15, got {can}")

    # Packet mode restrictions
    if payload == M17Payload.PACKET:
        if encryption != M17Encryption.NONE:
            raise ValueError("Packet mode does not support encryption")
        if signed:
            raise ValueError("Packet mode does not support signing")

    # Build the 16-bit value
    # Byte 0: [PAYLOAD:4][ENCRYPTION:3][SIGNED:1]
    byte0 = ((payload & 0x0F) << 4) | ((encryption & 0x07) << 1) | (1 if signed else 0)

    # Byte 1: [META:4][CAN:4]
    byte1 = ((meta & 0x0F) << 4) | (can & 0x0F)

    return (byte1 << 8) | byte0


# =============================================================================
# M17 v2.0.3 TYPE Field Enums (Legacy - Deprecated)
# =============================================================================


class M17Type(IntFlag):
    """
    M17 v2.0.3 stream/packet type indicator (bit 0).

    DEPRECATED: Use M17Payload for v3.0.0.
    """

    PACKET = 0  # Packet mode
    STREAM = 1  # Stream mode


class M17DataType(IntEnum):
    """
    M17 v2.0.3 data type field (bits 1-2).

    DEPRECATED: Use M17Payload for v3.0.0.
    """

    RESERVED = 0b00
    DATA = 0b01
    VOICE = 0b10
    VOICE_DATA = 0b11


class M17EncryptionType(IntEnum):
    """
    M17 v2.0.3 encryption type field (bits 3-4).

    DEPRECATED: Use M17Encryption for v3.0.0.
    """

    NONE = 0b00
    SCRAMBLER = 0b01
    AES = 0b10
    RESERVED = 0b11


class M17EncryptionSubtype(IntEnum):
    """
    M17 v2.0.3 encryption subtype field (bits 5-6).

    DEPRECATED: Use M17Meta for v3.0.0.
    """

    TEXT = 0b00  # When encryption is NONE: META contains text
    GNSS = 0b01  # When encryption is NONE: META contains GNSS position
    EXT_CALL = 0b10  # When encryption is NONE: META contains extended callsign data
    RESERVED = 0b11


class M17MetaType(IntEnum):
    """
    M17 v2.0.3 META field interpretation.

    DEPRECATED: Use M17Meta for v3.0.0.
    """

    TEXT = 0b00  # UTF-8 text data
    GNSS_POSITION = 0b01  # GNSS position data
    EXTENDED_CALLSIGN = 0b10  # Extended Callsign Data (ECD)
    RESERVED = 0b11


class ChannelAccessNumber(IntEnum):
    """Channel Access Number (CAN) values (0-15)."""

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
    """
    Parsed M17 v2.0.3 TYPE field components.

    DEPRECATED: Use TypeFieldV3 for v3.0.0.
    """

    stream_type: M17Type
    data_type: M17DataType
    encryption_type: M17EncryptionType
    encryption_subtype: M17EncryptionSubtype
    can: int
    reserved: int


def parse_type_field(type_value: int) -> TypeField:
    """
    Parse a 16-bit TYPE field value into v2.0.3 components.

    DEPRECATED: Use parse_type_field_v3() for v3.0.0.

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
    Build a 16-bit TYPE field from v2.0.3 components.

    DEPRECATED: Use build_type_field_v3() for v3.0.0.

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


# =============================================================================
# Version Detection
# =============================================================================


def detect_type_field_version(type_value: int) -> M17Version:
    """
    Detect whether a TYPE field is v2.0.3 or v3.0.0 format.

    The PAYLOAD field (bits 7-4 of byte 0) is used for detection:
    - If PAYLOAD == 0x0, it's a v2.0.3 frame (v2 always had these bits as 0)
    - If PAYLOAD != 0x0, it's a v3.0.0 frame

    Args:
        type_value: 16-bit TYPE field value.

    Returns:
        M17Version.V2 or M17Version.V3

    Examples:
        >>> detect_type_field_version(0x0005)  # v2.0.3 voice stream
        M17Version.V2
        >>> detect_type_field_version(0x0020)  # v3.0.0 voice 3200
        M17Version.V3
    """
    payload_field = (type_value >> 4) & 0x0F
    return M17Version.V3 if payload_field != 0 else M17Version.V2


# =============================================================================
# Common Pre-built TYPE Field Values (v2.0.3 format for backward compatibility)
# =============================================================================

# v2.0.3 format constants
TYPE_VOICE_STREAM: int = build_type_field(M17Type.STREAM, M17DataType.VOICE)
TYPE_DATA_STREAM: int = build_type_field(M17Type.STREAM, M17DataType.DATA)
TYPE_VOICE_DATA_STREAM: int = build_type_field(M17Type.STREAM, M17DataType.VOICE_DATA)
TYPE_DATA_PACKET: int = build_type_field(M17Type.PACKET, M17DataType.DATA)

# v3.0.0 format constants
TYPE_V3_VOICE_3200: int = build_type_field_v3(M17Payload.VOICE_3200)
TYPE_V3_VOICE_1600_DATA: int = build_type_field_v3(M17Payload.VOICE_1600_DATA)
TYPE_V3_DATA_ONLY: int = build_type_field_v3(M17Payload.DATA_ONLY)
TYPE_V3_PACKET: int = build_type_field_v3(M17Payload.PACKET)
