"""Comprehensive tests for M17 TYPE field definitions.

Tests for both v2.0.3 and v3.0.0 TYPE field parsing and building,
including edge cases and error handling.
"""

import pytest

from m17.core.types import (
    # Constants
    TYPE_DATA_PACKET,
    TYPE_DATA_STREAM,
    TYPE_VOICE_DATA_STREAM,
    TYPE_VOICE_STREAM,
    # v2.0.3
    ChannelAccessNumber,
    M17DataType,
    # v3.0.0
    M17Encryption,
    M17EncryptionSubtype,
    M17EncryptionType,
    M17Meta,
    M17MetaType,
    M17Payload,
    M17Type,
    M17Version,
    TypeField,
    TypeFieldV3,
    build_type_field,
    build_type_field_v3,
    detect_type_field_version,
    parse_type_field,
    parse_type_field_v3,
)


class TestM17Payload:
    """Test M17Payload enum values."""

    def test_version_detect_value(self):
        """Test VERSION_DETECT is 0."""
        assert M17Payload.VERSION_DETECT == 0x0

    def test_data_only_value(self):
        """Test DATA_ONLY value."""
        assert M17Payload.DATA_ONLY == 0x1

    def test_voice_3200_value(self):
        """Test VOICE_3200 value."""
        assert M17Payload.VOICE_3200 == 0x2

    def test_voice_1600_data_value(self):
        """Test VOICE_1600_DATA value."""
        assert M17Payload.VOICE_1600_DATA == 0x3

    def test_packet_value(self):
        """Test PACKET value."""
        assert M17Payload.PACKET == 0xF


class TestM17Encryption:
    """Test M17Encryption enum values."""

    def test_none_value(self):
        """Test NONE encryption."""
        assert M17Encryption.NONE == 0x0

    def test_scrambler_values(self):
        """Test scrambler encryption values."""
        assert M17Encryption.SCRAMBLER_8 == 0x1
        assert M17Encryption.SCRAMBLER_16 == 0x2
        assert M17Encryption.SCRAMBLER_24 == 0x3

    def test_aes_values(self):
        """Test AES encryption values."""
        assert M17Encryption.AES_128 == 0x4
        assert M17Encryption.AES_192 == 0x5
        assert M17Encryption.AES_256 == 0x6

    def test_reserved_value(self):
        """Test RESERVED value."""
        assert M17Encryption.RESERVED == 0x7


class TestM17Meta:
    """Test M17Meta enum values."""

    def test_none_value(self):
        """Test NONE meta."""
        assert M17Meta.NONE == 0x0

    def test_gnss_position_value(self):
        """Test GNSS_POSITION value."""
        assert M17Meta.GNSS_POSITION == 0x1

    def test_extended_callsign_value(self):
        """Test EXTENDED_CALLSIGN value."""
        assert M17Meta.EXTENDED_CALLSIGN == 0x2

    def test_text_data_value(self):
        """Test TEXT_DATA value."""
        assert M17Meta.TEXT_DATA == 0x3

    def test_aes_iv_value(self):
        """Test AES_IV value."""
        assert M17Meta.AES_IV == 0xF


class TestTypeFieldV3Namedtuple:
    """Test TypeFieldV3 named tuple."""

    def test_create_type_field_v3(self):
        """Test creating TypeFieldV3 directly."""
        tf = TypeFieldV3(
            payload=M17Payload.VOICE_3200,
            encryption=M17Encryption.NONE,
            signed=False,
            meta=M17Meta.NONE,
            can=0,
        )
        assert tf.payload == M17Payload.VOICE_3200
        assert tf.encryption == M17Encryption.NONE
        assert tf.signed is False
        assert tf.meta == M17Meta.NONE
        assert tf.can == 0

    def test_type_field_v3_as_tuple(self):
        """Test TypeFieldV3 tuple unpacking."""
        tf = TypeFieldV3(
            payload=M17Payload.DATA_ONLY,
            encryption=M17Encryption.AES_128,
            signed=True,
            meta=M17Meta.TEXT_DATA,
            can=5,
        )
        payload, encryption, signed, meta, can = tf
        assert payload == M17Payload.DATA_ONLY
        assert encryption == M17Encryption.AES_128
        assert signed is True
        assert meta == M17Meta.TEXT_DATA
        assert can == 5


class TestParseTypeFieldV3:
    """Test parse_type_field_v3 function."""

    def test_parse_voice_3200(self):
        """Test parsing voice 3200 TYPE field."""
        tf = parse_type_field_v3(0x0020)
        assert tf.payload == M17Payload.VOICE_3200
        assert tf.encryption == M17Encryption.NONE
        assert tf.signed is False
        assert tf.meta == M17Meta.NONE
        assert tf.can == 0

    def test_parse_with_encryption(self):
        """Test parsing TYPE field with encryption."""
        # ENCRYPTION=AES_128 (0x4) in bits 3-1
        type_value = (0x4 << 1) | (M17Payload.VOICE_3200 << 4)
        tf = parse_type_field_v3(type_value)
        assert tf.encryption == M17Encryption.AES_128

    def test_parse_with_signed(self):
        """Test parsing TYPE field with signed flag."""
        # SIGNED in bit 0
        type_value = (M17Payload.VOICE_3200 << 4) | 0x01
        tf = parse_type_field_v3(type_value)
        assert tf.signed is True

    def test_parse_with_meta(self):
        """Test parsing TYPE field with META."""
        # META=GNSS_POSITION (0x1) in bits 15-12
        type_value = (0x1 << 12) | (M17Payload.VOICE_3200 << 4)
        tf = parse_type_field_v3(type_value)
        assert tf.meta == M17Meta.GNSS_POSITION

    def test_parse_with_can(self):
        """Test parsing TYPE field with CAN."""
        # CAN=7 in bits 11-8
        type_value = (7 << 8) | (M17Payload.VOICE_3200 << 4)
        tf = parse_type_field_v3(type_value)
        assert tf.can == 7

    def test_parse_reserved_payload(self):
        """Test parsing TYPE field with reserved payload value."""
        # Reserved payload value (e.g., 0x8) should fall back to VERSION_DETECT
        type_value = 0x8 << 4  # Reserved payload value
        tf = parse_type_field_v3(type_value)
        assert tf.payload == M17Payload.VERSION_DETECT

    def test_parse_reserved_encryption(self):
        """Test parsing TYPE field with reserved encryption value."""
        # Reserved encryption value (0x7)
        type_value = (M17Payload.VOICE_3200 << 4) | (0x7 << 1)
        tf = parse_type_field_v3(type_value)
        assert tf.encryption == M17Encryption.RESERVED

    def test_parse_reserved_meta(self):
        """Test parsing TYPE field with reserved meta value."""
        # Reserved meta value (e.g., 0x8)
        type_value = (0x8 << 12) | (M17Payload.VOICE_3200 << 4)
        tf = parse_type_field_v3(type_value)
        assert tf.meta == M17Meta.NONE

    def test_parse_all_max_values(self):
        """Test parsing with maximum valid values."""
        type_value = build_type_field_v3(
            payload=M17Payload.PACKET,
            encryption=M17Encryption.NONE,  # Packet doesn't support encryption
            signed=False,  # Packet doesn't support signing
            meta=M17Meta.AES_IV,
            can=15,
        )
        tf = parse_type_field_v3(type_value)
        assert tf.payload == M17Payload.PACKET
        assert tf.meta == M17Meta.AES_IV
        assert tf.can == 15


class TestBuildTypeFieldV3:
    """Test build_type_field_v3 function."""

    def test_build_default(self):
        """Test building with default values."""
        tf = build_type_field_v3()
        # Default: VOICE_3200, NONE encryption, not signed, NONE meta, CAN=0
        assert tf == 0x0020

    def test_build_all_payloads(self):
        """Test building with all payload types."""
        for payload in M17Payload:
            if payload == M17Payload.PACKET:
                # Packet can't have encryption or signing
                tf = build_type_field_v3(payload=payload, encryption=M17Encryption.NONE)
            else:
                tf = build_type_field_v3(payload=payload)
            parsed = parse_type_field_v3(tf)
            assert parsed.payload == payload

    def test_build_all_encryptions(self):
        """Test building with all encryption types."""
        for encryption in M17Encryption:
            tf = build_type_field_v3(
                payload=M17Payload.VOICE_3200,
                encryption=encryption,
            )
            parsed = parse_type_field_v3(tf)
            assert parsed.encryption == encryption

    def test_build_all_metas(self):
        """Test building with all meta types."""
        for meta in M17Meta:
            tf = build_type_field_v3(
                payload=M17Payload.VOICE_3200,
                meta=meta,
            )
            parsed = parse_type_field_v3(tf)
            assert parsed.meta == meta

    def test_build_all_can_values(self):
        """Test building with all CAN values 0-15."""
        for can in range(16):
            tf = build_type_field_v3(can=can)
            parsed = parse_type_field_v3(tf)
            assert parsed.can == can

    def test_build_can_out_of_range_negative(self):
        """Test CAN < 0 raises ValueError."""
        with pytest.raises(ValueError, match="CAN must be 0-15"):
            build_type_field_v3(can=-1)

    def test_build_can_out_of_range_high(self):
        """Test CAN > 15 raises ValueError."""
        with pytest.raises(ValueError, match="CAN must be 0-15"):
            build_type_field_v3(can=16)

    def test_build_packet_with_encryption_raises(self):
        """Test packet mode with encryption raises."""
        with pytest.raises(ValueError, match="Packet mode does not support encryption"):
            build_type_field_v3(
                payload=M17Payload.PACKET,
                encryption=M17Encryption.AES_128,
            )

    def test_build_packet_with_signing_raises(self):
        """Test packet mode with signing raises."""
        with pytest.raises(ValueError, match="Packet mode does not support signing"):
            build_type_field_v3(
                payload=M17Payload.PACKET,
                signed=True,
            )


class TestM17Version:
    """Test M17Version enum."""

    def test_v2_value(self):
        """Test V2 value."""
        assert M17Version.V2 == 2

    def test_v3_value(self):
        """Test V3 value."""
        assert M17Version.V3 == 3


# =============================================================================
# v2.0.3 TYPE Field Tests
# =============================================================================


class TestM17TypeLegacy:
    """Test M17Type enum (v2.0.3 legacy)."""

    def test_packet_value(self):
        """Test PACKET value."""
        assert M17Type.PACKET == 0

    def test_stream_value(self):
        """Test STREAM value."""
        assert M17Type.STREAM == 1


class TestM17DataTypeLegacy:
    """Test M17DataType enum (v2.0.3 legacy)."""

    def test_reserved_value(self):
        """Test RESERVED value."""
        assert M17DataType.RESERVED == 0b00

    def test_data_value(self):
        """Test DATA value."""
        assert M17DataType.DATA == 0b01

    def test_voice_value(self):
        """Test VOICE value."""
        assert M17DataType.VOICE == 0b10

    def test_voice_data_value(self):
        """Test VOICE_DATA value."""
        assert M17DataType.VOICE_DATA == 0b11


class TestM17EncryptionTypeLegacy:
    """Test M17EncryptionType enum (v2.0.3 legacy)."""

    def test_none_value(self):
        """Test NONE value."""
        assert M17EncryptionType.NONE == 0b00

    def test_scrambler_value(self):
        """Test SCRAMBLER value."""
        assert M17EncryptionType.SCRAMBLER == 0b01

    def test_aes_value(self):
        """Test AES value."""
        assert M17EncryptionType.AES == 0b10

    def test_reserved_value(self):
        """Test RESERVED value."""
        assert M17EncryptionType.RESERVED == 0b11


class TestM17EncryptionSubtypeLegacy:
    """Test M17EncryptionSubtype enum (v2.0.3 legacy)."""

    def test_text_value(self):
        """Test TEXT value."""
        assert M17EncryptionSubtype.TEXT == 0b00

    def test_gnss_value(self):
        """Test GNSS value."""
        assert M17EncryptionSubtype.GNSS == 0b01

    def test_ext_call_value(self):
        """Test EXT_CALL value."""
        assert M17EncryptionSubtype.EXT_CALL == 0b10

    def test_reserved_value(self):
        """Test RESERVED value."""
        assert M17EncryptionSubtype.RESERVED == 0b11


class TestM17MetaTypeLegacy:
    """Test M17MetaType enum (v2.0.3 legacy)."""

    def test_text_value(self):
        """Test TEXT value."""
        assert M17MetaType.TEXT == 0b00

    def test_gnss_position_value(self):
        """Test GNSS_POSITION value."""
        assert M17MetaType.GNSS_POSITION == 0b01

    def test_extended_callsign_value(self):
        """Test EXTENDED_CALLSIGN value."""
        assert M17MetaType.EXTENDED_CALLSIGN == 0b10

    def test_reserved_value(self):
        """Test RESERVED value."""
        assert M17MetaType.RESERVED == 0b11


class TestChannelAccessNumber:
    """Test ChannelAccessNumber enum."""

    def test_all_can_values(self):
        """Test all CAN values 0-15."""
        for i in range(16):
            can = ChannelAccessNumber(i)
            assert can.value == i

    def test_can_names(self):
        """Test CAN enum names."""
        assert ChannelAccessNumber.CAN_0.value == 0
        assert ChannelAccessNumber.CAN_15.value == 15


class TestTypeFieldLegacy:
    """Test TypeField named tuple (v2.0.3 legacy)."""

    def test_create_type_field(self):
        """Test creating TypeField directly."""
        tf = TypeField(
            stream_type=M17Type.STREAM,
            data_type=M17DataType.VOICE,
            encryption_type=M17EncryptionType.NONE,
            encryption_subtype=M17EncryptionSubtype.TEXT,
            can=0,
            reserved=0,
        )
        assert tf.stream_type == M17Type.STREAM
        assert tf.data_type == M17DataType.VOICE

    def test_type_field_as_tuple(self):
        """Test TypeField tuple unpacking."""
        tf = TypeField(
            stream_type=M17Type.PACKET,
            data_type=M17DataType.DATA,
            encryption_type=M17EncryptionType.AES,
            encryption_subtype=M17EncryptionSubtype.GNSS,
            can=5,
            reserved=0,
        )
        stream_type, data_type, encryption_type, encryption_subtype, can, reserved = tf
        assert stream_type == M17Type.PACKET
        assert data_type == M17DataType.DATA


class TestParseTypeFieldLegacy:
    """Test parse_type_field function (v2.0.3 legacy)."""

    def test_parse_voice_stream(self):
        """Test parsing voice stream."""
        tf = parse_type_field(0x0005)
        assert tf.stream_type == M17Type.STREAM
        assert tf.data_type == M17DataType.VOICE
        assert tf.encryption_type == M17EncryptionType.NONE
        assert tf.can == 0

    def test_parse_data_packet(self):
        """Test parsing data packet."""
        tf = parse_type_field(0x0002)
        assert tf.stream_type == M17Type.PACKET
        assert tf.data_type == M17DataType.DATA

    def test_parse_with_can(self):
        """Test parsing with CAN value."""
        # CAN in bits 7-10
        type_value = 0x0005 | (7 << 7)
        tf = parse_type_field(type_value)
        assert tf.can == 7

    def test_parse_with_reserved(self):
        """Test parsing with reserved bits."""
        # Reserved in bits 11-15
        type_value = 0x0005 | (0x1F << 11)
        tf = parse_type_field(type_value)
        assert tf.reserved == 0x1F

    def test_parse_all_fields(self):
        """Test parsing all fields."""
        # Build a complete v2.0.3 TYPE field
        type_value = (
            M17Type.STREAM  # bit 0
            | (M17DataType.VOICE_DATA << 1)  # bits 1-2
            | (M17EncryptionType.SCRAMBLER << 3)  # bits 3-4
            | (M17EncryptionSubtype.GNSS << 5)  # bits 5-6
            | (10 << 7)  # CAN in bits 7-10
            | (3 << 11)  # reserved in bits 11-15
        )
        tf = parse_type_field(type_value)
        assert tf.stream_type == M17Type.STREAM
        assert tf.data_type == M17DataType.VOICE_DATA
        assert tf.encryption_type == M17EncryptionType.SCRAMBLER
        assert tf.encryption_subtype == M17EncryptionSubtype.GNSS
        assert tf.can == 10
        assert tf.reserved == 3


class TestBuildTypeFieldLegacy:
    """Test build_type_field function (v2.0.3 legacy)."""

    def test_build_voice_stream(self):
        """Test building voice stream."""
        tf = build_type_field(M17Type.STREAM, M17DataType.VOICE)
        assert tf == 0x0005

    def test_build_data_packet(self):
        """Test building data packet."""
        tf = build_type_field(M17Type.PACKET, M17DataType.DATA)
        assert tf == 0x0002

    def test_build_with_can(self):
        """Test building with CAN."""
        tf = build_type_field(M17Type.STREAM, M17DataType.VOICE, can=7)
        assert (tf >> 7) & 0x0F == 7

    def test_build_with_reserved(self):
        """Test building with reserved bits."""
        tf = build_type_field(M17Type.STREAM, M17DataType.VOICE, reserved=0x1F)
        assert (tf >> 11) & 0x1F == 0x1F

    def test_build_can_out_of_range_negative(self):
        """Test CAN < 0 raises ValueError."""
        with pytest.raises(ValueError, match="CAN must be 0-15"):
            build_type_field(M17Type.STREAM, M17DataType.VOICE, can=-1)

    def test_build_can_out_of_range_high(self):
        """Test CAN > 15 raises ValueError."""
        with pytest.raises(ValueError, match="CAN must be 0-15"):
            build_type_field(M17Type.STREAM, M17DataType.VOICE, can=16)

    def test_build_reserved_out_of_range_negative(self):
        """Test reserved < 0 raises ValueError."""
        with pytest.raises(ValueError, match="Reserved must be 0-31"):
            build_type_field(M17Type.STREAM, M17DataType.VOICE, reserved=-1)

    def test_build_reserved_out_of_range_high(self):
        """Test reserved > 31 raises ValueError."""
        with pytest.raises(ValueError, match="Reserved must be 0-31"):
            build_type_field(M17Type.STREAM, M17DataType.VOICE, reserved=32)

    def test_build_roundtrip(self):
        """Test build/parse roundtrip."""
        original = build_type_field(
            stream_type=M17Type.STREAM,
            data_type=M17DataType.VOICE_DATA,
            encryption_type=M17EncryptionType.AES,
            encryption_subtype=M17EncryptionSubtype.EXT_CALL,
            can=12,
            reserved=7,
        )
        parsed = parse_type_field(original)
        rebuilt = build_type_field(
            stream_type=parsed.stream_type,
            data_type=parsed.data_type,
            encryption_type=parsed.encryption_type,
            encryption_subtype=parsed.encryption_subtype,
            can=parsed.can,
            reserved=parsed.reserved,
        )
        assert rebuilt == original


class TestDetectTypeFieldVersion:
    """Test detect_type_field_version function."""

    def test_detect_v2_voice_stream(self):
        """Test detecting v2.0.3 voice stream."""
        version = detect_type_field_version(0x0005)
        assert version == M17Version.V2

    def test_detect_v2_data_packet(self):
        """Test detecting v2.0.3 data packet."""
        version = detect_type_field_version(0x0002)
        assert version == M17Version.V2

    def test_detect_v2_zero(self):
        """Test detecting v2.0.3 with zero TYPE field."""
        version = detect_type_field_version(0x0000)
        assert version == M17Version.V2

    def test_detect_v3_voice_3200(self):
        """Test detecting v3.0.0 voice 3200."""
        tf = build_type_field_v3(M17Payload.VOICE_3200)
        version = detect_type_field_version(tf)
        assert version == M17Version.V3

    def test_detect_v3_data_only(self):
        """Test detecting v3.0.0 data only."""
        tf = build_type_field_v3(M17Payload.DATA_ONLY)
        version = detect_type_field_version(tf)
        assert version == M17Version.V3

    def test_detect_v3_packet(self):
        """Test detecting v3.0.0 packet."""
        tf = build_type_field_v3(M17Payload.PACKET)
        version = detect_type_field_version(tf)
        assert version == M17Version.V3


class TestTypeFieldConstants:
    """Test pre-built TYPE field constants."""

    def test_type_voice_stream(self):
        """Test TYPE_VOICE_STREAM constant."""
        assert TYPE_VOICE_STREAM == 0x0005
        tf = parse_type_field(TYPE_VOICE_STREAM)
        assert tf.stream_type == M17Type.STREAM
        assert tf.data_type == M17DataType.VOICE

    def test_type_data_stream(self):
        """Test TYPE_DATA_STREAM constant."""
        tf = parse_type_field(TYPE_DATA_STREAM)
        assert tf.stream_type == M17Type.STREAM
        assert tf.data_type == M17DataType.DATA

    def test_type_voice_data_stream(self):
        """Test TYPE_VOICE_DATA_STREAM constant."""
        tf = parse_type_field(TYPE_VOICE_DATA_STREAM)
        assert tf.stream_type == M17Type.STREAM
        assert tf.data_type == M17DataType.VOICE_DATA

    def test_type_data_packet(self):
        """Test TYPE_DATA_PACKET constant."""
        tf = parse_type_field(TYPE_DATA_PACKET)
        assert tf.stream_type == M17Type.PACKET
        assert tf.data_type == M17DataType.DATA
