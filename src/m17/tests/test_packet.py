"""Tests for M17 Packet Frame module."""

import pytest

from m17.core.constants import PACKET_PROTOCOL_TLE
from m17.frames.packet import PacketChunk, PacketFrame, PacketProtocol, TLEPacket


class TestPacketChunkCreation:
    """Test PacketChunk creation and validation."""

    def test_default_creation(self):
        """Test creating PacketChunk with defaults."""
        chunk = PacketChunk()
        assert len(chunk.data) == 25
        assert chunk.is_last is False
        assert chunk.byte_count == 25

    def test_custom_creation(self):
        """Test creating PacketChunk with custom values."""
        data = bytes(range(25))
        chunk = PacketChunk(data=data, is_last=True, byte_count=20)
        assert chunk.data == data
        assert chunk.is_last is True
        assert chunk.byte_count == 20

    def test_invalid_byte_count_negative(self):
        """Test that negative byte count raises error."""
        with pytest.raises(ValueError, match="Byte count must be 0-25"):
            PacketChunk(byte_count=-1)

    def test_invalid_byte_count_too_large(self):
        """Test that byte count > 25 raises error."""
        with pytest.raises(ValueError, match="Byte count must be 0-25"):
            PacketChunk(byte_count=26)

    def test_byte_count_boundaries(self):
        """Test byte count at valid boundaries."""
        chunk_zero = PacketChunk(byte_count=0, is_last=True)
        assert chunk_zero.byte_count == 0

        chunk_max = PacketChunk(byte_count=25)
        assert chunk_max.byte_count == 25

    def test_data_padding(self):
        """Test short data is padded to 25 bytes."""
        chunk = PacketChunk(data=b"short")
        assert len(chunk.data) == 25
        assert chunk.data[:5] == b"short"
        assert chunk.data[5:] == bytes(20)

    def test_data_truncation(self):
        """Test long data is truncated to 25 bytes."""
        long_data = bytes(range(30))
        chunk = PacketChunk(data=long_data)
        assert len(chunk.data) == 25
        assert chunk.data == bytes(range(25))


class TestPacketChunkControlByte:
    """Test PacketChunk control byte calculations."""

    def test_control_byte_not_last(self):
        """Test control byte for non-last chunk."""
        chunk = PacketChunk(is_last=False, byte_count=25)
        # EOP=0, BC=25 (0x19), reserved=0
        # 0x00 | (25 << 2) = 0x64
        assert chunk.control_byte == 0x64

    def test_control_byte_last(self):
        """Test control byte for last chunk."""
        chunk = PacketChunk(is_last=True, byte_count=25)
        # EOP=1 (0x80), BC=25 (0x19 << 2 = 0x64)
        # 0x80 | 0x64 = 0xE4
        assert chunk.control_byte == 0xE4

    def test_control_byte_last_partial(self):
        """Test control byte for last chunk with partial data."""
        chunk = PacketChunk(is_last=True, byte_count=10)
        # EOP=1 (0x80), BC=10 (0x0A << 2 = 0x28)
        # 0x80 | 0x28 = 0xA8
        assert chunk.control_byte == 0xA8

    def test_control_byte_zero_bytes(self):
        """Test control byte for empty last chunk."""
        chunk = PacketChunk(is_last=True, byte_count=0)
        # EOP=1 (0x80), BC=0
        assert chunk.control_byte == 0x80


class TestPacketChunkValidData:
    """Test PacketChunk valid_data property."""

    def test_valid_data_full_chunk(self):
        """Test valid_data for full non-last chunk."""
        data = bytes(range(25))
        chunk = PacketChunk(data=data, is_last=False, byte_count=25)
        assert chunk.valid_data == data

    def test_valid_data_last_full(self):
        """Test valid_data for full last chunk."""
        data = bytes(range(25))
        chunk = PacketChunk(data=data, is_last=True, byte_count=25)
        assert chunk.valid_data == data

    def test_valid_data_last_partial(self):
        """Test valid_data for partial last chunk."""
        data = b"Hello World" + bytes(14)
        chunk = PacketChunk(data=data, is_last=True, byte_count=11)
        assert chunk.valid_data == b"Hello World"

    def test_valid_data_empty(self):
        """Test valid_data for empty last chunk."""
        chunk = PacketChunk(is_last=True, byte_count=0)
        assert chunk.valid_data == b""


class TestPacketChunkSerialization:
    """Test PacketChunk serialization."""

    def test_to_bytes_length(self):
        """Test that to_bytes returns 26 bytes."""
        chunk = PacketChunk()
        assert len(chunk.to_bytes()) == 26

    def test_bytes_dunder(self):
        """Test __bytes__ method."""
        chunk = PacketChunk()
        assert bytes(chunk) == chunk.to_bytes()

    def test_roundtrip(self):
        """Test serialization roundtrip."""
        original = PacketChunk(data=bytes(range(25)), is_last=True, byte_count=15)
        data = original.to_bytes()
        restored = PacketChunk.from_bytes(data)

        assert restored.data == original.data
        assert restored.is_last == original.is_last
        assert restored.byte_count == original.byte_count

    def test_from_bytes_wrong_size(self):
        """Test from_bytes with wrong size."""
        with pytest.raises(ValueError, match="Chunk must be 26 bytes"):
            PacketChunk.from_bytes(bytes(25))

        with pytest.raises(ValueError, match="Chunk must be 26 bytes"):
            PacketChunk.from_bytes(bytes(27))


class TestPacketChunkStr:
    """Test PacketChunk string representation."""

    def test_str_normal_chunk(self):
        """Test __str__ for normal chunk."""
        chunk = PacketChunk(data=b"TEST" + bytes(21), is_last=False, byte_count=25)
        s = str(chunk)
        assert "PacketChunk" in s
        assert "[25]" in s
        assert "LAST" not in s

    def test_str_last_chunk(self):
        """Test __str__ for last chunk."""
        chunk = PacketChunk(data=b"TEST" + bytes(21), is_last=True, byte_count=4)
        s = str(chunk)
        assert "PacketChunk" in s
        assert "[4]" in s
        assert "[LAST]" in s


class TestPacketFrameCreation:
    """Test PacketFrame creation."""

    def test_default_creation(self):
        """Test creating empty PacketFrame."""
        frame = PacketFrame()
        assert frame.chunks == []

    def test_from_data_small(self):
        """Test from_data with small data."""
        data = b"Hello M17"
        frame = PacketFrame.from_data(data)
        assert len(frame.chunks) == 1
        assert frame.chunks[0].is_last is True
        assert frame.chunks[0].byte_count == 9

    def test_from_data_exact_25(self):
        """Test from_data with exactly 25 bytes."""
        data = bytes(25)
        frame = PacketFrame.from_data(data)
        assert len(frame.chunks) == 1
        assert frame.chunks[0].is_last is True
        assert frame.chunks[0].byte_count == 25

    def test_from_data_multiple_chunks(self):
        """Test from_data with data requiring multiple chunks."""
        data = bytes(60)  # 25 + 25 + 10
        frame = PacketFrame.from_data(data)
        assert len(frame.chunks) == 3
        assert frame.chunks[0].is_last is False
        assert frame.chunks[1].is_last is False
        assert frame.chunks[2].is_last is True
        assert frame.chunks[2].byte_count == 10

    def test_from_data_empty(self):
        """Test from_data with empty data."""
        frame = PacketFrame.from_data(b"")
        assert len(frame.chunks) == 1
        assert frame.chunks[0].is_last is True
        assert frame.chunks[0].byte_count == 0


class TestPacketFrameGetData:
    """Test PacketFrame get_data method."""

    def test_get_data_single_chunk(self):
        """Test get_data with single chunk."""
        data = b"Test message"
        frame = PacketFrame.from_data(data)
        assert frame.get_data() == data

    def test_get_data_multiple_chunks(self):
        """Test get_data with multiple chunks."""
        data = bytes(range(60))
        frame = PacketFrame.from_data(data)
        assert frame.get_data() == data

    def test_get_data_empty(self):
        """Test get_data with empty frame."""
        frame = PacketFrame.from_data(b"")
        assert frame.get_data() == b""


class TestPacketFrameProperties:
    """Test PacketFrame properties."""

    def test_total_chunks(self):
        """Test total_chunks property."""
        frame = PacketFrame.from_data(bytes(60))
        assert frame.total_chunks == 3

    def test_total_bytes(self):
        """Test total_bytes property."""
        data = bytes(60)
        frame = PacketFrame.from_data(data)
        assert frame.total_bytes == 60

    def test_calculate_crc(self):
        """Test calculate_crc method."""
        frame = PacketFrame.from_data(b"Test CRC data")
        crc = frame.calculate_crc()
        assert isinstance(crc, int)
        assert 0 <= crc <= 0xFFFF


class TestPacketFrameMethods:
    """Test PacketFrame methods."""

    def test_to_bytes_list(self):
        """Test to_bytes_list method."""
        frame = PacketFrame.from_data(bytes(60))
        chunks = frame.to_bytes_list()
        assert len(chunks) == 3
        for chunk in chunks:
            assert len(chunk) == 26

    def test_str(self):
        """Test __str__ method."""
        frame = PacketFrame.from_data(bytes(60))
        s = str(frame)
        assert "PacketFrame" in s
        assert "3 chunks" in s
        assert "60 bytes" in s

    def test_iter(self):
        """Test __iter__ method."""
        frame = PacketFrame.from_data(bytes(60))
        chunks = list(frame)
        assert len(chunks) == 3
        for chunk in chunks:
            assert isinstance(chunk, PacketChunk)

    def test_len(self):
        """Test __len__ method."""
        frame = PacketFrame.from_data(bytes(60))
        assert len(frame) == 3

    def test_getitem(self):
        """Test __getitem__ method."""
        data = bytes(60)
        frame = PacketFrame.from_data(data)
        assert isinstance(frame[0], PacketChunk)
        assert isinstance(frame[1], PacketChunk)
        assert isinstance(frame[2], PacketChunk)
        assert frame[2].is_last is True


class TestPacketProtocolEnum:
    """Test PacketProtocol enum."""

    def test_protocol_values(self):
        """Test protocol enumeration values."""
        assert PacketProtocol.RAW == 0x00
        assert PacketProtocol.AX25 == 0x01
        assert PacketProtocol.APRS == 0x02
        assert PacketProtocol.LOWPAN_6 == 0x03
        assert PacketProtocol.IPV4 == 0x04
        assert PacketProtocol.SMS == 0x05
        assert PacketProtocol.WINLINK == 0x06
        assert PacketProtocol.TLE == 0x07


class TestTLEPacketCreation:
    """Test TLEPacket creation and validation."""

    ISS_NAME = "ISS (ZARYA)"
    ISS_LINE1 = "1 25544U 98067A   21275.52043534  .00006000  00000-0  11756-3 0  9991"
    ISS_LINE2 = "2 25544  51.6442 123.4567 0003656  35.8621  55.5028 15.48966391305169"

    def test_default_creation(self):
        """Test creating empty TLEPacket."""
        tle = TLEPacket()
        assert tle.satellite_name == ""
        assert tle.tle_line1 == ""
        assert tle.tle_line2 == ""

    def test_full_creation(self):
        """Test creating complete TLEPacket."""
        tle = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1=self.ISS_LINE1,
            tle_line2=self.ISS_LINE2,
        )
        assert tle.satellite_name == self.ISS_NAME
        assert tle.tle_line1 == self.ISS_LINE1
        assert tle.tle_line2 == self.ISS_LINE2


class TestTLEPacketIsValid:
    """Test TLEPacket is_valid property."""

    ISS_NAME = "ISS (ZARYA)"
    ISS_LINE1 = "1 25544U 98067A   21275.52043534  .00006000  00000-0  11756-3 0  9991"
    ISS_LINE2 = "2 25544  51.6442 123.4567 0003656  35.8621  55.5028 15.48966391305169"

    def test_is_valid_complete(self):
        """Test is_valid for complete TLE."""
        tle = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1=self.ISS_LINE1,
            tle_line2=self.ISS_LINE2,
        )
        assert tle.is_valid is True

    def test_is_valid_empty_line1(self):
        """Test is_valid with empty line1."""
        tle = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1="",
            tle_line2=self.ISS_LINE2,
        )
        assert tle.is_valid is False

    def test_is_valid_empty_line2(self):
        """Test is_valid with empty line2."""
        tle = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1=self.ISS_LINE1,
            tle_line2="",
        )
        assert tle.is_valid is False

    def test_is_valid_wrong_line1_length(self):
        """Test is_valid with wrong line1 length."""
        tle = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1="1 25544 short line",
            tle_line2=self.ISS_LINE2,
        )
        assert tle.is_valid is False

    def test_is_valid_wrong_line2_length(self):
        """Test is_valid with wrong line2 length."""
        tle = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1=self.ISS_LINE1,
            tle_line2="2 25544 short line",
        )
        assert tle.is_valid is False

    def test_is_valid_wrong_line1_prefix(self):
        """Test is_valid with wrong line1 prefix."""
        # Create line with correct length but wrong prefix
        wrong_line1 = "X " + "0" * 67
        tle = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1=wrong_line1,
            tle_line2=self.ISS_LINE2,
        )
        assert tle.is_valid is False

    def test_is_valid_wrong_line2_prefix(self):
        """Test is_valid with wrong line2 prefix."""
        # Create line with correct length but wrong prefix
        wrong_line2 = "X " + "0" * 67
        tle = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1=self.ISS_LINE1,
            tle_line2=wrong_line2,
        )
        assert tle.is_valid is False


class TestTLEPacketSerialization:
    """Test TLEPacket serialization."""

    ISS_NAME = "ISS (ZARYA)"
    ISS_LINE1 = "1 25544U 98067A   21275.52043534  .00006000  00000-0  11756-3 0  9991"
    ISS_LINE2 = "2 25544  51.6442 123.4567 0003656  35.8621  55.5028 15.48966391305169"

    def test_to_bytes_structure(self):
        """Test to_bytes returns proper structure."""
        tle = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1=self.ISS_LINE1,
            tle_line2=self.ISS_LINE2,
        )
        data = tle.to_bytes()

        # First byte is protocol ID
        assert data[0] == PACKET_PROTOCOL_TLE

        # Second to last byte before CRC is null terminator
        assert data[-3] == 0x00

        # Last two bytes are CRC
        assert len(data[-2:]) == 2

    def test_roundtrip(self):
        """Test serialization roundtrip."""
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


class TestTLEPacketFromBytesErrors:
    """Test TLEPacket from_bytes error handling."""

    def test_from_bytes_too_short(self):
        """Test from_bytes with data too short."""
        with pytest.raises(ValueError, match="TLE packet too short"):
            TLEPacket.from_bytes(bytes(3))

    def test_from_bytes_wrong_protocol(self):
        """Test from_bytes with wrong protocol ID."""
        # Create minimal packet with wrong protocol
        data = bytes([0xFF, 0x00]) + bytes(2)  # Wrong protocol + null + CRC
        with pytest.raises(ValueError, match="Invalid protocol ID"):
            TLEPacket.from_bytes(data)

    def test_from_bytes_crc_mismatch(self):
        """Test from_bytes with corrupted CRC."""
        tle = TLEPacket(
            satellite_name="TEST",
            tle_line1="1 " + "0" * 67,
            tle_line2="2 " + "0" * 67,
        )
        data = bytearray(tle.to_bytes())
        # Corrupt CRC
        data[-1] ^= 0xFF
        with pytest.raises(ValueError, match="CRC mismatch"):
            TLEPacket.from_bytes(bytes(data))


class TestTLEPacketFromBytesUnicode:
    """Test TLEPacket from_bytes with non-ASCII data."""

    def test_from_bytes_with_non_ascii(self):
        """Test parsing TLE with non-ASCII characters."""
        # Create a valid TLE then manually corrupt it with non-ASCII
        from m17.core.crc import crc_m17

        # Build packet with non-ASCII character
        tle_text = "SAT\xffNAME\n1 " + "0" * 67 + "\n2 " + "0" * 67
        tle_bytes = tle_text.encode("latin-1")
        packet_data = bytes([PACKET_PROTOCOL_TLE]) + tle_bytes + b"\x00"
        crc = crc_m17(packet_data)
        full_packet = packet_data + crc.to_bytes(2, "big")

        # Should handle non-ASCII gracefully
        tle = TLEPacket.from_bytes(full_packet)
        # Will have replacement character
        assert "SAT" in tle.satellite_name


class TestTLEPacketPacketFrame:
    """Test TLEPacket to/from PacketFrame conversion."""

    ISS_NAME = "ISS (ZARYA)"
    ISS_LINE1 = "1 25544U 98067A   21275.52043534  .00006000  00000-0  11756-3 0  9991"
    ISS_LINE2 = "2 25544  51.6442 123.4567 0003656  35.8621  55.5028 15.48966391305169"

    def test_to_packet_frame(self):
        """Test converting TLE to PacketFrame."""
        tle = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1=self.ISS_LINE1,
            tle_line2=self.ISS_LINE2,
        )
        frame = tle.to_packet_frame()

        assert isinstance(frame, PacketFrame)
        assert len(frame) > 0

    def test_from_packet_frame(self):
        """Test parsing TLE from PacketFrame."""
        original = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1=self.ISS_LINE1,
            tle_line2=self.ISS_LINE2,
        )
        frame = original.to_packet_frame()
        parsed = TLEPacket.from_packet_frame(frame)

        assert parsed.satellite_name == original.satellite_name
        assert parsed.tle_line1 == original.tle_line1
        assert parsed.tle_line2 == original.tle_line2


class TestTLEPacketStr:
    """Test TLEPacket string representation."""

    ISS_NAME = "ISS (ZARYA)"
    ISS_LINE1 = "1 25544U 98067A   21275.52043534  .00006000  00000-0  11756-3 0  9991"
    ISS_LINE2 = "2 25544  51.6442 123.4567 0003656  35.8621  55.5028 15.48966391305169"

    def test_str_valid(self):
        """Test __str__ for valid TLE."""
        tle = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1=self.ISS_LINE1,
            tle_line2=self.ISS_LINE2,
        )
        s = str(tle)
        assert "TLEPacket" in s
        assert self.ISS_NAME in s
        assert "valid" in s

    def test_str_invalid(self):
        """Test __str__ for invalid TLE."""
        tle = TLEPacket(satellite_name="TEST")
        s = str(tle)
        assert "TLEPacket" in s
        assert "invalid" in s

    def test_to_tle_string(self):
        """Test to_tle_string method."""
        tle = TLEPacket(
            satellite_name=self.ISS_NAME,
            tle_line1=self.ISS_LINE1,
            tle_line2=self.ISS_LINE2,
        )
        output = tle.to_tle_string()
        lines = output.split("\n")
        assert len(lines) == 3
        assert lines[0] == self.ISS_NAME
        assert lines[1] == self.ISS_LINE1
        assert lines[2] == self.ISS_LINE2


class TestTLEPacketWarnings:
    """Test TLEPacket warning logging."""

    def test_warning_on_short_line1(self, caplog):
        """Test warning when line1 has non-standard length."""
        import logging

        with caplog.at_level(logging.WARNING):
            TLEPacket(
                satellite_name="TEST",
                tle_line1="1 short",
                tle_line2="2 " + "0" * 67,
            )
        assert "non-standard length" in caplog.text

    def test_warning_on_short_line2(self, caplog):
        """Test warning when line2 has non-standard length."""
        import logging

        with caplog.at_level(logging.WARNING):
            TLEPacket(
                satellite_name="TEST",
                tle_line1="1 " + "0" * 67,
                tle_line2="2 short",
            )
        assert "non-standard length" in caplog.text


class TestPacketFrameIntegration:
    """Integration tests for packet handling."""

    def test_large_data_chunking(self):
        """Test chunking of large data."""
        data = bytes(range(256)) * 10  # 2560 bytes
        frame = PacketFrame.from_data(data)

        # Should create ceil(2560/25) = 103 chunks
        assert len(frame) == 103

        # Last chunk should have 2560 % 25 = 10 bytes
        assert frame[-1].is_last is True
        assert frame[-1].byte_count == 10

        # Reassembled data should match
        assert frame.get_data() == data

    def test_exactly_divisible_data(self):
        """Test data that divides evenly into chunks."""
        data = bytes(75)  # Exactly 3 chunks of 25
        frame = PacketFrame.from_data(data)

        assert len(frame) == 3
        assert frame[-1].is_last is True
        assert frame[-1].byte_count == 25
        assert frame.get_data() == data
