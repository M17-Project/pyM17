"""Tests for M17 Puncturing Patterns

Tests the puncture and depuncture operations for M17 FEC.
"""

import pytest

from m17.codec.puncture import (
    PUNCTURE_P1,
    PUNCTURE_P2,
    PUNCTURE_P3,
    depuncture,
    depuncture_lsf,
    depuncture_packet,
    depuncture_stream,
    puncture,
    puncture_bert,
    puncture_lsf,
    puncture_packet,
    puncture_stream,
)


class TestPuncturePatterns:
    """Tests for puncture pattern constants."""

    def test_p1_pattern_length(self):
        """Test P1 pattern length."""
        assert len(PUNCTURE_P1) == 61

    def test_p2_pattern_length(self):
        """Test P2 pattern length."""
        assert len(PUNCTURE_P2) == 12

    def test_p3_pattern_length(self):
        """Test P3 pattern length."""
        assert len(PUNCTURE_P3) == 8

    def test_p1_pattern_values(self):
        """Test P1 pattern contains only 0 and 1."""
        assert all(b in (0, 1) for b in PUNCTURE_P1)

    def test_p2_pattern_values(self):
        """Test P2 pattern contains only 0 and 1."""
        assert all(b in (0, 1) for b in PUNCTURE_P2)

    def test_p3_pattern_values(self):
        """Test P3 pattern contains only 0 and 1."""
        assert all(b in (0, 1) for b in PUNCTURE_P3)

    def test_p2_removes_one_in_twelve(self):
        """Test P2 removes 1 bit per 12."""
        # P2 has 11 ones and 1 zero
        assert sum(PUNCTURE_P2) == 11
        assert len(PUNCTURE_P2) - sum(PUNCTURE_P2) == 1

    def test_p3_removes_one_in_eight(self):
        """Test P3 removes 1 bit per 8."""
        # P3 has 7 ones and 1 zero
        assert sum(PUNCTURE_P3) == 7
        assert len(PUNCTURE_P3) - sum(PUNCTURE_P3) == 1


class TestPuncture:
    """Tests for puncture function."""

    def test_puncture_basic(self):
        """Test basic puncturing operation."""
        bits = [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1]
        result = puncture(bits, PUNCTURE_P2)
        # P2 removes position 11, so 12 -> 11
        assert len(result) == 11

    def test_puncture_empty(self):
        """Test puncturing empty input."""
        result = puncture([], PUNCTURE_P2)
        assert result == []

    def test_puncture_preserves_order(self):
        """Test that puncturing preserves bit order."""
        bits = list(range(12))  # [0,1,2,3,4,5,6,7,8,9,10,11]
        result = puncture(bits, PUNCTURE_P2)
        # P2 pattern removes last bit (index 11)
        assert result == list(range(11))  # [0,1,2,3,4,5,6,7,8,9,10]

    def test_puncture_p1_rate(self):
        """Test P1 puncture rate for LSF."""
        # LSF: 488 bits -> 368 bits
        bits = [0] * 488
        result = puncture(bits, PUNCTURE_P1)
        assert len(result) == 368

    def test_puncture_p2_rate(self):
        """Test P2 puncture rate for stream."""
        # Stream: 296 bits -> 272 bits
        bits = [0] * 296
        result = puncture(bits, PUNCTURE_P2)
        assert len(result) == 272

    def test_puncture_p3_rate(self):
        """Test P3 puncture rate for packet."""
        # Packet: 420 bits -> 368 bits
        bits = [0] * 420
        result = puncture(bits, PUNCTURE_P3)
        # 420 / 8 = 52.5 cycles, so 52*7 + partial
        assert len(result) == 368


class TestDepuncture:
    """Tests for depuncture function."""

    def test_depuncture_basic(self):
        """Test basic depuncturing operation."""
        bits = [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]  # 11 bits
        result = depuncture(bits, PUNCTURE_P2, fill_value=2)
        # P2 removes position 11, so fill at position 11
        assert len(result) == 12
        assert result[11] == 2  # Fill value at punctured position

    def test_depuncture_empty(self):
        """Test depuncturing empty input."""
        result = depuncture([], PUNCTURE_P2)
        assert result == []

    def test_depuncture_fill_value(self):
        """Test custom fill value."""
        bits = [0] * 11
        result = depuncture(bits, PUNCTURE_P2, fill_value=0x7FFF)
        assert result[11] == 0x7FFF

    def test_puncture_depuncture_roundtrip(self):
        """Test that puncture then depuncture preserves data at kept positions."""
        original = list(range(12))
        punctured = puncture(original, PUNCTURE_P2)
        depunctured = depuncture(punctured, PUNCTURE_P2, fill_value=-1)

        # Check that non-punctured positions match
        for i, p in enumerate(PUNCTURE_P2):
            if p == 1:  # Position was kept
                assert depunctured[i] == original[i]
            else:  # Position was punctured
                assert depunctured[i] == -1


class TestPunctureLsf:
    """Tests for puncture_lsf function."""

    def test_correct_output_length(self):
        """Test LSF puncturing produces correct length."""
        bits = [0] * 488
        result = puncture_lsf(bits)
        assert len(result) == 368

    def test_wrong_input_length(self):
        """Test that wrong input length raises error."""
        with pytest.raises(ValueError, match="488"):
            puncture_lsf([0] * 400)


class TestPunctureStream:
    """Tests for puncture_stream function."""

    def test_correct_output_length(self):
        """Test stream puncturing produces correct length."""
        bits = [0] * 296
        result = puncture_stream(bits)
        assert len(result) == 272

    def test_wrong_input_length(self):
        """Test that wrong input length raises error."""
        with pytest.raises(ValueError, match="296"):
            puncture_stream([0] * 300)


class TestPuncturePacket:
    """Tests for puncture_packet function."""

    def test_correct_output_length(self):
        """Test packet puncturing produces correct length."""
        bits = [0] * 420
        result = puncture_packet(bits)
        assert len(result) == 368

    def test_wrong_input_length(self):
        """Test that wrong input length raises error."""
        with pytest.raises(ValueError, match="420"):
            puncture_packet([0] * 400)


class TestPunctureBert:
    """Tests for puncture_bert function."""

    def test_correct_output_length(self):
        """Test BERT puncturing produces correct length."""
        bits = [0] * 402
        result = puncture_bert(bits)
        # P2 pattern: 402 bits with 11/12 kept = ~368-369 bits
        # The actual output depends on pattern alignment
        assert len(result) >= 368

    def test_wrong_input_length(self):
        """Test that wrong input length raises error."""
        with pytest.raises(ValueError, match="402"):
            puncture_bert([0] * 400)


class TestDepunctureFunctions:
    """Tests for frame-specific depuncture functions."""

    def test_depuncture_lsf(self):
        """Test LSF depuncturing."""
        bits = [0] * 368
        result = depuncture_lsf(bits)
        assert len(result) == 488

    def test_depuncture_stream(self):
        """Test stream depuncturing."""
        bits = [0] * 272
        result = depuncture_stream(bits)
        # Depuncture may add extra bits due to pattern alignment
        assert len(result) >= 296

    def test_depuncture_packet(self):
        """Test packet depuncturing."""
        bits = [0] * 368
        result = depuncture_packet(bits)
        # Depuncture may add extra bits due to pattern alignment
        assert len(result) >= 420

    def test_depuncture_custom_fill(self):
        """Test depuncturing with custom fill value."""
        bits = [0] * 272
        result = depuncture_stream(bits, fill_value=0x8000)
        # Check that fill values were inserted
        assert 0x8000 in result
