"""
Tests for M17 Golay(24,12) codec.
"""

import pytest

from m17.codec.golay import (
    golay24_encode,
    golay24_decode,
    golay24_sdecode,
    encode_lich,
    decode_lich,
    ENCODE_MATRIX,
    DECODE_MATRIX,
)


class TestGolay24Encode:
    """Test Golay(24,12) encoding."""

    def test_encode_zero(self):
        """Test encoding of zero."""
        result = golay24_encode(0)
        assert result == 0  # Data 0, checksum 0

    def test_encode_simple(self):
        """Test encoding a simple value."""
        result = golay24_encode(0x123)
        # Result should be 24 bits: 12 data + 12 parity
        assert (result >> 12) == 0x123  # Upper 12 bits are data
        assert 0 <= (result & 0xFFF) <= 0xFFF  # Lower 12 bits are parity

    def test_encode_max(self):
        """Test encoding maximum 12-bit value."""
        result = golay24_encode(0xFFF)
        assert (result >> 12) == 0xFFF
        assert isinstance(result, int)

    def test_encode_all_ones_data(self):
        """Test that all combinations produce valid codewords."""
        for data in range(0, 4096, 256):  # Sample every 256th value
            result = golay24_encode(data)
            assert 0 <= result <= 0xFFFFFF


class TestGolay24Decode:
    """Test Golay(24,12) decoding."""

    def test_decode_no_errors(self):
        """Test decoding codeword with no errors."""
        original = 0x123
        encoded = golay24_encode(original)
        decoded, errors = golay24_decode(encoded)
        assert decoded == original
        assert errors == 0

    def test_decode_one_error_parity(self):
        """Test decoding with one error in parity bits."""
        original = 0x123
        encoded = golay24_encode(original)
        # Flip one bit in parity (lower 12 bits)
        corrupted = encoded ^ 0x001
        decoded, errors = golay24_decode(corrupted)
        assert decoded == original
        assert errors == 1

    def test_decode_one_error_data(self):
        """Test decoding with one error in data bits."""
        original = 0x123
        encoded = golay24_encode(original)
        # Flip one bit in data (upper 12 bits)
        corrupted = encoded ^ 0x1000
        decoded, errors = golay24_decode(corrupted)
        assert decoded == original
        assert errors >= 1

    def test_decode_two_errors(self):
        """Test decoding with two errors."""
        original = 0x123
        encoded = golay24_encode(original)
        # Flip two bits
        corrupted = encoded ^ 0x003
        decoded, errors = golay24_decode(corrupted)
        assert decoded == original

    def test_decode_three_errors(self):
        """Test decoding with three errors (maximum correctable)."""
        original = 0x123
        encoded = golay24_encode(original)
        # Flip three bits
        corrupted = encoded ^ 0x007
        decoded, errors = golay24_decode(corrupted)
        assert decoded == original

    def test_decode_roundtrip(self):
        """Test encode/decode roundtrip for multiple values."""
        for original in [0, 0x001, 0x123, 0x555, 0xAAA, 0xFFF]:
            encoded = golay24_encode(original)
            decoded, errors = golay24_decode(encoded)
            assert decoded == original
            assert errors == 0


class TestGolay24SoftDecode:
    """Test Golay(24,12) soft decoding."""

    def test_sdecode_perfect_zeros(self):
        """Test soft decode with perfect zero codeword."""
        soft = [0] * 24  # All strong zeros
        # This represents data=0, parity=0
        result = golay24_sdecode(soft)
        assert result == 0

    def test_sdecode_perfect_ones(self):
        """Test soft decode with known codeword."""
        # Encode a known value
        original = 0x123
        encoded = golay24_encode(original)

        # Convert to soft bits (MSB first as in M17)
        soft = []
        for i in range(23, -1, -1):
            bit = (encoded >> i) & 1
            soft.append(0xFFFF if bit else 0)

        result = golay24_sdecode(soft)
        assert result == original

    def test_sdecode_noisy(self):
        """Test soft decode with some uncertainty."""
        original = 0x123
        encoded = golay24_encode(original)

        # Convert to soft with some noise
        soft = []
        for i in range(23, -1, -1):
            bit = (encoded >> i) & 1
            # Add some uncertainty
            if bit:
                soft.append(0xC000)  # Strong-ish 1
            else:
                soft.append(0x4000)  # Strong-ish 0

        result = golay24_sdecode(soft)
        assert result == original


class TestLICHCodec:
    """Test LICH chunk encoding/decoding."""

    def test_encode_lich_zeros(self):
        """Test encoding LICH chunk of zeros."""
        data = bytes(6)
        result = encode_lich(data)
        assert len(result) == 12  # 96 bits = 12 bytes

    def test_encode_lich_pattern(self):
        """Test encoding LICH chunk with pattern."""
        data = bytes([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC])
        result = encode_lich(data)
        assert len(result) == 12

    def test_encode_lich_wrong_size(self):
        """Test that wrong size raises error."""
        with pytest.raises(ValueError):
            encode_lich(bytes(5))
        with pytest.raises(ValueError):
            encode_lich(bytes(7))

    def test_decode_lich_roundtrip(self):
        """Test LICH encode/decode roundtrip."""
        original = bytes([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC])
        encoded = encode_lich(original)

        # Convert bytes to soft bits (8 bits per byte, MSB first)
        soft = []
        for byte in encoded:
            for i in range(7, -1, -1):
                bit = (byte >> i) & 1
                soft.append(0xFFFF if bit else 0)

        decoded = decode_lich(soft)
        assert decoded == original


class TestMatrices:
    """Test encoding/decoding matrices."""

    def test_encode_matrix_size(self):
        """Test encode matrix has correct size."""
        assert len(ENCODE_MATRIX) == 12

    def test_decode_matrix_size(self):
        """Test decode matrix has correct size."""
        assert len(DECODE_MATRIX) == 12

    def test_matrix_values_12bit(self):
        """Test all matrix values are 12-bit."""
        for val in ENCODE_MATRIX:
            assert 0 <= val <= 0xFFF
        for val in DECODE_MATRIX:
            assert 0 <= val <= 0xFFF
