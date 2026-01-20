"""Tests for M17 CRC-16 implementation.

Test vectors from M17 specification.
"""


from m17.core.crc import M17_CRC_POLY, crc_m17, crc_m17_bytes, verify_crc


class TestCRC:
    """Test CRC-16 calculation."""

    def test_crc_polynomial(self):
        """Verify CRC polynomial constant."""
        assert M17_CRC_POLY == 0x5935

    def test_crc_empty(self):
        """CRC of empty data should be 0xFFFF (initial value)."""
        assert crc_m17(b"") == 0xFFFF

    def test_crc_single_byte(self):
        """Test CRC of single byte 'A'."""
        assert crc_m17(b"A") == 0x206E

    def test_crc_check_sequence(self):
        """Test CRC with standard check sequence '123456789'."""
        assert crc_m17(b"123456789") == 0x772B

    def test_crc_bytes_output(self):
        """Test CRC bytes output format."""
        result = crc_m17_bytes(b"123456789")
        assert result == bytes([0x77, 0x2B])
        assert len(result) == 2

    def test_crc_verify_valid(self):
        """Test CRC verification with valid data."""
        data = b"123456789" + bytes([0x77, 0x2B])
        assert verify_crc(data) is True

    def test_crc_verify_invalid(self):
        """Test CRC verification with invalid data."""
        data = b"123456789" + bytes([0x00, 0x00])
        assert verify_crc(data) is False

    def test_crc_incremental(self):
        """Test that CRC calculation is consistent."""
        data1 = b"Hello"
        data2 = b"World"
        combined = data1 + data2

        # CRC of combined should match
        crc1 = crc_m17(combined)
        crc2 = crc_m17(b"HelloWorld")
        assert crc1 == crc2

    def test_crc_all_zeros(self):
        """Test CRC of all zeros."""
        result = crc_m17(bytes(10))
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFF

    def test_crc_all_ones(self):
        """Test CRC of all 0xFF bytes."""
        result = crc_m17(bytes([0xFF] * 10))
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFF

    def test_crc_lsf_size(self):
        """Test CRC calculation for LSF-sized data (28 bytes)."""
        lsf_data = bytes(28)
        result = crc_m17(lsf_data)
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFF

    def test_crc_bytearray(self):
        """Test CRC works with bytearray input."""
        data = bytearray(b"123456789")
        assert crc_m17(data) == 0x772B


class TestCRCEdgeCases:
    """Test edge cases for CRC."""

    def test_crc_single_zero(self):
        """Test CRC of single zero byte."""
        result = crc_m17(b"\x00")
        assert isinstance(result, int)

    def test_crc_single_ff(self):
        """Test CRC of single 0xFF byte."""
        result = crc_m17(b"\xff")
        assert isinstance(result, int)

    def test_crc_alternating(self):
        """Test CRC of alternating bits."""
        result = crc_m17(b"\xaa\x55\xaa\x55")
        assert isinstance(result, int)

    def test_crc_long_data(self):
        """Test CRC of longer data."""
        data = bytes(range(256)) * 4  # 1024 bytes
        result = crc_m17(data)
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFF
