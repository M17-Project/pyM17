"""
Tests for M17 Randomizer

Tests the XOR randomization for DC balance and synchronization.
"""

import pytest

from m17.codec.randomize import (
    randomize,
    derandomize,
    randomize_soft,
    derandomize_soft,
    get_random_bit,
    RAND_SEQ,
    _RAND_BITS,
)


class TestRandSeq:
    """Tests for randomization sequence constants."""

    def test_rand_seq_length(self):
        """Test RAND_SEQ is 46 bytes."""
        assert len(RAND_SEQ) == 46

    def test_rand_bits_length(self):
        """Test _RAND_BITS is 368 bits."""
        assert len(_RAND_BITS) == 368

    def test_rand_bits_values(self):
        """Test _RAND_BITS contains only 0 and 1."""
        assert all(b in (0, 1) for b in _RAND_BITS)

    def test_rand_seq_first_byte(self):
        """Test first byte of RAND_SEQ."""
        assert RAND_SEQ[0] == 0xD6

    def test_rand_seq_last_byte(self):
        """Test last byte of RAND_SEQ."""
        assert RAND_SEQ[45] == 0xC3

    def test_rand_bits_match_seq(self):
        """Test that _RAND_BITS matches RAND_SEQ unpacked."""
        for i in range(368):
            byte_idx = i // 8
            bit_idx = 7 - (i % 8)
            expected = (RAND_SEQ[byte_idx] >> bit_idx) & 1
            assert _RAND_BITS[i] == expected


class TestRandomize:
    """Tests for randomize function."""

    def test_correct_length(self):
        """Test randomize requires 368 bits."""
        bits = [0] * 368
        result = randomize(bits)
        assert len(result) == 368

    def test_wrong_length(self):
        """Test wrong length raises error."""
        with pytest.raises(ValueError, match="368"):
            randomize([0] * 100)

    def test_all_zeros_input(self):
        """Test randomizing all zeros produces RAND sequence."""
        bits = [0] * 368
        result = randomize(bits)
        # Result should be the random sequence itself
        assert result == list(_RAND_BITS)

    def test_all_ones_input(self):
        """Test randomizing all ones produces inverted RAND sequence."""
        bits = [1] * 368
        result = randomize(bits)
        # Result should be inverted random sequence
        expected = [1 - b for b in _RAND_BITS]
        assert result == expected

    def test_self_inverse(self):
        """Test that randomize is its own inverse."""
        original = [i % 2 for i in range(368)]
        randomized = randomize(original)
        recovered = randomize(randomized)  # Apply again
        assert recovered == original


class TestDerandomize:
    """Tests for derandomize function."""

    def test_same_as_randomize(self):
        """Test derandomize is same as randomize (self-inverse)."""
        bits = [i % 2 for i in range(368)]
        r1 = randomize(bits)
        r2 = derandomize(bits)
        assert r1 == r2

    def test_roundtrip(self):
        """Test randomize then derandomize returns original."""
        original = [1 if i % 3 == 0 else 0 for i in range(368)]
        randomized = randomize(original)
        recovered = derandomize(randomized)
        assert recovered == original


class TestRandomizeSoft:
    """Tests for randomize_soft function."""

    def test_correct_length(self):
        """Test randomize_soft requires 368 soft bits."""
        soft_bits = [0] * 368
        result = randomize_soft(soft_bits)
        assert len(result) == 368

    def test_wrong_length(self):
        """Test wrong length raises error."""
        with pytest.raises(ValueError, match="368"):
            randomize_soft([0] * 100)

    def test_all_strong_zeros(self):
        """Test randomizing all strong zeros."""
        soft_bits = [0] * 368
        result = randomize_soft(soft_bits)
        # Where RAND bit is 1, result should be 0xFFFF (inverted)
        for i in range(368):
            if _RAND_BITS[i]:
                assert result[i] == 0xFFFF
            else:
                assert result[i] == 0

    def test_all_strong_ones(self):
        """Test randomizing all strong ones."""
        soft_bits = [0xFFFF] * 368
        result = randomize_soft(soft_bits)
        # Where RAND bit is 1, result should be 0 (inverted)
        for i in range(368):
            if _RAND_BITS[i]:
                assert result[i] == 0
            else:
                assert result[i] == 0xFFFF

    def test_uncertain_values(self):
        """Test randomizing uncertain values (0x7FFF)."""
        soft_bits = [0x7FFF] * 368
        result = randomize_soft(soft_bits)
        # 0xFFFF - 0x7FFF = 0x8000, so inverted uncertain is also near uncertain
        for i in range(368):
            if _RAND_BITS[i]:
                assert result[i] == 0x8000
            else:
                assert result[i] == 0x7FFF

    def test_self_inverse(self):
        """Test that randomize_soft is its own inverse."""
        original = [i * 100 for i in range(368)]
        randomized = randomize_soft(original)
        recovered = randomize_soft(randomized)
        assert recovered == original


class TestDerandomizeSoft:
    """Tests for derandomize_soft function."""

    def test_same_as_randomize_soft(self):
        """Test derandomize_soft is same as randomize_soft."""
        soft_bits = [i * 50 for i in range(368)]
        r1 = randomize_soft(soft_bits)
        r2 = derandomize_soft(soft_bits)
        assert r1 == r2

    def test_roundtrip(self):
        """Test randomize_soft then derandomize_soft returns original."""
        original = [i * 100 % 0xFFFF for i in range(368)]
        randomized = randomize_soft(original)
        recovered = derandomize_soft(randomized)
        assert recovered == original


class TestGetRandomBit:
    """Tests for get_random_bit function."""

    def test_valid_indices(self):
        """Test getting random bits at valid indices."""
        for i in range(368):
            bit = get_random_bit(i)
            assert bit in (0, 1)
            assert bit == _RAND_BITS[i]

    def test_first_bit(self):
        """Test first random bit."""
        # 0xD6 = 11010110, bit 7 = 1
        assert get_random_bit(0) == 1

    def test_negative_index(self):
        """Test negative index raises error."""
        with pytest.raises(ValueError, match="0-367"):
            get_random_bit(-1)

    def test_out_of_range_index(self):
        """Test out of range index raises error."""
        with pytest.raises(ValueError, match="0-367"):
            get_random_bit(368)

        with pytest.raises(ValueError, match="0-367"):
            get_random_bit(1000)
