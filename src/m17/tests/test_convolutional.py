"""
Tests for M17 Convolutional Encoder

Tests the K=5 rate 1/2 convolutional encoder.
"""

import pytest

from m17.codec.convolutional import (
    conv_encode,
    conv_encode_lsf,
    conv_encode_stream,
    conv_encode_packet,
    conv_encode_bert,
    conv_encode_bytes,
    POLY_G1,
    POLY_G2,
    _unpack_bits,
)


class TestPolynomials:
    """Test polynomial constants."""

    def test_g1_polynomial(self):
        """Test G1 polynomial value."""
        assert POLY_G1 == 0x19  # x^4 + x^3 + 1

    def test_g2_polynomial(self):
        """Test G2 polynomial value."""
        assert POLY_G2 == 0x17  # x^4 + x^2 + x + 1


class TestUnpackBits:
    """Tests for _unpack_bits helper function."""

    def test_unpack_single_byte(self):
        """Test unpacking a single byte."""
        bits = _unpack_bits(b"\xA5")  # 10100101
        assert bits == [1, 0, 1, 0, 0, 1, 0, 1]

    def test_unpack_multiple_bytes(self):
        """Test unpacking multiple bytes."""
        bits = _unpack_bits(b"\xFF\x00")
        assert bits[:8] == [1] * 8
        assert bits[8:] == [0] * 8

    def test_unpack_partial(self):
        """Test unpacking partial bits."""
        bits = _unpack_bits(b"\xFF", num_bits=4)
        assert bits == [1, 1, 1, 1]

    def test_unpack_zero_byte(self):
        """Test unpacking zero byte."""
        bits = _unpack_bits(b"\x00")
        assert bits == [0] * 8


class TestConvEncode:
    """Tests for conv_encode function."""

    def test_empty_input(self):
        """Test encoding empty input."""
        encoded = conv_encode([], flush=True)
        # With flush, we still get 4*2=8 bits from the flush
        assert len(encoded) == 8

    def test_single_bit(self):
        """Test encoding a single bit."""
        encoded = conv_encode([1], flush=True)
        # 1 input bit + 4 flush bits = 5 bits -> 10 output bits
        assert len(encoded) == 10

    def test_output_length_with_flush(self):
        """Test output length with flush enabled."""
        input_bits = [0, 1, 0, 1, 0, 1, 0, 1]
        encoded = conv_encode(input_bits, flush=True)
        # (8 + 4) * 2 = 24 output bits
        assert len(encoded) == 24

    def test_output_length_without_flush(self):
        """Test output length without flush."""
        input_bits = [0, 1, 0, 1, 0, 1, 0, 1]
        encoded = conv_encode(input_bits, flush=False)
        # 8 * 2 = 16 output bits
        assert len(encoded) == 16

    def test_all_zeros(self):
        """Test encoding all zeros."""
        input_bits = [0] * 8
        encoded = conv_encode(input_bits, flush=True)
        # All zeros in, all zeros out (encoder starts at state 0)
        assert all(b == 0 for b in encoded)

    def test_deterministic(self):
        """Test that encoding is deterministic."""
        input_bits = [1, 0, 1, 1, 0, 0, 1, 0]
        encoded1 = conv_encode(input_bits, flush=True)
        encoded2 = conv_encode(input_bits, flush=True)
        assert encoded1 == encoded2

    def test_rate_half(self):
        """Test that output is exactly 2x input (plus flush)."""
        for length in [1, 8, 16, 32]:
            input_bits = [0] * length
            encoded = conv_encode(input_bits, flush=True)
            assert len(encoded) == (length + 4) * 2


class TestConvEncodeLsf:
    """Tests for conv_encode_lsf function."""

    def test_correct_input_length(self):
        """Test encoding 30-byte LSF."""
        lsf_data = bytes(30)
        encoded = conv_encode_lsf(lsf_data)
        # 240 input bits + 4 flush = 244 bits -> 488 output bits
        assert len(encoded) == 488

    def test_wrong_input_length(self):
        """Test that wrong input length raises error."""
        with pytest.raises(ValueError, match="30 bytes"):
            conv_encode_lsf(bytes(29))

        with pytest.raises(ValueError, match="30 bytes"):
            conv_encode_lsf(bytes(31))

    def test_known_input(self):
        """Test encoding known LSF data."""
        # All zeros
        lsf_data = bytes(30)
        encoded = conv_encode_lsf(lsf_data)
        assert len(encoded) == 488
        assert all(b == 0 for b in encoded)

    def test_nonzero_input(self):
        """Test encoding non-zero LSF data."""
        lsf_data = bytes(range(30))
        encoded = conv_encode_lsf(lsf_data)
        assert len(encoded) == 488
        # Should have some non-zero outputs
        assert any(b == 1 for b in encoded)


class TestConvEncodeStream:
    """Tests for conv_encode_stream function."""

    def test_correct_output_length(self):
        """Test encoding stream frame produces correct length."""
        frame_number = 0x0001
        payload = bytes(16)
        encoded = conv_encode_stream(frame_number, payload)
        # 16 + 128 = 144 bits + 4 flush = 148 bits -> 296 output bits
        assert len(encoded) == 296

    def test_wrong_payload_length(self):
        """Test that wrong payload length raises error."""
        with pytest.raises(ValueError, match="16 bytes"):
            conv_encode_stream(0x0001, bytes(15))

    def test_frame_number_encoding(self):
        """Test that frame number affects output."""
        payload = bytes(16)
        encoded1 = conv_encode_stream(0x0000, payload)
        encoded2 = conv_encode_stream(0x1234, payload)
        assert encoded1 != encoded2

    def test_payload_encoding(self):
        """Test that payload affects output."""
        encoded1 = conv_encode_stream(0x0000, bytes(16))
        encoded2 = conv_encode_stream(0x0000, bytes([0xFF] * 16))
        assert encoded1 != encoded2

    def test_eot_frame(self):
        """Test encoding EOT frame (MSB set)."""
        frame_number = 0x8000  # EOT flag
        payload = bytes(16)
        encoded = conv_encode_stream(frame_number, payload)
        assert len(encoded) == 296


class TestConvEncodePacket:
    """Tests for conv_encode_packet function."""

    def test_correct_output_length(self):
        """Test encoding packet chunk produces correct length."""
        packet_chunk = bytes(26)
        encoded = conv_encode_packet(packet_chunk)
        # 206 bits + 4 flush = 210 bits -> 420 output bits
        assert len(encoded) == 420

    def test_wrong_input_length(self):
        """Test that wrong input length raises error."""
        with pytest.raises(ValueError, match="26 bytes"):
            conv_encode_packet(bytes(25))


class TestConvEncodeBert:
    """Tests for conv_encode_bert function."""

    def test_correct_output_length(self):
        """Test encoding BERT frame produces correct length."""
        bert_data = bytes(25)
        encoded = conv_encode_bert(bert_data)
        # 197 bits + 4 flush = 201 bits -> 402 output bits
        assert len(encoded) == 402

    def test_wrong_input_length(self):
        """Test that wrong input length raises error."""
        with pytest.raises(ValueError, match="25 bytes"):
            conv_encode_bert(bytes(24))


class TestConvEncodeBytes:
    """Tests for conv_encode_bytes function."""

    def test_single_byte(self):
        """Test encoding a single byte."""
        encoded = conv_encode_bytes(b"\xFF")
        # 8 bits + 4 flush = 12 bits -> 24 output bits
        assert len(encoded) == 24

    def test_multiple_bytes(self):
        """Test encoding multiple bytes."""
        encoded = conv_encode_bytes(b"\x00\xFF")
        # 16 bits + 4 flush = 20 bits -> 40 output bits
        assert len(encoded) == 40

    def test_empty_bytes(self):
        """Test encoding empty bytes."""
        encoded = conv_encode_bytes(b"")
        # 0 bits + 4 flush = 4 bits -> 8 output bits
        assert len(encoded) == 8
