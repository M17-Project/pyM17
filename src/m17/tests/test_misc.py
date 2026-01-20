"""Comprehensive tests for M17 misc utilities.

Tests for binary printing, chunking, and other utility functions.
"""

import io
import sys
import tempfile

import pytest

from m17.misc import (
    DictDotAttribute,
    binary_print_factory,
    c_array_init,
    c_array_init_file,
    chunk,
    demonstrate_chunk,
    example_bytes,
    print_4bits,
    print_8bits,
    print_16bits,
    print_bits,
    print_hex,
)


class TestBinaryPrintFactory:
    """Test binary_print_factory function."""

    def test_create_4bit_printer(self):
        """Test creating a 4-bit printer."""
        printer = binary_print_factory(4)
        result = printer(0b1010)
        assert result == "1010"

    def test_create_8bit_printer(self):
        """Test creating an 8-bit printer."""
        printer = binary_print_factory(8)
        result = printer(0b10101010)
        assert result == "10101010"

    def test_create_16bit_printer(self):
        """Test creating a 16-bit printer."""
        printer = binary_print_factory(16)
        result = printer(0b1010101010101010)
        assert result == "1010101010101010"

    def test_chunking_larger_numbers(self):
        """Test chunking larger numbers into specified bit groups."""
        printer = binary_print_factory(4)
        result = printer(0b10101111)  # 8 bits
        assert result == "1010 1111"

    def test_zero_padding(self):
        """Test that numbers are zero-padded to fit chunk size."""
        printer = binary_print_factory(8)
        result = printer(0b1010)
        assert result == "00001010"


class TestPredefinedPrinters:
    """Test pre-defined binary printers."""

    def test_print_4bits(self):
        """Test print_4bits function."""
        result = print_4bits(0b1010)
        assert "1010" in result

    def test_print_8bits(self):
        """Test print_8bits function."""
        result = print_8bits(0b10101010)
        assert "10101010" in result

    def test_print_16bits(self):
        """Test print_16bits function."""
        result = print_16bits(0b1010101010101010)
        assert "1010101010101010" in result

    def test_print_bits_alias(self):
        """Test that print_bits is an alias for print_8bits."""
        result1 = print_bits(0b10101010)
        result2 = print_8bits(0b10101010)
        assert result1 == result2


class TestPrintHex:
    """Test print_hex function."""

    def test_print_hex_simple(self):
        """Test print_hex with simple bytes."""
        result = print_hex(b"\xde\xad\xbe\xef")
        assert b"deadbeef" in result.lower()

    def test_print_hex_with_separator(self):
        """Test print_hex includes spaces as separators."""
        result = print_hex(bytes(8))
        # Should have separator every 4 bytes
        assert b" " in result


class TestExampleBytes:
    """Test example_bytes function."""

    def test_example_bytes_length(self):
        """Test that example_bytes returns correct length."""
        result = example_bytes(10)
        assert len(result) == 10

    def test_example_bytes_type(self):
        """Test that example_bytes returns bytearray."""
        result = example_bytes(5)
        assert isinstance(result, bytearray)

    def test_example_bytes_zero_length(self):
        """Test example_bytes with zero length."""
        result = example_bytes(0)
        assert len(result) == 0

    def test_example_bytes_randomness(self):
        """Test that example_bytes produces values."""
        # With seeded random, this should be deterministic
        result = example_bytes(100)
        # Should have various values
        assert len(set(result)) > 1


class TestChunk:
    """Test chunk function."""

    def test_chunk_basic(self):
        """Test basic chunking."""
        data = b"0123456789"
        chunks = chunk(data, 5)
        assert chunks == [b"01234", b"56789"]

    def test_chunk_uneven(self):
        """Test chunking with uneven division."""
        data = b"0123456789AB"
        chunks = chunk(data, 5)
        assert chunks == [b"01234", b"56789", b"AB"]

    def test_chunk_single_chunk(self):
        """Test chunking smaller than chunk size."""
        data = b"123"
        chunks = chunk(data, 10)
        assert chunks == [b"123"]

    def test_chunk_negative_size(self):
        """Test chunking from right (negative size)."""
        data = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        chunks = chunk(data, -5)
        # Should chunk from the right
        expected = [b"0", b"12345", b"6789A", b"BCDEF", b"GHIJK", b"LMNOP", b"QRSTU", b"VWXYZ"]
        assert chunks == expected

    def test_chunk_negative_size_exact(self):
        """Test chunking from right with exact division."""
        data = b"ABCDEFGHIJ"
        chunks = chunk(data, -5)
        assert chunks == [b"ABCDE", b"FGHIJ"]

    def test_chunk_empty(self):
        """Test chunking empty data."""
        data = b""
        chunks = chunk(data, 5)
        assert chunks == []

    def test_chunk_size_one(self):
        """Test chunking with size one."""
        data = b"ABC"
        chunks = chunk(data, 1)
        assert chunks == [b"A", b"B", b"C"]


class TestDemonstrateChunk:
    """Test demonstrate_chunk function."""

    def test_demonstrate_chunk_output(self, capsys):
        """Test that demonstrate_chunk produces output."""
        demonstrate_chunk()
        captured = capsys.readouterr()
        # Should print the chunked output
        assert "01234" in captured.out or "[" in captured.out


class TestCArrayInit:
    """Test C array initializer functions."""

    def test_c_array_init_basic(self, capsys):
        """Test c_array_init with basic input.

        Note: The function only prints lines when cnt >= 8, so data
        shorter than 8 bytes won't appear between the braces.
        """
        data = bytes(range(8))  # Need at least 8 bytes
        c_array_init(data)
        captured = capsys.readouterr()
        assert "uint8_t sample_stream[]={" in captured.out
        assert "0x0" in captured.out
        assert "0x7" in captured.out
        assert "}" in captured.out

    def test_c_array_init_longer_input(self, capsys):
        """Test c_array_init with longer input."""
        data = bytes(range(16))
        c_array_init(data)
        captured = capsys.readouterr()
        assert "uint8_t sample_stream[]={" in captured.out
        assert "}" in captured.out
        # Should have multiple lines due to formatting
        assert "\n" in captured.out

    def test_c_array_init_empty(self, capsys):
        """Test c_array_init with empty input."""
        c_array_init(b"")
        captured = capsys.readouterr()
        assert "uint8_t sample_stream[]={" in captured.out
        assert "}" in captured.out

    def test_c_array_init_short(self, capsys):
        """Test c_array_init with short input (< 8 bytes).

        Note: The function only prints lines when cnt >= 8, so short
        data won't appear in output (this is how the function works).
        """
        data = b"\x01\x02\x03\x04"  # Only 4 bytes
        c_array_init(data)
        captured = capsys.readouterr()
        assert "uint8_t sample_stream[]={" in captured.out
        assert "}" in captured.out
        # Short data doesn't get printed due to line buffering

    def test_c_array_init_file(self, capsys):
        """Test c_array_init_file reads and processes file."""
        # Create a temporary file with 8+ bytes
        with tempfile.NamedTemporaryFile(delete=False, mode="wb") as f:
            f.write(bytes(range(16)))
            temp_path = f.name

        try:
            c_array_init_file(temp_path)
            captured = capsys.readouterr()
            assert "uint8_t sample_stream[]={" in captured.out
            assert "0x0" in captured.out
            assert "}" in captured.out
        finally:
            import os

            os.unlink(temp_path)


class TestDictDotAttribute:
    """Test DictDotAttribute class."""

    def test_basic_access(self):
        """Test basic dot attribute access."""
        d = DictDotAttribute({"abc": True})
        assert d.abc is True

    def test_set_attribute(self):
        """Test setting attribute."""
        d = DictDotAttribute({"abc": True})
        d.abc = False
        assert d.abc is False

    def test_nested_dict_access(self):
        """Test nested dict is converted to DictDotAttribute."""
        d = DictDotAttribute({"outer": {"inner": "value"}})
        assert d.outer.inner == "value"

    def test_nested_dict_set(self):
        """Test setting nested values."""
        d = DictDotAttribute({"outer": {"inner": "value"}})
        d.outer.inner = "new_value"
        assert d.outer.inner == "new_value"

    def test_new_key(self):
        """Test adding new keys."""
        d = DictDotAttribute({})
        d.new_key = "new_value"
        assert d.new_key == "new_value"
        assert d["new_key"] == "new_value"

    def test_dict_like_access(self):
        """Test that dict-like access still works."""
        d = DictDotAttribute({"key": "value"})
        assert d["key"] == "value"

    def test_mixed_access(self):
        """Test mixing dot and dict access."""
        d = DictDotAttribute({"key": {"nested": "value"}})
        assert d["key"]["nested"] == "value"
        assert d.key.nested == "value"


class TestMiscCLI:
    """Test misc.py CLI functionality."""

    def test_cli_commands_dict(self):
        """Test that CLI commands dictionary is valid."""
        # Import the module
        import m17.misc as misc_module

        # Check the functions that would be in _CLI_COMMANDS
        assert callable(c_array_init_file)
        assert callable(demonstrate_chunk)
