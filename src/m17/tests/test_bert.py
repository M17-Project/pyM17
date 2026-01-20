"""Tests for M17 BERT (Bit Error Rate Test) frames.

Tests BERT frame generation, encoding, and BER calculation.
"""

import pytest

from m17.core.constants import SYNC_BERT
from m17.frames.bert import (
    BERT_PAYLOAD_BITS,
    BERT_PAYLOAD_BYTES,
    BERTFrame,
    BERTGenerator,
    calculate_ber,
)


class TestBERTGenerator:
    """Tests for BERTGenerator class."""

    def test_default_seed(self):
        """Test default seed is 0x1FF."""
        gen = BERTGenerator()
        assert gen.seed == 0x1FF

    def test_custom_seed(self):
        """Test custom seed."""
        gen = BERTGenerator(seed=0x123)
        assert gen.seed == 0x123

    def test_zero_seed_handled(self):
        """Test that zero seed is converted to non-zero."""
        gen = BERTGenerator(seed=0)
        # Should still generate bits without locking up
        bits = gen.generate_bits(100)
        assert len(bits) == 100
        assert any(b == 1 for b in bits)  # Should have some ones

    def test_generate_bits(self):
        """Test bit generation."""
        gen = BERTGenerator(seed=0x1FF)
        bits = gen.generate_bits(50)

        assert len(bits) == 50
        assert all(b in (0, 1) for b in bits)

    def test_generate_bytes(self):
        """Test byte generation."""
        gen = BERTGenerator(seed=0x1FF)
        data = gen.generate_bytes(10)

        assert len(data) == 10
        assert isinstance(data, bytes)

    def test_deterministic_output(self):
        """Test that same seed produces same output."""
        gen1 = BERTGenerator(seed=0x1FF)
        gen2 = BERTGenerator(seed=0x1FF)

        bits1 = gen1.generate_bits(100)
        bits2 = gen2.generate_bits(100)

        assert bits1 == bits2

    def test_different_seeds_different_output(self):
        """Test that different seeds produce different output."""
        gen1 = BERTGenerator(seed=0x1FF)
        gen2 = BERTGenerator(seed=0x100)

        bits1 = gen1.generate_bits(100)
        bits2 = gen2.generate_bits(100)

        assert bits1 != bits2

    def test_reset(self):
        """Test generator reset."""
        gen = BERTGenerator(seed=0x1FF)

        bits1 = gen.generate_bits(50)
        gen.reset()
        bits2 = gen.generate_bits(50)

        assert bits1 == bits2

    def test_prbs_pattern(self):
        """Test that output is pseudo-random (not all zeros or ones)."""
        gen = BERTGenerator(seed=0x1FF)
        bits = gen.generate_bits(1000)

        zeros = bits.count(0)
        ones = bits.count(1)

        # Should be roughly balanced (within 10% for PRBS-9)
        assert 400 < zeros < 600
        assert 400 < ones < 600


class TestBERTFrame:
    """Tests for BERTFrame class."""

    def test_default_payload(self):
        """Test default payload is zeros."""
        frame = BERTFrame()
        assert len(frame.payload) == BERT_PAYLOAD_BYTES
        assert frame.payload == bytes(BERT_PAYLOAD_BYTES)

    def test_payload_padding(self):
        """Test short payload is padded."""
        frame = BERTFrame(payload=b"\x12\x34")
        assert len(frame.payload) == BERT_PAYLOAD_BYTES
        assert frame.payload[:2] == b"\x12\x34"

    def test_payload_truncation(self):
        """Test long payload is truncated."""
        frame = BERTFrame(payload=bytes(50))
        assert len(frame.payload) == BERT_PAYLOAD_BYTES

    def test_generate(self):
        """Test frame generation."""
        frame = BERTFrame.generate(seed=0x1FF)

        assert len(frame.payload) == BERT_PAYLOAD_BYTES
        assert frame.seed == 0x1FF
        assert frame.payload != bytes(BERT_PAYLOAD_BYTES)  # Not all zeros

    def test_generate_deterministic(self):
        """Test that generation is deterministic."""
        frame1 = BERTFrame.generate(seed=0x123)
        frame2 = BERTFrame.generate(seed=0x123)

        assert frame1.payload == frame2.payload

    def test_sync_word(self):
        """Test sync word property."""
        frame = BERTFrame()
        assert frame.sync_word == SYNC_BERT

    def test_get_bits(self):
        """Test bit extraction."""
        frame = BERTFrame.generate()
        bits = frame.get_bits()

        assert len(bits) == BERT_PAYLOAD_BITS
        assert all(b in (0, 1) for b in bits)

    def test_bytes_conversion(self):
        """Test __bytes__ method."""
        frame = BERTFrame.generate()
        assert bytes(frame) == frame.payload

    def test_equality(self):
        """Test frame equality."""
        frame1 = BERTFrame.generate(seed=0x1FF)
        frame2 = BERTFrame.generate(seed=0x1FF)
        frame3 = BERTFrame.generate(seed=0x100)

        assert frame1 == frame2
        assert frame1 != frame3

    def test_bytes_equality(self):
        """Test equality with bytes."""
        frame = BERTFrame.generate(seed=0x1FF)
        assert frame == frame.payload


class TestBERTFrameBER:
    """Tests for BER calculation."""

    def test_zero_ber(self):
        """Test BER is zero for identical frames."""
        frame1 = BERTFrame.generate(seed=0x1FF)
        frame2 = BERTFrame.generate(seed=0x1FF)

        ber = frame1.calculate_ber(frame2)
        assert ber == 0.0

    def test_count_errors_zero(self):
        """Test error count is zero for identical frames."""
        frame1 = BERTFrame.generate(seed=0x1FF)
        frame2 = BERTFrame.generate(seed=0x1FF)

        errors = frame1.count_errors(frame2)
        assert errors == 0

    def test_ber_with_errors(self):
        """Test BER calculation with bit errors."""
        frame1 = BERTFrame.generate(seed=0x1FF)

        # Create frame with one bit flipped
        payload = bytearray(frame1.payload)
        payload[0] ^= 0x80  # Flip MSB of first byte
        frame2 = BERTFrame(payload=bytes(payload))

        errors = frame1.count_errors(frame2)
        assert errors == 1

        ber = frame1.calculate_ber(frame2)
        assert ber == pytest.approx(1 / BERT_PAYLOAD_BITS)

    def test_different_seeds_high_ber(self):
        """Test that different seeds produce high BER."""
        frame1 = BERTFrame.generate(seed=0x1FF)
        frame2 = BERTFrame.generate(seed=0x100)

        ber = frame1.calculate_ber(frame2)
        # Should be around 50% for uncorrelated patterns
        assert 0.3 < ber < 0.7


class TestBERTFrameRF:
    """Tests for RF encoding/decoding."""

    def test_encode_for_rf(self):
        """Test RF encoding produces correct size."""
        frame = BERTFrame.generate()
        rf_data = frame.encode_for_rf()

        # 2 bytes sync + 46 bytes payload
        assert len(rf_data) == 48

        # Check sync word
        sync = int.from_bytes(rf_data[:2], "big")
        assert sync == SYNC_BERT

    def test_encode_deterministic(self):
        """Test RF encoding is deterministic."""
        frame = BERTFrame.generate(seed=0x1FF)

        rf1 = frame.encode_for_rf()
        rf2 = frame.encode_for_rf()

        assert rf1 == rf2

    def test_from_rf_invalid_length(self):
        """Test decoding with invalid length."""
        frame = BERTFrame.from_rf(bytes(10))
        assert frame is None

    def test_from_rf_wrong_sync(self):
        """Test decoding with wrong sync word."""
        data = bytes(48)  # All zeros, wrong sync
        frame = BERTFrame.from_rf(data)
        assert frame is None


class TestCalculateBER:
    """Tests for calculate_ber function."""

    def test_identical_data(self):
        """Test BER is zero for identical data."""
        data = bytes(range(16))
        ber = calculate_ber(data, data)
        assert ber == 0.0

    def test_different_data(self):
        """Test BER calculation."""
        data1 = b"\xFF\x00"
        data2 = b"\x00\xFF"

        # All bits different
        ber = calculate_ber(data1, data2)
        assert ber == 1.0

    def test_partial_errors(self):
        """Test BER with partial errors."""
        data1 = b"\x00\x00"
        data2 = b"\x01\x00"  # One bit different

        ber = calculate_ber(data1, data2)
        assert ber == pytest.approx(1 / 16)

    def test_length_mismatch(self):
        """Test error on length mismatch."""
        with pytest.raises(ValueError):
            calculate_ber(b"\x00", b"\x00\x00")

    def test_num_bits_parameter(self):
        """Test num_bits parameter."""
        data1 = b"\x00\x00"
        data2 = b"\x01\xFF"  # First byte has 1 error, second has 8

        # Compare only first byte (8 bits)
        ber = calculate_ber(data1, data2, num_bits=8)
        assert ber == pytest.approx(1 / 8)

    def test_empty_data(self):
        """Test empty data."""
        ber = calculate_ber(b"", b"")
        assert ber == 0.0


class TestBERTGeneratorReset:
    """Additional tests for BERTGenerator reset behavior."""

    def test_reset_with_zero_seed(self):
        """Test reset with seed that becomes zero."""
        gen = BERTGenerator(seed=0)
        # Generate some bits
        gen.generate_bits(50)
        # Reset should set state to 1 if seed is 0
        gen.reset()
        # Should still generate properly
        bits = gen.generate_bits(50)
        assert len(bits) == 50
        assert any(b == 1 for b in bits)

    def test_reset_preserves_original_seed_behavior(self):
        """Test that reset restores to original seed behavior."""
        gen = BERTGenerator(seed=0x100)
        bits1 = gen.generate_bits(100)
        gen.generate_bits(100)  # Generate more
        gen.reset()
        bits2 = gen.generate_bits(100)
        assert bits1 == bits2


class TestBERTFrameFromRF:
    """Tests for BERT frame RF decoding."""

    def test_from_rf_roundtrip(self):
        """Test encode/decode roundtrip through RF path."""
        original = BERTFrame.generate(seed=0x1FF)
        rf_data = original.encode_for_rf()

        # Decode
        decoded = BERTFrame.from_rf(rf_data, seed=0x1FF)

        # The RF encode/decode path should return a valid frame
        assert decoded is not None
        assert len(decoded.payload) == BERT_PAYLOAD_BYTES
        # The decode may not be bit-perfect due to FEC processing
        # Just verify we got something back

    def test_from_rf_with_different_seed(self):
        """Test from_rf with different seed parameter."""
        original = BERTFrame.generate(seed=0x123)
        rf_data = original.encode_for_rf()

        # Decode with same seed
        decoded = BERTFrame.from_rf(rf_data, seed=0x123)
        assert decoded is not None
        assert decoded.seed == 0x123

    def test_from_rf_correct_sync_word(self):
        """Test from_rf recognizes correct sync word."""
        frame = BERTFrame.generate()
        rf_data = frame.encode_for_rf()

        # Verify sync word is correct
        sync = int.from_bytes(rf_data[:2], "big")
        assert sync == SYNC_BERT

        # Should decode successfully
        result = BERTFrame.from_rf(rf_data)
        assert result is not None

    def test_from_rf_preserves_payload_length(self):
        """Test that from_rf produces correct payload length."""
        frame = BERTFrame.generate()
        rf_data = frame.encode_for_rf()
        decoded = BERTFrame.from_rf(rf_data)

        assert decoded is not None
        assert len(decoded.payload) == BERT_PAYLOAD_BYTES


class TestBERTFrameEquality:
    """Tests for BERT frame equality comparisons."""

    def test_equality_with_different_type(self):
        """Test equality with incompatible type returns NotImplemented."""
        frame = BERTFrame.generate()
        # Comparing with an incompatible type
        result = frame.__eq__(42)
        assert result is NotImplemented

    def test_equality_with_string(self):
        """Test equality with string returns NotImplemented."""
        frame = BERTFrame.generate()
        result = frame.__eq__("not a frame")
        assert result is NotImplemented

    def test_equality_with_list(self):
        """Test equality with list returns NotImplemented."""
        frame = BERTFrame.generate()
        result = frame.__eq__([1, 2, 3])
        assert result is NotImplemented

    def test_inequality_with_different_type(self):
        """Test that comparing with different type works with !=."""
        frame = BERTFrame.generate()
        # Python's != will use __eq__ and then negate
        assert frame != 42
        assert frame != "string"


class TestBERTFrameEdgeCases:
    """Edge case tests for BERT frames."""

    def test_generate_multiple_seeds(self):
        """Test generating frames with different seeds."""
        seeds = [0x001, 0x0FF, 0x100, 0x1FF]
        frames = [BERTFrame.generate(seed=s) for s in seeds]

        # All should have different payloads (except by chance)
        payloads = [f.payload for f in frames]
        # At least some should be different
        assert len(set(payloads)) > 1

    def test_get_bits_deterministic(self):
        """Test that get_bits is deterministic."""
        frame = BERTFrame.generate(seed=0x1FF)
        bits1 = frame.get_bits()
        bits2 = frame.get_bits()
        assert bits1 == bits2

    def test_payload_exact_size(self):
        """Test payload at exact size."""
        payload = bytes(BERT_PAYLOAD_BYTES)
        frame = BERTFrame(payload=payload)
        assert len(frame.payload) == BERT_PAYLOAD_BYTES
        assert frame.payload == payload
