"""
Tests for M17 v3.0.0 specification features.
"""

import pytest

from m17.core.types import (
    M17Version,
    M17Payload,
    M17Encryption,
    M17Meta,
    TypeFieldV3,
    build_type_field_v3,
    parse_type_field_v3,
    detect_type_field_version,
    # Legacy v2.0.3
    build_type_field,
    M17Type,
    M17DataType,
)
from m17.frames.lsf import (
    LinkSetupFrame,
    MetaText,
    MetaAesIV,
)
from m17.frames.packet import (
    PacketProtocol,
    TLEPacket,
    PacketFrame,
)
from m17.core.address import Address


class TestTypeFieldV3:
    """Test v3.0.0 TYPE field parsing and building."""

    def test_build_voice_3200(self):
        """Test building voice 3200 TYPE field."""
        tf = build_type_field_v3(
            payload=M17Payload.VOICE_3200,
            encryption=M17Encryption.NONE,
            signed=False,
            meta=M17Meta.NONE,
            can=0,
        )
        # PAYLOAD=0x2 in bits 7-4, rest zeros
        # Byte 0: 0x20 (payload=2 << 4)
        assert tf == 0x0020

    def test_build_voice_with_gnss(self):
        """Test building voice with GNSS meta."""
        tf = build_type_field_v3(
            payload=M17Payload.VOICE_3200,
            encryption=M17Encryption.NONE,
            signed=False,
            meta=M17Meta.GNSS_POSITION,
            can=0,
        )
        # META=0x1 in bits 15-12
        assert (tf >> 12) & 0x0F == 0x1

    def test_build_with_can(self):
        """Test building TYPE field with CAN."""
        tf = build_type_field_v3(
            payload=M17Payload.VOICE_3200,
            can=5,
        )
        # CAN in bits 11-8
        assert (tf >> 8) & 0x0F == 5

    def test_build_with_encryption(self):
        """Test building TYPE field with AES encryption."""
        tf = build_type_field_v3(
            payload=M17Payload.VOICE_3200,
            encryption=M17Encryption.AES_256,
            meta=M17Meta.AES_IV,
        )
        # ENCRYPTION=0x6 in bits 3-1
        assert (tf >> 1) & 0x07 == 0x6

    def test_build_signed(self):
        """Test building TYPE field with signature flag."""
        tf = build_type_field_v3(
            payload=M17Payload.VOICE_3200,
            signed=True,
        )
        # SIGNED in bit 0
        assert tf & 0x01 == 1

    def test_build_packet_mode(self):
        """Test building packet mode TYPE field."""
        tf = build_type_field_v3(payload=M17Payload.PACKET)
        assert (tf >> 4) & 0x0F == 0x0F

    def test_packet_no_encryption(self):
        """Test that packet mode rejects encryption."""
        with pytest.raises(ValueError):
            build_type_field_v3(
                payload=M17Payload.PACKET,
                encryption=M17Encryption.AES_128,
            )

    def test_packet_no_signing(self):
        """Test that packet mode rejects signing."""
        with pytest.raises(ValueError):
            build_type_field_v3(
                payload=M17Payload.PACKET,
                signed=True,
            )

    def test_parse_roundtrip(self):
        """Test parse/build roundtrip."""
        original = build_type_field_v3(
            payload=M17Payload.VOICE_1600_DATA,
            encryption=M17Encryption.SCRAMBLER_16,
            signed=True,
            meta=M17Meta.TEXT_DATA,
            can=7,
        )
        parsed = parse_type_field_v3(original)

        assert parsed.payload == M17Payload.VOICE_1600_DATA
        assert parsed.encryption == M17Encryption.SCRAMBLER_16
        assert parsed.signed is True
        assert parsed.meta == M17Meta.TEXT_DATA
        assert parsed.can == 7


class TestVersionDetection:
    """Test version detection from TYPE field."""

    def test_detect_v2(self):
        """Test detecting v2.0.3 frame."""
        # v2.0.3 voice stream (0x0005)
        tf = build_type_field(M17Type.STREAM, M17DataType.VOICE)
        version = detect_type_field_version(tf)
        assert version == M17Version.V2

    def test_detect_v3(self):
        """Test detecting v3.0.0 frame."""
        tf = build_type_field_v3(M17Payload.VOICE_3200)
        version = detect_type_field_version(tf)
        assert version == M17Version.V3

    def test_detect_v3_all_payloads(self):
        """Test v3 detection for all payload types."""
        for payload in [M17Payload.DATA_ONLY, M17Payload.VOICE_3200,
                        M17Payload.VOICE_1600_DATA, M17Payload.PACKET]:
            tf = build_type_field_v3(payload=payload)
            assert detect_type_field_version(tf) == M17Version.V3


class TestMetaText:
    """Test multi-block text META field."""

    def test_single_block(self):
        """Test single-block text encoding."""
        meta = MetaText(text="Hello", block_count=1, block_index=1)
        data = meta.to_bytes()

        assert len(data) == 14
        # Control byte: 0x11 (1 block, index 1)
        assert data[0] == 0x11
        # Text content
        assert data[1:6] == b"Hello"

    def test_single_block_roundtrip(self):
        """Test single-block text roundtrip."""
        original = MetaText(text="Test 123", block_count=1, block_index=1)
        data = original.to_bytes()
        parsed = MetaText.from_bytes(data)

        assert parsed.text == "Test 123"
        assert parsed.block_count == 1
        assert parsed.block_index == 1

    def test_multi_block_encode(self):
        """Test multi-block text encoding."""
        long_text = "This is a longer text message for testing multi-block encoding"
        blocks = MetaText.encode_multi_block(long_text)

        # Should need multiple blocks (13 bytes per block)
        expected_blocks = (len(long_text.encode("utf-8")) + 12) // 13
        assert len(blocks) == expected_blocks

        # Each block should be 14 bytes
        for block in blocks:
            assert len(block) == 14

    def test_multi_block_roundtrip(self):
        """Test multi-block text roundtrip."""
        original_text = "Hello M17! This message spans multiple META blocks."
        blocks = MetaText.encode_multi_block(original_text)
        recovered = MetaText.decode_multi_block(blocks)

        assert recovered == original_text

    def test_max_text_length(self):
        """Test maximum text length (195 bytes)."""
        max_text = "x" * 195
        blocks = MetaText.encode_multi_block(max_text)
        assert len(blocks) == 15

    def test_text_too_long(self):
        """Test that text over 195 bytes raises error."""
        too_long = "x" * 196
        with pytest.raises(ValueError):
            MetaText.encode_multi_block(too_long)

    def test_utf8_encoding(self):
        """Test UTF-8 text encoding."""
        # Simple ASCII fits in 13 bytes
        meta = MetaText(text="Hello World!")
        data = meta.to_bytes()
        parsed = MetaText.from_bytes(data)
        assert parsed.text == "Hello World!"


class TestMetaAesIV:
    """Test AES IV META field."""

    def test_create_iv(self):
        """Test creating AES IV meta."""
        iv = bytes(range(14))
        meta = MetaAesIV(iv=iv)
        assert meta.iv == iv

    def test_to_bytes(self):
        """Test serialization."""
        iv = bytes([0xDE, 0xAD, 0xBE, 0xEF] + [0] * 10)
        meta = MetaAesIV(iv=iv)
        data = meta.to_bytes()

        assert len(data) == 14
        assert data[:4] == bytes([0xDE, 0xAD, 0xBE, 0xEF])

    def test_roundtrip(self):
        """Test AES IV roundtrip."""
        original_iv = bytes(range(14))
        meta = MetaAesIV(iv=original_iv)
        data = meta.to_bytes()
        parsed = MetaAesIV.from_bytes(data)

        assert parsed.iv == original_iv


class TestLinkSetupFrameV3:
    """Test LinkSetupFrame with v3.0.0 features."""

    def test_set_type_v3(self):
        """Test setting v3.0.0 TYPE field."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="N0CALL"),
        )
        lsf.set_type_v3(
            payload=M17Payload.VOICE_3200,
            meta=M17Meta.GNSS_POSITION,
        )

        assert lsf.version == M17Version.V3
        assert lsf.payload_type == M17Payload.VOICE_3200
        assert lsf.meta_type == M17Meta.GNSS_POSITION

    def test_version_detection(self):
        """Test version detection from LSF."""
        # v2.0.3 LSF
        lsf_v2 = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="N0CALL"),
            type_field=0x0005,  # v2.0.3 voice stream
        )
        assert lsf_v2.version == M17Version.V2

        # v3.0.0 LSF
        lsf_v3 = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="N0CALL"),
        )
        lsf_v3.set_type_v3(M17Payload.VOICE_3200)
        assert lsf_v3.version == M17Version.V3

    def test_set_text_meta(self):
        """Test setting text META."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="N0CALL"),
        )
        lsf.set_text_meta("Hello M17!")

        meta = lsf.get_text_meta()
        assert meta.text == "Hello M17!"

    def test_set_aes_iv_meta(self):
        """Test setting AES IV META."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="N0CALL"),
        )
        iv = bytes(range(14))
        lsf.set_aes_iv_meta(iv)

        meta = lsf.get_aes_iv_meta()
        assert meta.iv == iv

    def test_create_text_message_frames(self):
        """Test creating multi-frame text message."""
        frames = LinkSetupFrame.create_text_message_frames(
            dst="W2FBI",
            src="N0CALL",
            text="This is a test message that spans multiple frames.",
        )

        assert len(frames) > 1
        for frame in frames:
            assert frame.version == M17Version.V3
            assert frame.meta_type == M17Meta.TEXT_DATA


class TestPacketProtocol:
    """Test packet protocol identifiers."""

    def test_protocol_values(self):
        """Test protocol identifier values."""
        assert PacketProtocol.RAW == 0x00
        assert PacketProtocol.AX25 == 0x01
        assert PacketProtocol.APRS == 0x02
        assert PacketProtocol.LOWPAN_6 == 0x03
        assert PacketProtocol.IPV4 == 0x04
        assert PacketProtocol.SMS == 0x05
        assert PacketProtocol.WINLINK == 0x06
        assert PacketProtocol.TLE == 0x07


class TestTLEPacket:
    """Test TLE (Two-Line Element) packet."""

    # Example TLE for ISS
    ISS_NAME = "ISS (ZARYA)"
    ISS_LINE1 = "1 25544U 98067A   21275.52043534  .00001234  00000-0  12345-4 0  9999"
    ISS_LINE2 = "2 25544  51.6442 123.4567 0001234  12.3456 234.5678 15.48919755123456"

    def test_create_tle(self):
        """Test creating TLE packet."""
        tle = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1=self.ISS_LINE1,
            tle_line2=self.ISS_LINE2,
        )
        assert tle.satellite_name == self.ISS_NAME
        assert tle.tle_line1 == self.ISS_LINE1
        assert tle.tle_line2 == self.ISS_LINE2

    def test_tle_validity(self):
        """Test TLE validity checking."""
        valid_tle = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1=self.ISS_LINE1,
            tle_line2=self.ISS_LINE2,
        )
        assert valid_tle.is_valid is True

        invalid_tle = TLEPacket(
            satellite_name="TEST",
            tle_line1="invalid",
            tle_line2="data",
        )
        assert invalid_tle.is_valid is False

    def test_tle_to_bytes(self):
        """Test TLE serialization."""
        tle = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1=self.ISS_LINE1,
            tle_line2=self.ISS_LINE2,
        )
        data = tle.to_bytes()

        # Should start with protocol ID
        assert data[0] == PacketProtocol.TLE

        # Should end with CRC
        assert len(data) > 3

    def test_tle_roundtrip(self):
        """Test TLE serialization roundtrip."""
        original = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1=self.ISS_LINE1,
            tle_line2=self.ISS_LINE2,
        )
        data = original.to_bytes()
        parsed = TLEPacket.from_bytes(data)

        assert parsed.satellite_name == original.satellite_name
        assert parsed.tle_line1 == original.tle_line1
        assert parsed.tle_line2 == original.tle_line2

    def test_tle_to_packet_frame(self):
        """Test converting TLE to PacketFrame."""
        tle = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1=self.ISS_LINE1,
            tle_line2=self.ISS_LINE2,
        )
        frame = tle.to_packet_frame()

        assert isinstance(frame, PacketFrame)
        assert len(frame) > 0

    def test_tle_from_packet_frame(self):
        """Test parsing TLE from PacketFrame."""
        original = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1=self.ISS_LINE1,
            tle_line2=self.ISS_LINE2,
        )
        frame = original.to_packet_frame()
        parsed = TLEPacket.from_packet_frame(frame)

        assert parsed.satellite_name == original.satellite_name

    def test_tle_string_output(self):
        """Test TLE string formatting."""
        tle = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1=self.ISS_LINE1,
            tle_line2=self.ISS_LINE2,
        )
        tle_str = tle.to_tle_string()

        lines = tle_str.split("\n")
        assert len(lines) == 3
        assert lines[0] == self.ISS_NAME
        assert lines[1] == self.ISS_LINE1
        assert lines[2] == self.ISS_LINE2

    def test_tle_crc_verification(self):
        """Test TLE CRC verification on corrupted data."""
        tle = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1=self.ISS_LINE1,
            tle_line2=self.ISS_LINE2,
        )
        data = bytearray(tle.to_bytes())

        # Corrupt the data
        data[10] ^= 0xFF

        with pytest.raises(ValueError, match="CRC mismatch"):
            TLEPacket.from_bytes(bytes(data))
