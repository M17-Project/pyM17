"""Tests for M17 IP Frame module."""

import pytest

from m17.core.address import Address
from m17.core.constants import M17_MAGIC_NUMBER
from m17.frames.ip import IPFrame
from m17.frames.lsf import LinkSetupFrame
from m17.frames.stream import M17Payload


class TestIPFrameCreation:
    """Test IPFrame creation and validation."""

    def test_default_creation(self):
        """Test creating IPFrame with defaults."""
        frame = IPFrame()
        assert frame.magic_number == M17_MAGIC_NUMBER
        assert frame.stream_id == 0
        assert frame.lsf.dst.callsign == "@ALL"
        assert frame.lsf.src.callsign == "N0CALL"

    def test_custom_creation(self):
        """Test creating IPFrame with custom values."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="K3ABC"),
            type_field=0x0005,
        )
        payload = M17Payload(frame_number=42, payload=b"test payload!!!!!")
        frame = IPFrame(stream_id=0x1234, lsf=lsf, payload=payload)

        assert frame.stream_id == 0x1234
        assert frame.lsf.dst.callsign == "W2FBI"
        assert frame.lsf.src.callsign == "K3ABC"
        assert frame.payload.frame_number == 42

    def test_invalid_magic_number_length(self):
        """Test that invalid magic number length raises error."""
        with pytest.raises(ValueError, match="Magic number must be 4 bytes"):
            IPFrame(magic_number=b"M17")

        with pytest.raises(ValueError, match="Magic number must be 4 bytes"):
            IPFrame(magic_number=b"M17  ")

    def test_invalid_stream_id_negative(self):
        """Test that negative stream ID raises error."""
        with pytest.raises(ValueError, match="Stream ID must be 0-65535"):
            IPFrame(stream_id=-1)

    def test_invalid_stream_id_too_large(self):
        """Test that stream ID > 65535 raises error."""
        with pytest.raises(ValueError, match="Stream ID must be 0-65535"):
            IPFrame(stream_id=0x10000)

    def test_stream_id_boundaries(self):
        """Test stream ID at valid boundaries."""
        frame_zero = IPFrame(stream_id=0)
        assert frame_zero.stream_id == 0

        frame_max = IPFrame(stream_id=0xFFFF)
        assert frame_max.stream_id == 0xFFFF


class TestIPFrameProperties:
    """Test IPFrame properties."""

    def test_frame_number_property(self):
        """Test frame_number property."""
        payload = M17Payload(frame_number=0x123)
        frame = IPFrame(payload=payload)
        assert frame.frame_number == 0x123

    def test_is_last_frame_property(self):
        """Test is_last_frame property."""
        # Frame number with MSB set indicates last frame
        payload_normal = M17Payload(frame_number=0x0001)
        frame_normal = IPFrame(payload=payload_normal)
        assert not frame_normal.is_last_frame

        payload_last = M17Payload(frame_number=0x8001)
        frame_last = IPFrame(payload=payload_last)
        assert frame_last.is_last_frame

    def test_dst_property(self):
        """Test dst property."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="TEST1"),
            src=Address(callsign="TEST2"),
        )
        frame = IPFrame(lsf=lsf)
        assert frame.dst.callsign == "TEST1"

    def test_src_property(self):
        """Test src property."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="TEST1"),
            src=Address(callsign="TEST2"),
        )
        frame = IPFrame(lsf=lsf)
        assert frame.src.callsign == "TEST2"

    def test_stream_type_property(self):
        """Test stream_type property."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="TEST1"),
            src=Address(callsign="TEST2"),
            type_field=0x0007,
        )
        frame = IPFrame(lsf=lsf)
        assert frame.stream_type == 0x0007

    def test_lich_legacy_property(self):
        """Test legacy lich property returns lsf."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="N0CALL"),
        )
        frame = IPFrame(lsf=lsf)
        assert frame.lich is frame.lsf

    def test_m17_payload_legacy_property(self):
        """Test legacy m17_payload property returns payload."""
        payload = M17Payload(frame_number=99)
        frame = IPFrame(payload=payload)
        assert frame.m17_payload is frame.payload

    def test_nonce_property(self):
        """Test nonce property returns LSF meta."""
        meta = bytes([0x12, 0x34] + [0] * 12)
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="N0CALL"),
            meta=meta,
        )
        frame = IPFrame(lsf=lsf)
        assert frame.nonce == meta


class TestIPFrameSerialization:
    """Test IPFrame serialization and deserialization."""

    def test_to_bytes_length(self):
        """Test that to_bytes returns 54 bytes."""
        frame = IPFrame()
        data = frame.to_bytes()
        assert len(data) == 54

    def test_pack_method(self):
        """Test that pack is alias for to_bytes."""
        frame = IPFrame()
        assert frame.pack() == frame.to_bytes()

    def test_bytes_dunder(self):
        """Test __bytes__ method."""
        frame = IPFrame()
        assert bytes(frame) == frame.to_bytes()

    def test_roundtrip(self):
        """Test serialization roundtrip."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="SP5WWP"),
            src=Address(callsign="W2FBI"),
            type_field=0x0005,
            meta=bytes(14),
        )
        payload = M17Payload(frame_number=42, payload=bytes(16))
        original = IPFrame(stream_id=0xABCD, lsf=lsf, payload=payload)

        data = original.to_bytes()
        restored = IPFrame.from_bytes(data)

        assert original == restored
        assert restored.stream_id == 0xABCD
        assert restored.lsf.dst.callsign == "SP5WWP"
        assert restored.lsf.src.callsign == "W2FBI"
        assert restored.payload.frame_number == 42

    def test_from_bytes_wrong_size(self):
        """Test from_bytes with wrong size."""
        with pytest.raises(ValueError, match="IP frame must be 54 bytes"):
            IPFrame.from_bytes(bytes(53))

        with pytest.raises(ValueError, match="IP frame must be 54 bytes"):
            IPFrame.from_bytes(bytes(55))

    def test_from_bytes_invalid_magic(self):
        """Test from_bytes with invalid magic number."""
        # Create valid frame then corrupt magic
        frame = IPFrame()
        data = bytearray(frame.to_bytes())
        data[0:4] = b"XXXX"

        with pytest.raises(ValueError, match="Invalid magic number"):
            IPFrame.from_bytes(bytes(data))

    def test_unpack_method(self):
        """Test that unpack is alias for from_bytes."""
        frame = IPFrame()
        data = frame.to_bytes()
        assert IPFrame.unpack(data) == IPFrame.from_bytes(data)


class TestIPFrameCRC:
    """Test IPFrame CRC calculation."""

    def test_calculate_crc(self):
        """Test CRC calculation returns valid value."""
        frame = IPFrame()
        crc = frame.calculate_crc()
        assert isinstance(crc, int)
        assert 0 <= crc <= 0xFFFF

    def test_crc_changes_with_payload(self):
        """Test CRC changes when payload changes."""
        payload1 = M17Payload(frame_number=0, payload=bytes(16))
        payload2 = M17Payload(frame_number=0, payload=bytes([1] + [0] * 15))

        frame1 = IPFrame(payload=payload1)
        frame2 = IPFrame(payload=payload2)

        assert frame1.calculate_crc() != frame2.calculate_crc()

    def test_crc_changes_with_frame_number(self):
        """Test CRC changes when frame number changes."""
        payload1 = M17Payload(frame_number=0)
        payload2 = M17Payload(frame_number=1)

        frame1 = IPFrame(payload=payload1)
        frame2 = IPFrame(payload=payload2)

        assert frame1.calculate_crc() != frame2.calculate_crc()


class TestIPFrameIsM17:
    """Test is_m17 static method."""

    def test_is_m17_valid(self):
        """Test is_m17 with valid M17 data."""
        frame = IPFrame()
        data = frame.to_bytes()
        assert IPFrame.is_m17(data) is True

    def test_is_m17_just_magic(self):
        """Test is_m17 with just magic number."""
        assert IPFrame.is_m17(M17_MAGIC_NUMBER) is True

    def test_is_m17_invalid_magic(self):
        """Test is_m17 with invalid magic."""
        assert IPFrame.is_m17(b"XXXX" + bytes(50)) is False

    def test_is_m17_too_short(self):
        """Test is_m17 with data too short."""
        assert IPFrame.is_m17(b"M17") is False
        assert IPFrame.is_m17(b"") is False

    def test_is_m17_partial_magic(self):
        """Test is_m17 with partial magic."""
        assert IPFrame.is_m17(b"M17") is False


class TestIPFrameCreate:
    """Test IPFrame.create factory method."""

    def test_create_with_strings(self):
        """Test create with string callsigns."""
        frame = IPFrame.create(dst="W2FBI", src="K3ABC", stream_id=0x1234)
        assert frame.dst.callsign == "W2FBI"
        assert frame.src.callsign == "K3ABC"
        assert frame.stream_id == 0x1234

    def test_create_with_addresses(self):
        """Test create with Address objects."""
        dst = Address(callsign="W2FBI")
        src = Address(callsign="K3ABC")
        frame = IPFrame.create(dst=dst, src=src)
        assert frame.dst.callsign == "W2FBI"
        assert frame.src.callsign == "K3ABC"

    def test_create_random_stream_id(self):
        """Test create generates random stream_id if not specified."""
        frame = IPFrame.create(dst="W2FBI", src="K3ABC")
        assert 1 <= frame.stream_id <= 0xFFFF

    def test_create_with_stream_type(self):
        """Test create with custom stream type."""
        frame = IPFrame.create(dst="W2FBI", src="K3ABC", stream_type=0x000D)
        assert frame.stream_type == 0x000D

    def test_create_with_nonce_padding(self):
        """Test create pads short nonce to 14 bytes."""
        frame = IPFrame.create(dst="W2FBI", src="K3ABC", nonce=b"\x12\x34")
        assert len(frame.nonce) == 14
        assert frame.nonce[:2] == b"\x12\x34"
        assert frame.nonce[2:] == bytes(12)

    def test_create_with_nonce_truncation(self):
        """Test create truncates long nonce to 14 bytes."""
        long_nonce = bytes(range(20))
        frame = IPFrame.create(dst="W2FBI", src="K3ABC", nonce=long_nonce)
        assert len(frame.nonce) == 14
        assert frame.nonce == bytes(range(14))

    def test_create_with_payload_padding(self):
        """Test create pads short payload to 16 bytes."""
        frame = IPFrame.create(dst="W2FBI", src="K3ABC", payload=b"short")
        assert len(frame.payload.payload) == 16
        assert frame.payload.payload[:5] == b"short"

    def test_create_with_payload_truncation(self):
        """Test create truncates long payload to 16 bytes."""
        long_payload = bytes(range(20))
        frame = IPFrame.create(dst="W2FBI", src="K3ABC", payload=long_payload)
        assert len(frame.payload.payload) == 16
        assert frame.payload.payload == bytes(range(16))

    def test_create_with_frame_number(self):
        """Test create with custom frame number."""
        frame = IPFrame.create(dst="W2FBI", src="K3ABC", frame_number=100)
        assert frame.frame_number == 100


class TestIPFrameGetPackValues:
    """Test get_pack_values legacy method."""

    def test_get_pack_values_returns_list(self):
        """Test get_pack_values returns a list."""
        frame = IPFrame()
        values = frame.get_pack_values()
        assert isinstance(values, list)

    def test_get_pack_values_length(self):
        """Test get_pack_values returns correct number of elements."""
        frame = IPFrame()
        values = frame.get_pack_values()
        # 4 magic + 1 stream_id + 6 dst + 6 src + 1 type + 14 meta + 1 fn + 16 payload + 1 crc = 50
        assert len(values) == 50


class TestIPFrameStringRepresentation:
    """Test IPFrame string representations."""

    def test_str_format(self):
        """Test __str__ format."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="K3ABC"),
        )
        frame = IPFrame(stream_id=0x1234, lsf=lsf)
        s = str(frame)
        assert "IPFrame" in s
        assert "SID=1234" in s
        assert "K3ABC" in s
        assert "W2FBI" in s

    def test_repr_format(self):
        """Test __repr__ format."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="K3ABC"),
            type_field=0x0005,
        )
        frame = IPFrame(stream_id=0x1234, lsf=lsf)
        r = repr(frame)
        assert "IPFrame" in r
        assert "stream_id=0x1234" in r
        assert "src='K3ABC'" in r
        assert "dst='W2FBI'" in r
        assert "type=0x0005" in r


class TestIPFrameEquality:
    """Test IPFrame equality comparisons."""

    def test_equal_frames(self):
        """Test equality of identical frames."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="K3ABC"),
        )
        frame1 = IPFrame(stream_id=0x1234, lsf=lsf)
        frame2 = IPFrame(stream_id=0x1234, lsf=lsf)
        assert frame1 == frame2

    def test_unequal_frames(self):
        """Test inequality of different frames."""
        frame1 = IPFrame(stream_id=0x1234)
        frame2 = IPFrame(stream_id=0x5678)
        assert frame1 != frame2

    def test_equal_to_bytes(self):
        """Test equality comparison with bytes."""
        frame = IPFrame()
        data = bytes(frame)
        assert frame == data

    def test_not_equal_to_different_bytes(self):
        """Test inequality with different bytes."""
        frame = IPFrame()
        data = bytes(54)
        assert frame != data

    def test_not_equal_to_other_types(self):
        """Test comparison with non-IPFrame/bytes returns NotImplemented."""
        frame = IPFrame()
        assert (frame == "not a frame") is False
        assert (frame == 12345) is False


class TestIPFrameDictFromBytes:
    """Test dict_from_bytes static method."""

    def test_dict_from_bytes_keys(self):
        """Test dict_from_bytes returns expected keys."""
        frame = IPFrame.create(dst="W2FBI", src="K3ABC", stream_id=0x1234)
        data = frame.to_bytes()
        result = IPFrame.dict_from_bytes(data)

        assert "magic_number" in result
        assert "stream_id" in result
        assert "dst" in result
        assert "src" in result
        assert "stream_type" in result
        assert "nonce" in result
        assert "frame_number" in result
        assert "payload" in result
        assert "crc" in result

    def test_dict_from_bytes_values(self):
        """Test dict_from_bytes returns correct values."""
        lsf = LinkSetupFrame(
            dst=Address(callsign="W2FBI"),
            src=Address(callsign="K3ABC"),
            type_field=0x0005,
            meta=bytes(14),
        )
        payload = M17Payload(frame_number=42, payload=bytes(16))
        frame = IPFrame(stream_id=0xABCD, lsf=lsf, payload=payload)
        data = frame.to_bytes()
        result = IPFrame.dict_from_bytes(data)

        assert result["magic_number"] == M17_MAGIC_NUMBER
        assert result["stream_id"] == 0xABCD
        assert result["dst"].callsign == "W2FBI"
        assert result["src"].callsign == "K3ABC"
        assert result["stream_type"] == 0x0005
        assert result["frame_number"] == 42


class TestIPFrameIntegration:
    """Integration tests for IPFrame."""

    def test_full_workflow(self):
        """Test complete create-serialize-parse workflow."""
        # Create frame
        frame = IPFrame.create(
            dst="TESTDST",
            src="TESTSRC",
            stream_id=0xCAFE,
            stream_type=0x0005,
            nonce=b"\x01\x02\x03\x04",
            frame_number=100,
            payload=b"Hello M17 World!",
        )

        # Verify creation
        assert frame.dst.callsign == "TESTDST"
        assert frame.src.callsign == "TESTSRC"
        assert frame.stream_id == 0xCAFE

        # Serialize
        data = frame.to_bytes()
        assert len(data) == 54
        assert IPFrame.is_m17(data)

        # Parse
        parsed = IPFrame.from_bytes(data)
        assert parsed == frame
        assert parsed.dst.callsign == "TESTDST"
        assert parsed.src.callsign == "TESTSRC"
        assert parsed.stream_id == 0xCAFE
        assert parsed.frame_number == 100

    def test_multiple_frames_different_ids(self):
        """Test creating multiple frames with different stream IDs."""
        frames = [IPFrame.create(dst="W2FBI", src="K3ABC", stream_id=i) for i in range(1, 5)]

        for i, frame in enumerate(frames, 1):
            assert frame.stream_id == i
            data = frame.to_bytes()
            parsed = IPFrame.from_bytes(data)
            assert parsed.stream_id == i
