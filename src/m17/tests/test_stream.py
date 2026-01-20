"""Tests for M17 Stream Frame Definitions

Tests for M17Payload and StreamFrame classes.
"""

import pytest

from m17.frames.stream import M17Payload, StreamFrame


class TestM17Payload:
    """Tests for M17Payload class."""

    def test_default_construction(self):
        """Test default payload construction."""
        payload = M17Payload()
        assert payload.frame_number == 0
        assert len(payload.payload) == 16
        assert payload.payload == bytes(16)
        assert payload.crc == 0

    def test_construction_with_values(self):
        """Test payload construction with values."""
        data = bytes(range(16))
        payload = M17Payload(frame_number=0x1234, payload=data, crc=0xABCD)
        assert payload.frame_number == 0x1234
        assert payload.payload == data
        assert payload.crc == 0xABCD

    def test_payload_padding(self):
        """Test short payload is padded."""
        payload = M17Payload(payload=b"short")
        assert len(payload.payload) == 16
        assert payload.payload[:5] == b"short"
        assert payload.payload[5:] == bytes(11)

    def test_payload_truncation(self):
        """Test long payload is truncated."""
        payload = M17Payload(payload=bytes(20))
        assert len(payload.payload) == 16

    def test_frame_number_validation(self):
        """Test frame number must be 0-65535."""
        with pytest.raises(ValueError):
            M17Payload(frame_number=-1)

        with pytest.raises(ValueError):
            M17Payload(frame_number=0x10000)

    def test_is_last_frame(self):
        """Test EOT flag detection."""
        payload = M17Payload(frame_number=0x0000)
        assert not payload.is_last_frame

        payload = M17Payload(frame_number=0x8000)
        assert payload.is_last_frame

        payload = M17Payload(frame_number=0x8001)
        assert payload.is_last_frame

    def test_sequence_number(self):
        """Test sequence number extraction."""
        payload = M17Payload(frame_number=0x1234)
        assert payload.sequence_number == 0x1234

        payload = M17Payload(frame_number=0x8123)
        assert payload.sequence_number == 0x0123

    def test_set_last_frame(self):
        """Test setting EOT flag."""
        payload = M17Payload(frame_number=0x0001)
        assert not payload.is_last_frame

        payload.set_last_frame(True)
        assert payload.is_last_frame
        assert payload.frame_number == 0x8001

        payload.set_last_frame(False)
        assert not payload.is_last_frame
        assert payload.frame_number == 0x0001

    def test_calculate_crc(self):
        """Test CRC calculation."""
        lich_chunk = bytes(6)
        payload = M17Payload(frame_number=0x0001, payload=bytes(16))
        crc = payload.calculate_crc(lich_chunk)
        assert isinstance(crc, int)
        assert 0 <= crc <= 0xFFFF

    def test_to_bytes(self):
        """Test serialization to bytes."""
        payload = M17Payload(frame_number=0x1234, payload=bytes(16), crc=0xABCD)
        data = payload.to_bytes()
        assert len(data) == 20  # 2 + 16 + 2
        assert data[0:2] == b"\x12\x34"  # frame_number big-endian
        assert data[-2:] == b"\xAB\xCD"  # crc big-endian

    def test_to_bytes_without_crc(self):
        """Test serialization without CRC."""
        payload = M17Payload(frame_number=0x1234, payload=bytes(16))
        data = payload.to_bytes_without_crc()
        assert len(data) == 18  # 2 + 16

    def test_from_bytes_with_crc(self):
        """Test parsing from bytes with CRC."""
        original = M17Payload(frame_number=0x1234, payload=bytes(range(16)), crc=0xABCD)
        data = original.to_bytes()
        parsed = M17Payload.from_bytes(data, has_crc=True)
        assert parsed.frame_number == original.frame_number
        assert parsed.payload == original.payload
        assert parsed.crc == original.crc

    def test_from_bytes_without_crc(self):
        """Test parsing from bytes without CRC."""
        original = M17Payload(frame_number=0x1234, payload=bytes(range(16)))
        data = original.to_bytes_without_crc()
        parsed = M17Payload.from_bytes(data, has_crc=False)
        assert parsed.frame_number == original.frame_number
        assert parsed.payload == original.payload
        assert parsed.crc == 0

    def test_from_bytes_wrong_length(self):
        """Test parsing wrong length raises error."""
        with pytest.raises(ValueError, match="20 bytes"):
            M17Payload.from_bytes(bytes(19), has_crc=True)

        with pytest.raises(ValueError, match="18 bytes"):
            M17Payload.from_bytes(bytes(19), has_crc=False)

    def test_equality(self):
        """Test payload equality comparison."""
        p1 = M17Payload(frame_number=0x1234, payload=bytes(16))
        p2 = M17Payload(frame_number=0x1234, payload=bytes(16))
        p3 = M17Payload(frame_number=0x5678, payload=bytes(16))

        assert p1 == p2
        assert p1 != p3

    def test_bytes_equality(self):
        """Test equality with bytes."""
        payload = M17Payload(frame_number=0x1234, payload=bytes(16), crc=0xABCD)
        assert payload == payload.to_bytes()

    def test_str_representation(self):
        """Test string representation."""
        payload = M17Payload(frame_number=0x0001, payload=bytes(16))
        s = str(payload)
        assert "1" in s  # sequence number
        assert "EOT" not in s

        payload.set_last_frame(True)
        s = str(payload)
        assert "EOT" in s


class TestStreamFrame:
    """Tests for StreamFrame class."""

    def test_default_construction(self):
        """Test default frame construction."""
        frame = StreamFrame()
        assert len(frame.lich_chunk) == 6
        assert frame.lich_chunk == bytes(6)
        assert isinstance(frame.payload, M17Payload)

    def test_construction_with_values(self):
        """Test frame construction with values."""
        lich = bytes(range(6))
        payload = M17Payload(frame_number=0x1234, payload=bytes(16))
        frame = StreamFrame(lich_chunk=lich, payload=payload)
        assert frame.lich_chunk == lich
        assert frame.payload == payload

    def test_lich_chunk_padding(self):
        """Test short LICH chunk is padded."""
        frame = StreamFrame(lich_chunk=b"abc")
        assert len(frame.lich_chunk) == 6
        assert frame.lich_chunk[:3] == b"abc"

    def test_lich_chunk_truncation(self):
        """Test long LICH chunk is truncated."""
        frame = StreamFrame(lich_chunk=bytes(10))
        assert len(frame.lich_chunk) == 6

    def test_frame_number_property(self):
        """Test frame_number property."""
        payload = M17Payload(frame_number=0x5678)
        frame = StreamFrame(payload=payload)
        assert frame.frame_number == 0x5678

    def test_is_last_frame_property(self):
        """Test is_last_frame property."""
        payload = M17Payload(frame_number=0x8000)
        frame = StreamFrame(payload=payload)
        assert frame.is_last_frame

    def test_calculate_crc(self):
        """Test CRC calculation."""
        frame = StreamFrame()
        crc = frame.calculate_crc()
        assert isinstance(crc, int)
        assert 0 <= crc <= 0xFFFF

    def test_to_bytes(self):
        """Test serialization to bytes."""
        frame = StreamFrame()
        data = frame.to_bytes()
        assert len(data) == 26  # 6 + 2 + 16 + 2

    def test_from_bytes(self):
        """Test parsing from bytes."""
        original = StreamFrame(
            lich_chunk=bytes(range(6)),
            payload=M17Payload(frame_number=0x1234, payload=bytes(range(16))),
        )
        data = original.to_bytes()
        parsed = StreamFrame.from_bytes(data)
        assert parsed.lich_chunk == original.lich_chunk
        assert parsed.payload.frame_number == original.payload.frame_number
        assert parsed.payload.payload == original.payload.payload

    def test_from_bytes_wrong_length(self):
        """Test parsing wrong length raises error."""
        with pytest.raises(ValueError, match="26 bytes"):
            StreamFrame.from_bytes(bytes(25))

    def test_from_bytes_legacy(self):
        """Test parsing legacy format (18 bytes)."""
        # Create 18-byte legacy frame
        legacy_data = bytes(6) + b"\x12\x34" + bytes(10)
        frame = StreamFrame.from_bytes_legacy(legacy_data)
        assert len(frame.lich_chunk) == 6
        assert frame.payload.frame_number == 0x1234

    def test_from_bytes_legacy_wrong_length(self):
        """Test parsing wrong legacy length raises error."""
        with pytest.raises(ValueError, match="18 bytes"):
            StreamFrame.from_bytes_legacy(bytes(20))

    def test_equality(self):
        """Test frame equality comparison."""
        f1 = StreamFrame(lich_chunk=bytes(6), payload=M17Payload(frame_number=0x1234))
        f2 = StreamFrame(lich_chunk=bytes(6), payload=M17Payload(frame_number=0x1234))
        f3 = StreamFrame(lich_chunk=bytes(6), payload=M17Payload(frame_number=0x5678))

        assert f1 == f2
        assert f1 != f3

    def test_bytes_equality(self):
        """Test equality with bytes."""
        frame = StreamFrame()
        assert frame == frame.to_bytes()

    def test_str_representation(self):
        """Test string representation."""
        frame = StreamFrame()
        s = str(frame)
        assert "StreamFrame" in s
        assert "lich=" in s


class TestStreamFrameRoundtrip:
    """Integration tests for stream frame roundtrip."""

    def test_full_roundtrip(self):
        """Test complete serialize/deserialize roundtrip."""
        original = StreamFrame(
            lich_chunk=bytes([0x11, 0x22, 0x33, 0x44, 0x55, 0x66]),
            payload=M17Payload(
                frame_number=0x1234,
                payload=bytes([0xAA] * 16),
            ),
        )

        # Serialize
        data = original.to_bytes()

        # Deserialize
        parsed = StreamFrame.from_bytes(data)

        # Compare
        assert parsed.lich_chunk == original.lich_chunk
        assert parsed.payload.frame_number == original.payload.frame_number
        assert parsed.payload.payload == original.payload.payload

    def test_eot_frame_roundtrip(self):
        """Test EOT frame roundtrip."""
        original = StreamFrame(
            payload=M17Payload(frame_number=0x8000),  # EOT flag set
        )

        data = original.to_bytes()
        parsed = StreamFrame.from_bytes(data)

        assert parsed.is_last_frame
        assert parsed.payload.is_last_frame
