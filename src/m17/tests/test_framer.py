"""Tests for M17 framer module (legacy).

Tests for M17RFFramer and M17IPFramer classes.
Note: This module is deprecated but still needs test coverage.
"""

import warnings

import pytest


class TestM17RFFramer:
    """Tests for M17RFFramer class."""

    def test_construction(self):
        """Test basic framer construction."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from m17.framer import M17RFFramer

            framer = M17RFFramer(dst="W2FBI", src="N0CALL")

            assert framer.packet_count == 0
            assert framer.lich_frame is not None

    def test_payload_stream_single_frame(self):
        """Test payload_stream with data that fits in one frame."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from m17.framer import M17RFFramer

            framer = M17RFFramer(dst="W2FBI", src="N0CALL")

            # 16 bytes fits in one stream frame
            payload = bytes(16)
            frames = framer.payload_stream(payload)

            assert len(frames) == 1
            assert framer.packet_count == 1

    def test_payload_stream_multiple_frames(self):
        """Test payload_stream with data requiring multiple frames."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from m17.framer import M17RFFramer
            from m17.frames import StreamFrame

            framer = M17RFFramer(dst="W2FBI", src="N0CALL")

            # Large payload that needs multiple frames
            payload = bytes(StreamFrame.payload_sz * 3 + 5)
            frames = framer.payload_stream(payload)

            assert len(frames) == 4  # 3 full + 1 partial
            assert framer.packet_count == 4

    def test_payload_stream_padding(self):
        """Test that short payloads are padded."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from m17.framer import M17RFFramer
            from m17.frames import StreamFrame

            framer = M17RFFramer(dst="W2FBI", src="N0CALL")

            # Short payload
            payload = b"test"
            frames = framer.payload_stream(payload)

            assert len(frames) == 1
            # Frame payload should be full size (padded)
            assert len(frames[0].payload.payload) == StreamFrame.payload_sz

    def test_packet_count_increments(self):
        """Test that packet_count increments properly."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from m17.framer import M17RFFramer

            framer = M17RFFramer(dst="W2FBI", src="N0CALL")

            assert framer.packet_count == 0

            framer.payload_stream(bytes(16))
            assert framer.packet_count == 1

            framer.payload_stream(bytes(16))
            assert framer.packet_count == 2

    def test_packet_count_wraps(self):
        """Test that packet_count wraps at 2^16."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from m17.framer import M17RFFramer

            framer = M17RFFramer(dst="W2FBI", src="N0CALL")

            # Set to max - 1
            framer.packet_count = 2**16 - 1

            # Generate one frame
            framer.payload_stream(bytes(16))

            # Should wrap to 0
            assert framer.packet_count == 0

    def test_lich_chunks_rotate(self):
        """Test that LICH chunks rotate through frames."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from m17.framer import M17RFFramer
            from m17.frames import StreamFrame

            framer = M17RFFramer(dst="W2FBI", src="N0CALL")

            # Generate 6 frames to see LICH rotation
            payload = bytes(StreamFrame.payload_sz * 6)
            frames = framer.payload_stream(payload)

            assert len(frames) == 6

            # Each frame should have a LICH chunk
            for frame in frames:
                assert len(frame.lich_chunk) == 6

    def test_stream_type_preserved(self):
        """Test that stream_type is preserved."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from m17.framer import M17RFFramer

            framer = M17RFFramer(dst="W2FBI", src="N0CALL", stream_type=0x0005)

            assert framer.lich_frame.stream_type == 0x0005

    def test_nonce_preserved(self):
        """Test that nonce is preserved."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from m17.framer import M17RFFramer

            nonce = bytes(range(14))
            framer = M17RFFramer(dst="W2FBI", src="N0CALL", nonce=nonce)

            assert framer.lich_frame.nonce == nonce


class TestM17IPFramer:
    """Tests for M17IPFramer class."""

    def test_construction(self):
        """Test basic IP framer construction."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from m17.framer import M17IPFramer

            framer = M17IPFramer(dst="W2FBI", src="N0CALL")

            assert framer.packet_count == 0
            assert framer.lich_frame is not None
            assert 0 <= framer.stream_id < 2**16

    def test_construction_with_stream_id(self):
        """Test IP framer with explicit stream_id."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from m17.framer import M17IPFramer

            framer = M17IPFramer(stream_id=0x1234, dst="W2FBI", src="N0CALL")

            assert framer.stream_id == 0x1234

    def test_payload_stream_returns_ip_frames(self):
        """Test payload_stream returns IPFrame objects."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from m17.framer import M17IPFramer
            from m17.frames import IPFrame

            framer = M17IPFramer(dst="W2FBI", src="N0CALL")

            payload = bytes(16)
            frames = framer.payload_stream(payload)

            assert len(frames) == 1
            assert isinstance(frames[0], IPFrame)

    def test_payload_stream_multiple_frames(self):
        """Test payload_stream with multiple frames."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from m17.framer import M17IPFramer
            from m17.frames import IPFrame, StreamFrame

            framer = M17IPFramer(dst="W2FBI", src="N0CALL")

            # Generate multiple frames
            payload = bytes(StreamFrame.payload_sz * 3)
            frames = framer.payload_stream(payload)

            assert len(frames) == 3
            for frame in frames:
                assert isinstance(frame, IPFrame)

    def test_stream_id_consistent(self):
        """Test that stream_id is consistent across frames."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from m17.framer import M17IPFramer
            from m17.frames import StreamFrame

            framer = M17IPFramer(stream_id=0xABCD, dst="W2FBI", src="N0CALL")

            payload = bytes(StreamFrame.payload_sz * 3)
            frames = framer.payload_stream(payload)

            for frame in frames:
                assert frame.stream_id == 0xABCD

    def test_frame_numbers_increment(self):
        """Test that frame numbers increment."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from m17.framer import M17IPFramer
            from m17.frames import StreamFrame

            framer = M17IPFramer(dst="W2FBI", src="N0CALL")

            payload = bytes(StreamFrame.payload_sz * 3)
            frames = framer.payload_stream(payload)

            for i, frame in enumerate(frames):
                assert frame.frame_number == i

    def test_dst_src_preserved(self):
        """Test that destination and source are preserved."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from m17.framer import M17IPFramer

            framer = M17IPFramer(dst="W2FBI", src="N0CALL")

            payload = bytes(16)
            frames = framer.payload_stream(payload)

            assert frames[0].dst.callsign.strip() == "W2FBI"
            assert frames[0].src.callsign.strip() == "N0CALL"

    def test_packet_count_wraps(self):
        """Test that packet_count wraps at 2^16."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from m17.framer import M17IPFramer

            framer = M17IPFramer(dst="W2FBI", src="N0CALL")

            # Set to max - 1
            framer.packet_count = 2**16 - 1

            # Generate one frame
            framer.payload_stream(bytes(16))

            # Should wrap to 0
            assert framer.packet_count == 0

    def test_payload_padding(self):
        """Test that short payloads are padded."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from m17.framer import M17IPFramer
            from m17.frames import StreamFrame

            framer = M17IPFramer(dst="W2FBI", src="N0CALL")

            # Very short payload
            payload = b"hi"
            frames = framer.payload_stream(payload)

            assert len(frames) == 1
            # The IPFrame.payload is an M17Payload which contains:
            # - frame_number (2 bytes) + payload (16 bytes) + CRC (2 bytes) = 20 bytes
            # But the actual voice data in M17Payload.payload is 16 bytes
            assert len(frames[0].payload.payload) == StreamFrame.payload_sz

    def test_nonce_preserved(self):
        """Test that nonce is preserved in IP frames."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from m17.framer import M17IPFramer

            nonce = bytes(range(14))
            framer = M17IPFramer(dst="W2FBI", src="N0CALL", nonce=nonce)

            payload = bytes(16)
            frames = framer.payload_stream(payload)

            assert frames[0].nonce == nonce

    def test_stream_type_preserved(self):
        """Test that stream_type is preserved in IP frames."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from m17.framer import M17IPFramer

            framer = M17IPFramer(dst="W2FBI", src="N0CALL", stream_type=0x0005)

            payload = bytes(16)
            frames = framer.payload_stream(payload)

            assert frames[0].stream_type == 0x0005


class TestFramerDeprecationWarning:
    """Tests for framer module deprecation warning."""

    def test_import_emits_deprecation_warning(self):
        """Test that importing framer emits deprecation warning."""
        import sys

        # Remove from cache if present
        for mod in list(sys.modules.keys()):
            if mod == "m17.framer" or mod.startswith("m17.framer."):
                del sys.modules[mod]

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            import m17.framer  # noqa: F401

            # Should have at least one deprecation warning
            deprecation_warnings = [
                x for x in w if issubclass(x.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1

            # Check warning message
            warning_messages = [str(x.message) for x in deprecation_warnings]
            assert any("deprecated" in msg.lower() for msg in warning_messages)
