"""Tests for M17 interleaver.
"""

import pytest

from m17.codec.interleave import (
    INTERLEAVE_SEQ,
    deinterleave,
    deinterleave_soft,
    interleave,
    interleave_soft,
)


class TestInterleave:
    """Test interleaving."""

    def test_sequence_length(self):
        """Test that interleave sequence is correct length."""
        assert len(INTERLEAVE_SEQ) == 368

    def test_sequence_unique(self):
        """Test that all values in sequence are unique."""
        assert len(set(INTERLEAVE_SEQ)) == 368

    def test_sequence_range(self):
        """Test that all values are in valid range."""
        for val in INTERLEAVE_SEQ:
            assert 0 <= val < 368

    def test_interleave_zeros(self):
        """Test interleaving zeros."""
        inp = [0] * 368
        out = interleave(inp)
        assert out == inp

    def test_interleave_position_markers(self):
        """Test that positions are correctly mapped."""
        inp = list(range(368))
        out = interleave(inp)
        # out[i] should be inp[INTERLEAVE_SEQ[i]]
        for i in range(368):
            assert out[i] == INTERLEAVE_SEQ[i]

    def test_deinterleave_recovers_original(self):
        """Test that deinterleave reverses interleave."""
        original = list(range(368))
        interleaved = interleave(original)
        recovered = deinterleave(interleaved)
        assert recovered == original

    def test_interleave_wrong_size(self):
        """Test that wrong size raises error."""
        with pytest.raises(ValueError):
            interleave([0] * 367)
        with pytest.raises(ValueError):
            interleave([0] * 369)

    def test_deinterleave_wrong_size(self):
        """Test that wrong size raises error."""
        with pytest.raises(ValueError):
            deinterleave([0] * 367)

    def test_interleave_preserves_values(self):
        """Test that interleave doesn't modify values."""
        original = [i % 256 for i in range(368)]
        interleaved = interleave(original)
        # Same values, different order
        assert sorted(interleaved) == sorted(original)

    def test_double_interleave_is_identity(self):
        """Test that interleaving twice returns original (involution property).

        The M17 interleaver is designed as a self-inverse permutation,
        meaning interleave(interleave(x)) == x. This is equivalent to
        deinterleave being the same operation as interleave.
        """
        original = list(range(368))
        once = interleave(original)
        twice = interleave(once)
        # M17 interleaver is self-inverse (an involution)
        assert twice == original

    def test_interleave_spreads_adjacent(self):
        """Test that adjacent bits get spread apart."""
        # This is the main purpose of interleaving
        inp = list(range(368))
        out = interleave(inp)

        # Check that at least some adjacent input positions
        # are now far apart in output
        adjacent_spread = False
        for i in range(367):
            # Find where inp[i] and inp[i+1] ended up
            pos_i = out.index(i)
            pos_i1 = out.index(i + 1)
            if abs(pos_i - pos_i1) > 10:
                adjacent_spread = True
                break

        assert adjacent_spread


class TestInterleaveWithSoftBits:
    """Test interleaver with soft bit values."""

    def test_interleave_soft_values(self):
        """Test interleaving soft bit values."""
        # Soft bits: 0 = strong 0, 0xFFFF = strong 1
        inp = [0x7FFF] * 368  # All uncertain
        out = interleave(inp)
        assert all(v == 0x7FFF for v in out)

    def test_deinterleave_soft_roundtrip(self):
        """Test soft bit roundtrip."""
        inp = [i * 178 for i in range(368)]  # Various soft values
        interleaved = interleave(inp)
        recovered = deinterleave(interleaved)
        assert recovered == inp


class TestSoftBitAliases:
    """Test soft bit alias functions."""

    def test_interleave_soft_function(self):
        """Test interleave_soft is an alias for interleave."""
        inp = list(range(368))
        result1 = interleave(inp)
        result2 = interleave_soft(inp)
        assert result1 == result2

    def test_deinterleave_soft_function(self):
        """Test deinterleave_soft is an alias for deinterleave."""
        inp = list(range(368))
        result1 = deinterleave(inp)
        result2 = deinterleave_soft(inp)
        assert result1 == result2

    def test_interleave_soft_with_soft_values(self):
        """Test interleave_soft with typical soft decision values."""
        # Soft bits: 0x0000 = strong 0, 0xFFFF = strong 1, 0x7FFF = uncertain
        inp = [0x0000 if i % 3 == 0 else (0xFFFF if i % 3 == 1 else 0x7FFF) for i in range(368)]
        result = interleave_soft(inp)
        assert len(result) == 368
        # Verify values are preserved
        assert sorted(result) == sorted(inp)

    def test_deinterleave_soft_with_soft_values(self):
        """Test deinterleave_soft with typical soft decision values."""
        inp = [0x0000 if i % 2 == 0 else 0xFFFF for i in range(368)]
        interleaved = interleave_soft(inp)
        recovered = deinterleave_soft(interleaved)
        assert recovered == inp

    def test_soft_roundtrip(self):
        """Test full soft bit roundtrip using alias functions."""
        original = [i * 100 for i in range(368)]  # Varying soft values
        interleaved = interleave_soft(original)
        recovered = deinterleave_soft(interleaved)
        assert recovered == original
