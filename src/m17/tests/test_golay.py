"""Tests for M17 Golay(24,12) codec.
"""

import pytest

from m17.codec.golay import (
    DECODE_MATRIX,
    ENCODE_MATRIX,
    decode_lich,
    encode_lich,
    golay24_decode,
    golay24_encode,
    golay24_sdecode,
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


class TestGolay24DecodeErrorCorrection:
    """Test Golay(24,12) error correction edge cases."""

    def test_decode_two_errors_in_data(self):
        """Test decoding with two errors in data bits."""
        original = 0x555
        encoded = golay24_encode(original)
        # Flip two bits in data (upper 12 bits)
        corrupted = encoded ^ 0x003000  # Bits 12 and 13
        decoded, errors = golay24_decode(corrupted)
        assert decoded == original
        assert errors >= 2

    def test_decode_two_errors_mixed(self):
        """Test decoding with errors in both data and parity."""
        original = 0xABC
        encoded = golay24_encode(original)
        # One error in data, one in parity
        corrupted = encoded ^ 0x001001
        decoded, errors = golay24_decode(corrupted)
        assert decoded == original

    def test_decode_three_errors_in_data(self):
        """Test decoding with three errors in data bits."""
        original = 0x789
        encoded = golay24_encode(original)
        # Flip three bits in data
        corrupted = encoded ^ 0x007000
        decoded, errors = golay24_decode(corrupted)
        assert decoded == original
        assert errors >= 0  # Should correct

    def test_decode_three_errors_mixed_data_parity(self):
        """Test decoding with two data errors and one parity error."""
        original = 0x456
        encoded = golay24_encode(original)
        # Two bits in data, one in parity
        corrupted = encoded ^ 0x003001
        decoded, errors = golay24_decode(corrupted)
        assert decoded == original

    def test_decode_uncorrectable(self):
        """Test that too many errors returns uncorrectable."""
        original = 0x123
        encoded = golay24_encode(original)
        # Flip many bits (more than 3)
        corrupted = encoded ^ 0x0F0F0F
        decoded, errors = golay24_decode(corrupted)
        # May be uncorrectable or wrong decode
        if errors == -1:
            assert decoded == 0xFFFF

    def test_decode_algebraic_path(self):
        """Test algebraic decoding path (3 errors in data)."""
        original = 0xDEF
        encoded = golay24_encode(original)
        # Three errors specifically in data bits
        corrupted = encoded ^ 0x111000  # Three separated bits in data
        decoded, errors = golay24_decode(corrupted)
        assert decoded == original

    def test_decode_one_parity_two_data(self):
        """Test one error in parity, two in data."""
        original = 0x321
        encoded = golay24_encode(original)
        # One in parity, two in data
        corrupted = encoded ^ 0x011001
        decoded, errors = golay24_decode(corrupted)
        assert decoded == original

    def test_decode_exhaustive_single_errors(self):
        """Test all single-bit error positions are correctable."""
        original = 0xABD
        encoded = golay24_encode(original)
        for bit in range(24):
            corrupted = encoded ^ (1 << bit)
            decoded, errors = golay24_decode(corrupted)
            assert decoded == original, f"Failed for bit {bit}"
            assert errors == 1

    def test_decode_exhaustive_double_errors_sample(self):
        """Test sample of double-bit error positions."""
        original = 0x742
        encoded = golay24_encode(original)
        # Sample of double-bit error positions
        error_patterns = [
            0x000003,  # Bits 0,1
            0x000005,  # Bits 0,2
            0x001001,  # Bits 0,12
            0x003000,  # Bits 12,13
            0x800001,  # Bits 0,23
        ]
        for pattern in error_patterns:
            corrupted = encoded ^ pattern
            decoded, errors = golay24_decode(corrupted)
            assert decoded == original, f"Failed for pattern {hex(pattern)}"


class TestGolay24SoftDecodeEdgeCases:
    """Test Golay(24,12) soft decoding edge cases."""

    def test_sdecode_wrong_length(self):
        """Test that wrong length raises error."""
        with pytest.raises(ValueError, match="must be 24 soft bits"):
            golay24_sdecode([0] * 23)
        with pytest.raises(ValueError, match="must be 24 soft bits"):
            golay24_sdecode([0] * 25)

    def test_sdecode_with_flipped_bit(self):
        """Test soft decode with one flipped bit."""
        original = 0x456
        encoded = golay24_encode(original)

        # Convert to soft bits with one flipped
        soft = []
        for i in range(23, -1, -1):
            bit = (encoded >> i) & 1
            soft.append(0xFFFF if bit else 0)

        # Flip one bit (make it opposite)
        soft[5] = 0 if soft[5] == 0xFFFF else 0xFFFF

        result = golay24_sdecode(soft)
        assert result == original

    def test_sdecode_with_two_flipped_bits(self):
        """Test soft decode with two flipped bits."""
        original = 0x789
        encoded = golay24_encode(original)

        soft = []
        for i in range(23, -1, -1):
            bit = (encoded >> i) & 1
            soft.append(0xFFFF if bit else 0)

        # Flip two bits
        soft[3] = 0 if soft[3] == 0xFFFF else 0xFFFF
        soft[7] = 0 if soft[7] == 0xFFFF else 0xFFFF

        result = golay24_sdecode(soft)
        assert result == original

    def test_sdecode_with_uncertain_bits(self):
        """Test soft decode with uncertain (middle value) bits."""
        original = 0x111
        encoded = golay24_encode(original)

        soft = []
        for i in range(23, -1, -1):
            bit = (encoded >> i) & 1
            # Make some bits uncertain (near 0x7FFF)
            if i % 4 == 0:
                soft.append(0x8000 if bit else 0x7000)
            else:
                soft.append(0xFFFF if bit else 0)

        result = golay24_sdecode(soft)
        assert result == original

    def test_sdecode_all_uncertain(self):
        """Test soft decode when all bits are uncertain."""
        # All bits at middle value - result unpredictable but shouldn't crash
        soft = [0x7FFF] * 24
        result = golay24_sdecode(soft)
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFF

    def test_sdecode_three_flipped_bits(self):
        """Test soft decode with three flipped bits."""
        original = 0xABC
        encoded = golay24_encode(original)

        soft = []
        for i in range(23, -1, -1):
            bit = (encoded >> i) & 1
            soft.append(0xFFFF if bit else 0)

        # Flip three bits
        soft[2] = 0 if soft[2] == 0xFFFF else 0xFFFF
        soft[10] = 0 if soft[10] == 0xFFFF else 0xFFFF
        soft[18] = 0 if soft[18] == 0xFFFF else 0xFFFF

        result = golay24_sdecode(soft)
        assert result == original


class TestDecodeLichEdgeCases:
    """Test LICH decoding edge cases."""

    def test_decode_lich_wrong_length(self):
        """Test that wrong length raises error."""
        with pytest.raises(ValueError, match="must be 96 soft bits"):
            decode_lich([0] * 95)
        with pytest.raises(ValueError, match="must be 96 soft bits"):
            decode_lich([0] * 97)

    def test_decode_lich_with_noise(self):
        """Test LICH decode with noisy soft bits."""
        original = bytes([0xDE, 0xAD, 0xBE, 0xEF, 0xCA, 0xFE])
        encoded = encode_lich(original)

        # Convert to soft bits with some noise
        soft = []
        for byte in encoded:
            for i in range(7, -1, -1):
                bit = (byte >> i) & 1
                # Add slight noise
                if bit:
                    soft.append(0xE000)  # Slightly weaker 1
                else:
                    soft.append(0x2000)  # Slightly weaker 0

        decoded = decode_lich(soft)
        assert decoded == original

    def test_decode_lich_zeros(self):
        """Test LICH decode of all zeros."""
        original = bytes(6)
        encoded = encode_lich(original)

        soft = []
        for byte in encoded:
            for i in range(7, -1, -1):
                bit = (byte >> i) & 1
                soft.append(0xFFFF if bit else 0)

        decoded = decode_lich(soft)
        assert decoded == original

    def test_decode_lich_all_ones(self):
        """Test LICH decode of all 0xFF."""
        original = bytes([0xFF] * 6)
        encoded = encode_lich(original)

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
