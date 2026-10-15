"""Additional tests for M17 LSF module to improve coverage.

Tests for edge cases and error handling in frames/lsf.py.
"""

import pytest

from m17.core.address import Address
from m17.frames.lsf import (
    DataSource,
    LinkSetupFrame,
    MetaAesIV,
    MetaExtendedCallsign,
    MetaNonce,
    MetaPosition,
    MetaText,
    StationType,
    ValidityField,
)


class TestMetaPositionCoverage:
    """Additional coverage tests for MetaPosition."""

    def test_from_bytes_invalid_length(self):
        """Test from_bytes with invalid length raises ValueError."""
        with pytest.raises(ValueError, match="META field must be 14 bytes"):
            MetaPosition.from_bytes(bytes(10))

        with pytest.raises(ValueError, match="META field must be 14 bytes"):
            MetaPosition.from_bytes(bytes(20))

    def test_from_bytes_empty(self):
        """Test from_bytes with empty data raises ValueError."""
        with pytest.raises(ValueError, match="META field must be 14 bytes"):
            MetaPosition.from_bytes(b"")

    def test_roundtrip(self):
        """Test encode/decode roundtrip."""
        pos = MetaPosition(
            data_source=DataSource.GNSS_FIX,
            station_type=StationType.MOBILE,
            validity=ValidityField.ALL_VALID,
            latitude=45.5,
            longitude=-122.6,
            altitude=100.0,
            speed=50.0,
            bearing=90,
            radius=4.0,
        )

        encoded = pos.to_bytes()
        assert len(encoded) == 14

        decoded = MetaPosition.from_bytes(encoded)
        # Allow some rounding error
        assert abs(decoded.latitude - pos.latitude) < 0.01
        assert abs(decoded.longitude - pos.longitude) < 0.01


class TestMetaExtendedCallsignCoverage:
    """Additional coverage tests for MetaExtendedCallsign."""

    def test_from_bytes_invalid_length(self):
        """Test from_bytes with invalid length raises ValueError."""
        with pytest.raises(ValueError, match="META field must be 14 bytes"):
            MetaExtendedCallsign.from_bytes(bytes(10))

    def test_roundtrip(self):
        """Test encode/decode roundtrip."""
        ecd = MetaExtendedCallsign(
            callsign_field_1="W2FBI", callsign_field_2="N0CALL"
        )

        encoded = ecd.to_bytes()
        assert len(encoded) == 14

        decoded = MetaExtendedCallsign.from_bytes(encoded)
        assert decoded.callsign_field_1 == "W2FBI"
        assert decoded.callsign_field_2 == "N0CALL"

    def test_empty_callsigns(self):
        """Test with empty callsigns."""
        ecd = MetaExtendedCallsign(callsign_field_1="", callsign_field_2="")

        encoded = ecd.to_bytes()
        assert len(encoded) == 14


class TestMetaNonceCoverage:
    """Additional coverage tests for MetaNonce."""

    def test_from_bytes_invalid_length(self):
        """Test from_bytes with invalid length raises ValueError."""
        with pytest.raises(ValueError, match="META field must be 14 bytes"):
            MetaNonce.from_bytes(bytes(10))

    def test_timestamp_before_2020_epoch(self):
        """Test timestamp before 2020 epoch is handled."""
        # Unix timestamp before 2020 (Jan 1, 2019)
        nonce = MetaNonce(timestamp=1546300800, random_data=bytes(10))

        encoded = nonce.to_bytes()
        assert len(encoded) == 14

        # The timestamp should be clamped to 0 (2020 epoch)
        assert encoded[0:4] == b"\x00\x00\x00\x00"

    def test_roundtrip_future_timestamp(self):
        """Test encode/decode roundtrip with future timestamp."""
        # Timestamp in 2025
        future_ts = 1735689600
        nonce = MetaNonce(timestamp=future_ts, random_data=bytes(range(10)))

        encoded = nonce.to_bytes()
        decoded = MetaNonce.from_bytes(encoded)

        assert decoded.timestamp == future_ts
        assert decoded.random_data == bytes(range(10))

    def test_short_random_data_padded(self):
        """Test short random_data is padded."""
        nonce = MetaNonce(timestamp=1735689600, random_data=b"\x01\x02")

        encoded = nonce.to_bytes()
        assert len(encoded) == 14

        decoded = MetaNonce.from_bytes(encoded)
        assert decoded.random_data[:2] == b"\x01\x02"
        assert decoded.random_data[2:] == bytes(8)


class TestMetaTextCoverage:
    """Additional coverage tests for MetaText."""

    def test_from_bytes_invalid_length(self):
        """Test from_bytes with invalid length raises ValueError."""
        with pytest.raises(ValueError, match="META field must be 14 bytes"):
            MetaText.from_bytes(bytes(10))

    def test_from_bytes_unicode_decode_error(self):
        """Test from_bytes handles invalid UTF-8 gracefully."""
        # Create invalid UTF-8 sequence
        data = bytearray(14)
        data[0] = 0x11  # block_count=1, block_index=1
        data[1] = 0xFF  # Invalid UTF-8 start byte
        data[2] = 0xFE  # Invalid UTF-8 continuation

        decoded = MetaText.from_bytes(bytes(data))
        # Should use errors='replace' and contain replacement characters
        assert decoded.text is not None
        assert "\ufffd" in decoded.text

    def test_encode_multi_block_unicode_boundary(self):
        """Test encode_multi_block handles UTF-8 multi-byte characters."""
        # Create text with multi-byte characters that might split on boundaries
        # This tests the UnicodeDecodeError handling in encode_multi_block
        text = "Hello" + "日本語" * 10  # Mix of ASCII and 3-byte UTF-8

        blocks = MetaText.encode_multi_block(text)
        assert len(blocks) > 0

        # Decode and verify
        decoded = MetaText.decode_multi_block(blocks)
        # May have some replacement characters if split mid-character
        assert len(decoded) > 0

    def test_encode_multi_block_text_too_long(self):
        """Test encode_multi_block raises error for text too long."""
        long_text = "x" * 200  # More than 195 bytes

        with pytest.raises(ValueError, match="Text too long"):
            MetaText.encode_multi_block(long_text)

    def test_encode_decode_multi_block_roundtrip(self):
        """Test multi-block encode/decode roundtrip."""
        text = "Hello, this is a test message that spans multiple blocks!"

        blocks = MetaText.encode_multi_block(text)
        decoded = MetaText.decode_multi_block(blocks)

        assert decoded == text


class TestMetaAesIVCoverage:
    """Additional coverage tests for MetaAesIV."""

    def test_from_bytes_invalid_length(self):
        """Test from_bytes with invalid length raises ValueError."""
        with pytest.raises(ValueError, match="META field must be 14 bytes"):
            MetaAesIV.from_bytes(bytes(10))

    def test_to_bytes_short_iv(self):
        """Test to_bytes pads short IV."""
        aes_iv = MetaAesIV(iv=b"\x01\x02\x03")  # 3 bytes

        encoded = aes_iv.to_bytes()
        assert len(encoded) == 14
        assert encoded[:3] == b"\x01\x02\x03"
        assert encoded[3:] == bytes(11)

    def test_to_bytes_long_iv(self):
        """Test to_bytes truncates long IV."""
        aes_iv = MetaAesIV(iv=bytes(range(20)))  # 20 bytes

        encoded = aes_iv.to_bytes()
        assert len(encoded) == 14
        assert encoded == bytes(range(14))

    def test_roundtrip(self):
        """Test encode/decode roundtrip."""
        aes_iv = MetaAesIV(iv=bytes(range(14)))

        encoded = aes_iv.to_bytes()
        decoded = MetaAesIV.from_bytes(encoded)

        assert decoded.iv == bytes(range(14))


class TestLinkSetupFrameCoverage:
    """Additional coverage tests for LinkSetupFrame."""

    def test_meta_padding_short(self):
        """Test that short meta is padded."""
        lsf = LinkSetupFrame(dst="W2FBI", src="N0CALL", meta=b"\x01\x02")

        assert len(lsf.meta) == 14
        assert lsf.meta[:2] == b"\x01\x02"
        assert lsf.meta[2:] == bytes(12)

    def test_meta_truncation_long(self):
        """Test that long meta is truncated."""
        lsf = LinkSetupFrame(dst="W2FBI", src="N0CALL", meta=bytes(range(20)))

        assert len(lsf.meta) == 14
        assert lsf.meta == bytes(range(14))

    def test_meta_exact_length(self):
        """Test that exact length meta is unchanged."""
        meta = bytes(range(14))
        lsf = LinkSetupFrame(dst="W2FBI", src="N0CALL", meta=meta)

        assert lsf.meta == meta

    def test_str_representation(self):
        """Test __str__ method."""
        lsf = LinkSetupFrame(dst="W2FBI", src="N0CALL", type_field=0x0005)

        s = str(lsf)
        assert "N0CALL" in s
        assert "W2FBI" in s
        assert "0x0005" in s
        assert "LSF:" in s

    def test_from_bytes_wrong_length_with_crc(self):
        """Test from_bytes with wrong length (expecting CRC)."""
        with pytest.raises(ValueError, match="LSF must be 30 bytes"):
            LinkSetupFrame.from_bytes(bytes(28), has_crc=True)

    def test_from_bytes_wrong_length_without_crc(self):
        """Test from_bytes with wrong length (no CRC)."""
        with pytest.raises(ValueError, match="LSF must be 28 bytes"):
            LinkSetupFrame.from_bytes(bytes(30), has_crc=False)

    def test_from_bytes_invalid_crc(self):
        """Test from_bytes with invalid CRC."""
        # Create valid LSF bytes (30 bytes with CRC)
        lsf = LinkSetupFrame(dst="W2FBI", src="N0CALL")
        valid_data = lsf.to_bytes()  # This includes CRC (30 bytes)
        assert len(valid_data) == 30

        # Corrupt the data (change a byte in the middle)
        corrupted = bytearray(valid_data)
        corrupted[10] ^= 0xFF

        with pytest.raises(ValueError, match="Invalid LSF CRC"):
            LinkSetupFrame.from_bytes(bytes(corrupted), has_crc=True)

    def test_encryption_type_property(self):
        """Test encryption_type property."""
        from m17.core.types import M17EncryptionType

        lsf = LinkSetupFrame(dst="W2FBI", src="N0CALL", type_field=0x0008)

        assert lsf.encryption_type == M17EncryptionType((0x0008 >> 3) & 0x03)

    def test_encryption_subtype_property(self):
        """Test encryption_subtype property."""
        from m17.core.types import M17EncryptionSubtype

        lsf = LinkSetupFrame(dst="W2FBI", src="N0CALL", type_field=0x0020)

        assert lsf.encryption_subtype == M17EncryptionSubtype((0x0020 >> 5) & 0x03)

    def test_v3_properties(self):
        """Test v3.0.0 TYPE field properties."""
        # Build v3.0.0 type field
        from m17.core.types import M17Encryption, M17Meta, M17Payload, build_type_field_v3

        type_field = build_type_field_v3(
            payload=M17Payload.VOICE_3200,
            encryption=M17Encryption.AES_128,
            signed=True,
            meta=M17Meta.TEXT_DATA,
            can=5,
        )

        lsf = LinkSetupFrame(dst="W2FBI", src="N0CALL", type_field=type_field)

        assert lsf.payload_type == M17Payload.VOICE_3200
        assert lsf.encryption_v3 == M17Encryption.AES_128
        assert lsf.is_signed is True
        assert lsf.meta_type == M17Meta.TEXT_DATA
        assert lsf.can_v3 == 5

    def test_set_type_v3(self):
        """Test set_type_v3 method."""
        from m17.core.types import M17Encryption, M17Meta, M17Payload

        lsf = LinkSetupFrame(dst="W2FBI", src="N0CALL")
        lsf.set_type_v3(
            payload=M17Payload.DATA_ONLY,
            encryption=M17Encryption.SCRAMBLER_16,
            signed=False,
            meta=M17Meta.GNSS_POSITION,
            can=10,
        )

        assert lsf.payload_type == M17Payload.DATA_ONLY
        assert lsf.encryption_v3 == M17Encryption.SCRAMBLER_16
        assert lsf.is_signed is False
        assert lsf.meta_type == M17Meta.GNSS_POSITION
        assert lsf.can_v3 == 10

    def test_text_meta_methods(self):
        """Test text META field methods."""
        lsf = LinkSetupFrame(dst="W2FBI", src="N0CALL")
        lsf.set_text_meta("Hello M17!")

        text_meta = lsf.get_text_meta()
        assert text_meta.text == "Hello M17!"

    def test_aes_iv_meta_methods(self):
        """Test AES IV META field methods."""
        lsf = LinkSetupFrame(dst="W2FBI", src="N0CALL")
        iv = bytes(range(14))
        lsf.set_aes_iv_meta(iv)

        aes_iv = lsf.get_aes_iv_meta()
        assert aes_iv.iv == iv

    def test_create_text_message_frames(self):
        """Test create_text_message_frames class method."""
        text = "This is a longer message that needs multiple blocks to encode!"

        frames = LinkSetupFrame.create_text_message_frames(
            dst="W2FBI", src="N0CALL", text=text, can=7
        )

        assert len(frames) > 0
        for frame in frames:
            assert isinstance(frame, LinkSetupFrame)
            assert frame.can_v3 == 7

    def test_chunks_method(self):
        """Test chunks method for LICH transmission."""
        lsf = LinkSetupFrame(dst="W2FBI", src="N0CALL")

        # chunks() uses bytes(lsf) which returns 28 bytes (without CRC)
        chunks = lsf.chunks(chunk_size=6)

        # 28 bytes / 6 = 4 chunks of 6 bytes + 1 chunk of 4 bytes = 5 total chunks
        assert len(chunks) == 5

        # First 4 chunks should be 6 bytes, last chunk is 4 bytes
        for i, chunk in enumerate(chunks):
            if i < 4:
                assert len(chunk) == 6
            else:
                assert len(chunk) == 4

    def test_from_bytes_without_crc_valid(self):
        """Test from_bytes without CRC."""
        lsf1 = LinkSetupFrame(dst="W2FBI", src="N0CALL", type_field=0x1234)
        data_without_crc = lsf1.to_bytes_without_crc()

        lsf2 = LinkSetupFrame.from_bytes(data_without_crc, has_crc=False)

        assert lsf2.type_field == 0x1234

    def test_from_bytes_with_crc_valid(self):
        """Test from_bytes with valid CRC."""
        lsf1 = LinkSetupFrame(dst="W2FBI", src="N0CALL", type_field=0x5678)
        data_with_crc = lsf1.to_bytes()  # to_bytes() includes CRC (30 bytes)
        assert len(data_with_crc) == 30

        lsf2 = LinkSetupFrame.from_bytes(data_with_crc, has_crc=True)

        assert lsf2.type_field == 0x5678

    def test_nonce_meta_methods(self):
        """Test nonce META field methods."""
        lsf = LinkSetupFrame(dst="W2FBI", src="N0CALL")
        # set_nonce_meta takes timestamp and random_data separately
        lsf.set_nonce_meta(timestamp=1735689600, random_data=bytes(10))

        retrieved = lsf.get_nonce_meta()
        assert retrieved.timestamp == 1735689600

    def test_position_meta_methods(self):
        """Test position META field methods."""
        lsf = LinkSetupFrame(dst="W2FBI", src="N0CALL")
        # set_position_meta takes individual parameters, not a MetaPosition object
        lsf.set_position_meta(
            latitude=45.5, longitude=-122.6, altitude=100.0, speed=50.0
        )

        retrieved = lsf.get_position_meta()
        assert abs(retrieved.latitude - 45.5) < 0.01
        assert abs(retrieved.longitude - (-122.6)) < 0.01

    def test_extended_callsign_meta_methods(self):
        """Test extended callsign META field methods."""
        lsf = LinkSetupFrame(dst="W2FBI", src="N0CALL")
        # set_extended_callsign_meta takes two string arguments, not a MetaExtendedCallsign
        lsf.set_extended_callsign_meta(cf1="TEST1", cf2="TEST2")

        retrieved = lsf.get_extended_callsign_meta()
        assert retrieved.callsign_field_1 == "TEST1"
        assert retrieved.callsign_field_2 == "TEST2"


class TestValidityFieldEnum:
    """Tests for ValidityField enum."""

    def test_all_values(self):
        """Test all ValidityField values exist."""
        assert ValidityField.NONE == 0
        assert ValidityField.POSITION_VALID == 1
        assert ValidityField.ALTITUDE_VALID == 2
        assert ValidityField.POSITION_ALTITUDE_VALID == 3
        assert ValidityField.SPEED_VALID == 4
        assert ValidityField.ALL_VALID == 7


class TestDataSourceEnum:
    """Tests for DataSource enum."""

    def test_common_values(self):
        """Test common DataSource values."""
        assert DataSource.NONE == 0
        assert DataSource.GNSS_FIX == 1
        assert DataSource.GNSS_DR == 2
        assert DataSource.GNSS_LAST == 3
        assert DataSource.USER_INPUT == 4
        assert DataSource.EXTERNAL == 5


class TestStationTypeEnum:
    """Tests for StationType enum."""

    def test_common_values(self):
        """Test common StationType values."""
        assert StationType.FIXED == 0
        assert StationType.MOBILE == 1
        assert StationType.PORTABLE == 2
