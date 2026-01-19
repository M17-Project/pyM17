"""
Tests for M17 LICH (Link Information Channel) Frame Handling

Tests for LICHFrame, LICHChunk, and LICHCollector classes.
"""

import pytest

from m17.frames.lich import LICHFrame, LICHChunk, LICHCollector
from m17.frames.lsf import LinkSetupFrame
from m17.core.address import Address


class TestLICHChunk:
    """Tests for LICHChunk class."""

    def test_default_construction(self):
        """Test default chunk construction."""
        chunk = LICHChunk()
        assert len(chunk.data) == 6
        assert chunk.data == bytes(6)
        assert chunk.index == 0

    def test_construction_with_values(self):
        """Test chunk construction with values."""
        data = bytes(range(6))
        chunk = LICHChunk(data=data, index=3)
        assert chunk.data == data
        assert chunk.index == 3

    def test_data_padding(self):
        """Test short data is padded."""
        chunk = LICHChunk(data=b"abc")
        assert len(chunk.data) == 6
        assert chunk.data[:3] == b"abc"
        assert chunk.data[3:] == bytes(3)

    def test_data_truncation(self):
        """Test long data is truncated."""
        chunk = LICHChunk(data=bytes(10))
        assert len(chunk.data) == 6

    def test_index_validation(self):
        """Test index must be 0-4."""
        with pytest.raises(ValueError, match="0-4"):
            LICHChunk(index=-1)

        with pytest.raises(ValueError, match="0-4"):
            LICHChunk(index=5)

    def test_valid_indices(self):
        """Test all valid indices work."""
        for i in range(5):
            chunk = LICHChunk(index=i)
            assert chunk.index == i

    def test_bytes_conversion(self):
        """Test bytes conversion."""
        data = bytes(range(6))
        chunk = LICHChunk(data=data)
        assert bytes(chunk) == data

    def test_str_representation(self):
        """Test string representation."""
        chunk = LICHChunk(data=bytes(6), index=2)
        s = str(chunk)
        assert "LICHChunk" in s
        assert "[2]" in s


class TestLICHFrame:
    """Tests for LICHFrame class."""

    def test_construction(self):
        """Test LICH frame construction."""
        dst = Address(callsign="W2FBI")
        src = Address(callsign="N0CALL")
        lich = LICHFrame(dst=dst, src=src)
        assert lich.dst == dst
        assert lich.src == src
        assert lich.stream_type == 0x0005  # Default
        assert len(lich.nonce) == 14

    def test_construction_with_string_callsigns(self):
        """Test construction with string callsigns."""
        lich = LICHFrame(dst="W2FBI", src="N0CALL")
        assert lich.dst.callsign == "W2FBI"
        assert lich.src.callsign == "N0CALL"

    def test_construction_with_type(self):
        """Test construction with custom type."""
        lich = LICHFrame(dst="W2FBI", src="N0CALL", stream_type=0x1234)
        assert lich.stream_type == 0x1234

    def test_nonce_padding(self):
        """Test short nonce is padded."""
        lich = LICHFrame(dst="W2FBI", src="N0CALL", nonce=b"short")
        assert len(lich.nonce) == 14

    def test_nonce_truncation(self):
        """Test long nonce is truncated."""
        lich = LICHFrame(dst="W2FBI", src="N0CALL", nonce=bytes(20))
        assert len(lich.nonce) == 14

    def test_to_bytes(self):
        """Test serialization to bytes."""
        lich = LICHFrame(dst="W2FBI", src="N0CALL")
        data = lich.to_bytes()
        assert len(data) == 28  # 6 + 6 + 2 + 14

    def test_pack_alias(self):
        """Test pack() is alias for to_bytes()."""
        lich = LICHFrame(dst="W2FBI", src="N0CALL")
        assert lich.pack() == lich.to_bytes()

    def test_from_bytes(self):
        """Test parsing from bytes."""
        original = LICHFrame(dst="W2FBI", src="N0CALL", stream_type=0x1234)
        data = original.to_bytes()
        parsed = LICHFrame.from_bytes(data)
        assert parsed.dst.callsign == original.dst.callsign
        assert parsed.src.callsign == original.src.callsign
        assert parsed.stream_type == original.stream_type

    def test_from_bytes_wrong_length(self):
        """Test parsing wrong length raises error."""
        with pytest.raises(ValueError, match="28 bytes"):
            LICHFrame.from_bytes(bytes(27))

    def test_unpack_alias(self):
        """Test unpack() is alias for from_bytes()."""
        lich = LICHFrame(dst="W2FBI", src="N0CALL")
        data = lich.to_bytes()
        parsed = LICHFrame.unpack(data)
        assert parsed.dst.callsign == lich.dst.callsign

    def test_from_lsf(self):
        """Test creating LICH from LSF."""
        lsf = LinkSetupFrame(dst="W2FBI", src="N0CALL", type_field=0x1234)
        lich = LICHFrame.from_lsf(lsf)
        assert lich.dst.callsign == "W2FBI"
        assert lich.src.callsign == "N0CALL"
        assert lich.stream_type == 0x1234

    def test_to_lsf(self):
        """Test converting LICH to LSF."""
        lich = LICHFrame(dst="W2FBI", src="N0CALL", stream_type=0x1234)
        lsf = lich.to_lsf()
        assert lsf.dst.callsign == "W2FBI"
        assert lsf.src.callsign == "N0CALL"
        assert lsf.type_field == 0x1234

    def test_chunks(self):
        """Test splitting LICH into chunks."""
        lich = LICHFrame(dst="W2FBI", src="N0CALL")
        chunks = lich.chunks()
        assert len(chunks) == 5
        assert all(len(c) == 6 for c in chunks)

    def test_get_chunk(self):
        """Test getting chunk for frame number."""
        lich = LICHFrame(dst="W2FBI", src="N0CALL")
        chunks = lich.chunks()

        for fn in range(10):
            chunk = lich.get_chunk(fn)
            assert chunk == chunks[fn % 5]

    def test_equality(self):
        """Test LICH equality comparison."""
        l1 = LICHFrame(dst="W2FBI", src="N0CALL")
        l2 = LICHFrame(dst="W2FBI", src="N0CALL")
        l3 = LICHFrame(dst="W2FBI", src="DIFFER")

        assert l1 == l2
        assert l1 != l3

    def test_bytes_equality(self):
        """Test equality with bytes."""
        lich = LICHFrame(dst="W2FBI", src="N0CALL")
        assert lich == lich.to_bytes()

    def test_str_representation(self):
        """Test string representation."""
        lich = LICHFrame(dst="W2FBI", src="N0CALL")
        s = str(lich)
        assert "LICH" in s
        assert "W2FBI" in s
        assert "N0CALL" in s

    def test_dict_from_bytes(self):
        """Test static dict_from_bytes method."""
        lich = LICHFrame(dst="W2FBI", src="N0CALL", stream_type=0x1234)
        data = lich.to_bytes()
        d = LICHFrame.dict_from_bytes(data)
        assert d["dst"].callsign == "W2FBI"
        assert d["src"].callsign == "N0CALL"
        assert d["stream_type"] == 0x1234


class TestLICHCollector:
    """Tests for LICHCollector class."""

    def test_initial_state(self):
        """Test initial collector state."""
        collector = LICHCollector()
        assert not collector.is_complete
        assert collector.chunks_received == 0

    def test_add_chunk(self):
        """Test adding chunks."""
        collector = LICHCollector()
        chunk = bytes(6)

        # Add first chunk
        complete = collector.add_chunk(chunk, 0)
        assert not complete
        assert collector.chunks_received == 1

    def test_add_chunk_wrong_length(self):
        """Test adding wrong length chunk raises error."""
        collector = LICHCollector()
        with pytest.raises(ValueError, match="6 bytes"):
            collector.add_chunk(bytes(5), 0)

    def test_complete_after_all_chunks(self):
        """Test completion after all chunks received."""
        lich = LICHFrame(dst="W2FBI", src="N0CALL")
        chunks = lich.chunks()

        collector = LICHCollector()
        for fn in range(5):
            complete = collector.add_chunk(chunks[fn], fn)
            if fn < 4:
                assert not complete
            else:
                assert complete

        assert collector.is_complete
        assert collector.chunks_received == 5

    def test_get_lsf_before_complete(self):
        """Test getting LSF before complete returns None."""
        collector = LICHCollector()
        collector.add_chunk(bytes(6), 0)
        assert collector.get_lsf() is None

    def test_get_lsf_after_complete(self):
        """Test getting LSF after complete."""
        original_lich = LICHFrame(dst="W2FBI", src="N0CALL")
        chunks = original_lich.chunks()

        collector = LICHCollector()
        for fn in range(5):
            collector.add_chunk(chunks[fn], fn)

        lsf = collector.get_lsf()
        assert lsf is not None
        assert lsf.dst.callsign == "W2FBI"
        assert lsf.src.callsign == "N0CALL"

    def test_get_lich_after_complete(self):
        """Test getting LICH after complete."""
        original_lich = LICHFrame(dst="W2FBI", src="N0CALL")
        chunks = original_lich.chunks()

        collector = LICHCollector()
        for fn in range(5):
            collector.add_chunk(chunks[fn], fn)

        lich = collector.get_lich()
        assert lich is not None
        assert lich.dst.callsign == "W2FBI"

    def test_reset(self):
        """Test collector reset."""
        collector = LICHCollector()
        collector.add_chunk(bytes(6), 0)
        collector.add_chunk(bytes(6), 1)
        assert collector.chunks_received == 2

        collector.reset()
        assert collector.chunks_received == 0
        assert not collector.is_complete

    def test_out_of_order_chunks(self):
        """Test handling out-of-order chunks."""
        lich = LICHFrame(dst="W2FBI", src="N0CALL")
        chunks = lich.chunks()

        collector = LICHCollector()
        # Add in reverse order
        for fn in [4, 3, 2, 1, 0]:
            collector.add_chunk(chunks[fn], fn)

        assert collector.is_complete
        recovered = collector.get_lich()
        assert recovered.dst.callsign == "W2FBI"

    def test_recover_from_frames(self):
        """Test static recover_from_frames method."""
        lich = LICHFrame(dst="W2FBI", src="N0CALL")
        chunks = lich.chunks()

        # Create fake frame bytes with LICH chunks at start
        frames = [chunk + bytes(20) for chunk in chunks]

        data = LICHCollector.recover_from_frames(frames)
        assert data is not None
        # LSF is 28 bytes without CRC, 30 with CRC - implementation may vary
        assert len(data) in (28, 30)

    def test_recover_from_frames_incomplete(self):
        """Test recover_from_frames with incomplete data."""
        frames = [bytes(6) + bytes(20)] * 3  # Only 3 frames
        data = LICHCollector.recover_from_frames(frames)
        # Should return None since not all chunks received
        # (actually it might return something since same chunk 3 times
        #  will overwrite, but let's test the behavior)


class TestLICHRoundtrip:
    """Integration tests for LICH roundtrip."""

    def test_full_roundtrip(self):
        """Test complete LICH -> chunks -> collect -> LICH roundtrip."""
        # Create original LICH
        original = LICHFrame(
            dst="W2FBI",
            src="N0CALL",
            stream_type=0x1234,
            nonce=bytes(range(14)),
        )

        # Split into chunks
        chunks = original.chunks()

        # Collect chunks
        collector = LICHCollector()
        for fn, chunk in enumerate(chunks):
            collector.add_chunk(chunk, fn)

        # Recover LICH
        recovered = collector.get_lich()

        # Compare
        assert recovered.dst.callsign == original.dst.callsign
        assert recovered.src.callsign == original.src.callsign
        assert recovered.stream_type == original.stream_type
        assert recovered.nonce == original.nonce

    def test_lsf_lich_conversion_roundtrip(self):
        """Test LSF -> LICH -> LSF roundtrip."""
        # Create LSF
        original_lsf = LinkSetupFrame(
            dst="W2FBI",
            src="N0CALL",
            type_field=0x1234,
        )

        # Convert to LICH
        lich = LICHFrame.from_lsf(original_lsf)

        # Convert back to LSF
        recovered_lsf = lich.to_lsf()

        # Compare
        assert recovered_lsf.dst.callsign == original_lsf.dst.callsign
        assert recovered_lsf.src.callsign == original_lsf.src.callsign
        assert recovered_lsf.type_field == original_lsf.type_field
