"""
Tests for M17 Link Setup Frame (LSF).
"""

import pytest

from m17.frames.lsf import (
    LinkSetupFrame,
    MetaPosition,
    MetaExtendedCallsign,
    MetaNonce,
    DataSource,
    StationType,
    ValidityField,
)
from m17.core.address import Address
from m17.core.types import M17Type, M17DataType


class TestLinkSetupFrame:
    """Test LinkSetupFrame class."""

    def test_create_basic(self):
        """Test creating basic LSF."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="N0CALL"),
        )
        assert lsf.dst.callsign == "W2FBI"
        assert lsf.src.callsign == "N0CALL"

    def test_create_with_strings(self):
        """Test creating LSF with string callsigns."""
        lsf = LinkSetupFrame(
            dst="W2FBI",
            src="N0CALL",
        )
        assert lsf.dst.callsign == "W2FBI"
        assert lsf.src.callsign == "N0CALL"

    def test_default_type(self):
        """Test default TYPE field."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="N0CALL"),
        )
        # Default should be voice stream (0x0005)
        assert lsf.type_field == 0x0005

    def test_to_bytes_without_crc(self):
        """Test serialization without CRC."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="N0CALL"),
        )
        data = lsf.to_bytes_without_crc()
        assert len(data) == 28

    def test_to_bytes_with_crc(self):
        """Test serialization with CRC."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="N0CALL"),
        )
        data = lsf.to_bytes()
        assert len(data) == 30

    def test_from_bytes_without_crc(self):
        """Test parsing without CRC."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="N0CALL"),
        )
        data = lsf.to_bytes_without_crc()
        parsed = LinkSetupFrame.from_bytes(data, has_crc=False)
        assert parsed.dst.callsign == "W2FBI"
        assert parsed.src.callsign == "N0CALL"

    def test_from_bytes_with_crc(self):
        """Test parsing with CRC."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="N0CALL"),
        )
        data = lsf.to_bytes()
        parsed = LinkSetupFrame.from_bytes(data, has_crc=True)
        assert parsed.dst.callsign == "W2FBI"
        assert parsed.src.callsign == "N0CALL"

    def test_crc_property(self):
        """Test CRC calculation."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="N0CALL"),
        )
        crc = lsf.crc
        assert isinstance(crc, int)
        assert 0 <= crc <= 0xFFFF

    def test_type_properties(self):
        """Test TYPE field properties."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="N0CALL"),
            type_field=0x0005,  # Voice stream
        )
        assert lsf.stream_type == M17Type.STREAM
        assert lsf.data_type == M17DataType.VOICE

    def test_chunks(self):
        """Test LICH chunking."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="N0CALL"),
        )
        chunks = lsf.chunks()
        assert len(chunks) == 5  # 28 bytes / 6 = 4.67, rounds to 5
        for chunk in chunks[:-1]:
            assert len(chunk) == 6


class TestMetaPosition:
    """Test GNSS position META field."""

    def test_create_default(self):
        """Test creating default position."""
        pos = MetaPosition()
        assert pos.latitude == 0.0
        assert pos.longitude == 0.0

    def test_to_bytes(self):
        """Test serialization."""
        pos = MetaPosition(
            latitude=40.7128,
            longitude=-74.0060,
            altitude=100.0,
            speed=50.0,
            bearing=90,
        )
        data = pos.to_bytes()
        assert len(data) == 14

    def test_from_bytes_roundtrip(self):
        """Test serialization roundtrip."""
        original = MetaPosition(
            data_source=DataSource.GNSS_FIX,
            station_type=StationType.MOBILE,
            validity=ValidityField.ALL_VALID,
            latitude=40.7128,
            longitude=-74.0060,
            altitude=500.0,
            speed=100.0,
            bearing=180,
            radius=8.0,
        )
        data = original.to_bytes()
        parsed = MetaPosition.from_bytes(data)

        # Allow for quantization error
        assert abs(parsed.latitude - original.latitude) < 0.001
        assert abs(parsed.longitude - original.longitude) < 0.001
        assert abs(parsed.altitude - original.altitude) < 1.0
        assert abs(parsed.speed - original.speed) < 1.0
        assert parsed.bearing == original.bearing

    def test_latitude_limits(self):
        """Test latitude at limits."""
        pos_north = MetaPosition(latitude=90.0)
        pos_south = MetaPosition(latitude=-90.0)

        data_north = pos_north.to_bytes()
        data_south = pos_south.to_bytes()

        parsed_north = MetaPosition.from_bytes(data_north)
        parsed_south = MetaPosition.from_bytes(data_south)

        assert abs(parsed_north.latitude - 90.0) < 0.01
        assert abs(parsed_south.latitude - (-90.0)) < 0.01

    def test_longitude_limits(self):
        """Test longitude at limits."""
        pos_east = MetaPosition(longitude=180.0)
        pos_west = MetaPosition(longitude=-180.0)

        data_east = pos_east.to_bytes()
        data_west = pos_west.to_bytes()

        parsed_east = MetaPosition.from_bytes(data_east)
        parsed_west = MetaPosition.from_bytes(data_west)

        assert abs(parsed_east.longitude - 180.0) < 0.01
        assert abs(parsed_west.longitude - (-180.0)) < 0.01


class TestMetaExtendedCallsign:
    """Test Extended Callsign Data META field."""

    def test_create(self):
        """Test creating ECD."""
        ecd = MetaExtendedCallsign(
            callsign_field_1="W2FBI",
            callsign_field_2="N0CALL",
        )
        assert ecd.callsign_field_1 == "W2FBI"
        assert ecd.callsign_field_2 == "N0CALL"

    def test_to_bytes(self):
        """Test serialization."""
        ecd = MetaExtendedCallsign(
            callsign_field_1="W2FBI",
            callsign_field_2="N0CALL",
        )
        data = ecd.to_bytes()
        assert len(data) == 14

    def test_from_bytes_roundtrip(self):
        """Test serialization roundtrip."""
        original = MetaExtendedCallsign(
            callsign_field_1="W2FBI",
            callsign_field_2="K3ABC",
        )
        data = original.to_bytes()
        parsed = MetaExtendedCallsign.from_bytes(data)

        assert parsed.callsign_field_1 == "W2FBI"
        assert parsed.callsign_field_2 == "K3ABC"


class TestMetaNonce:
    """Test nonce META field for encryption."""

    def test_create(self):
        """Test creating nonce."""
        nonce = MetaNonce(
            timestamp=1704067200,  # 2024-01-01 00:00:00 UTC
            random_data=bytes(10),
        )
        assert nonce.timestamp == 1704067200

    def test_to_bytes(self):
        """Test serialization."""
        nonce = MetaNonce(
            timestamp=1704067200,
            random_data=b"0123456789",
        )
        data = nonce.to_bytes()
        assert len(data) == 14

    def test_from_bytes_roundtrip(self):
        """Test serialization roundtrip."""
        original = MetaNonce(
            timestamp=1704067200,
            random_data=b"0123456789",
        )
        data = original.to_bytes()
        parsed = MetaNonce.from_bytes(data)

        assert parsed.timestamp == original.timestamp
        assert parsed.random_data == original.random_data


class TestLSFMetaIntegration:
    """Test LSF with different META field types."""

    def test_set_position_meta(self):
        """Test setting position META in LSF."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="N0CALL"),
        )
        lsf.set_position_meta(
            latitude=40.7128,
            longitude=-74.0060,
            altitude=100.0,
        )
        pos = lsf.get_position_meta()
        assert abs(pos.latitude - 40.7128) < 0.001

    def test_set_extended_callsign_meta(self):
        """Test setting ECD META in LSF."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="N0CALL"),
        )
        lsf.set_extended_callsign_meta("TEST1", "TEST2")
        ecd = lsf.get_extended_callsign_meta()
        assert ecd.callsign_field_1 == "TEST1"

    def test_set_nonce_meta(self):
        """Test setting nonce META in LSF."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="N0CALL"),
        )
        lsf.set_nonce_meta(1704067200, b"0123456789")
        nonce = lsf.get_nonce_meta()
        assert nonce.timestamp == 1704067200
