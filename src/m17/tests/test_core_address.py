"""Tests for M17 Address encoding/decoding.

Tests both the new dataclass-based Address and legacy functionality.
"""

import pytest

from m17.core.address import Address, decode_callsign, encode_callsign
from m17.core.constants import BROADCAST_ADDRESS, HASH_ADDRESS_MAX, HASH_ADDRESS_MIN


class TestAddressEncoding:
    """Test address encoding."""

    def test_encode_simple(self):
        """Test encoding a simple callsign."""
        result = encode_callsign("W2FBI")
        assert result == 0x161AE1F

    def test_encode_with_suffix(self):
        """Test encoding callsign with suffix."""
        result = encode_callsign("W2FBI-M")
        assert isinstance(result, int)
        assert result > 0

    def test_encode_numeric_suffix(self):
        """Test encoding callsign with numeric suffix."""
        result = encode_callsign("W2FBI-9")
        assert isinstance(result, int)

    def test_encode_lowercase_normalized(self):
        """Test that lowercase is normalized to uppercase."""
        result1 = encode_callsign("w2fbi")
        result2 = encode_callsign("W2FBI")
        assert result1 == result2

    def test_encode_broadcast(self):
        """Test encoding broadcast address."""
        result = encode_callsign("@ALL")
        assert result == BROADCAST_ADDRESS

    def test_encode_hash_prefix(self):
        """Test encoding hash-prefixed callsign."""
        result = encode_callsign("#TEST")
        assert HASH_ADDRESS_MIN <= result <= HASH_ADDRESS_MAX

    def test_encode_invalid_char(self):
        """Test that invalid characters raise error."""
        with pytest.raises(ValueError):
            encode_callsign("W2FBI!")

    def test_encode_too_long(self):
        """Test that too-long callsign raises error."""
        with pytest.raises(ValueError):
            encode_callsign("W2FBI-TOOLONG")


class TestAddressDecoding:
    """Test address decoding."""

    def test_decode_simple(self):
        """Test decoding a simple callsign."""
        result = decode_callsign(0x161AE1F)
        assert result == "W2FBI"

    def test_decode_broadcast(self):
        """Test decoding broadcast address."""
        result = decode_callsign(BROADCAST_ADDRESS)
        assert result == "@ALL"

    def test_decode_hash_prefix(self):
        """Test decoding hash-prefixed address."""
        # First encode, then decode
        encoded = encode_callsign("#TEST")
        decoded = decode_callsign(encoded)
        assert decoded == "#TEST"

    def test_decode_zero(self):
        """Test decoding zero address."""
        result = decode_callsign(0)
        assert result == ""


class TestAddressClass:
    """Test Address class."""

    def test_create_from_callsign(self):
        """Test creating Address from callsign."""
        addr = Address(callsign="W2FBI")
        assert addr.callsign == "W2FBI"
        assert addr.numeric == 0x161AE1F

    def test_create_from_numeric(self):
        """Test creating Address from numeric value."""
        addr = Address(numeric=0x161AE1F)
        assert addr.callsign == "W2FBI"
        assert addr.numeric == 0x161AE1F

    def test_create_from_bytes(self):
        """Test creating Address from bytes."""
        addr_bytes = (0x161AE1F).to_bytes(6, "big")
        addr = Address(addr=addr_bytes)
        assert addr.callsign == "W2FBI"

    def test_bytes_conversion(self):
        """Test bytes conversion."""
        addr = Address(callsign="W2FBI")
        addr_bytes = bytes(addr)
        assert len(addr_bytes) == 6
        assert addr_bytes == addr.addr

    def test_int_conversion(self):
        """Test int conversion."""
        addr = Address(callsign="W2FBI")
        assert int(addr) == 0x161AE1F

    def test_str_conversion(self):
        """Test string conversion."""
        addr = Address(callsign="W2FBI")
        assert str(addr) == "W2FBI"

    def test_equality_same_callsign(self):
        """Test equality with same callsign."""
        addr1 = Address(callsign="W2FBI")
        addr2 = Address(callsign="W2FBI")
        assert addr1 == addr2

    def test_equality_with_string(self):
        """Test equality with string."""
        addr = Address(callsign="W2FBI")
        assert addr == "W2FBI"

    def test_equality_with_int(self):
        """Test equality with int."""
        addr = Address(callsign="W2FBI")
        assert addr == 0x161AE1F

    def test_equality_with_bytes(self):
        """Test equality with bytes."""
        addr = Address(callsign="W2FBI")
        addr_bytes = (0x161AE1F).to_bytes(6, "big")
        assert addr == addr_bytes

    def test_is_broadcast(self):
        """Test is_broadcast property."""
        addr = Address(callsign="@ALL")
        assert addr.is_broadcast is True

        addr2 = Address(callsign="W2FBI")
        assert addr2.is_broadcast is False

    def test_is_hash_address(self):
        """Test is_hash_address property."""
        addr = Address(callsign="#TEST")
        assert addr.is_hash_address is True

        addr2 = Address(callsign="W2FBI")
        assert addr2.is_hash_address is False

    def test_is_regular(self):
        """Test is_regular property."""
        addr = Address(callsign="W2FBI")
        assert addr.is_regular is True

        addr2 = Address(callsign="@ALL")
        assert addr2.is_regular is False

    def test_hashable(self):
        """Test that Address is hashable (usable in sets/dicts)."""
        addr = Address(callsign="W2FBI")
        addr_set = {addr}
        assert addr in addr_set

    def test_immutable(self):
        """Test that Address is immutable."""
        addr = Address(callsign="W2FBI")
        with pytest.raises(AttributeError):
            addr._value = 0


class TestAddressLegacy:
    """Test legacy Address methods for backward compatibility."""

    def test_legacy_encode_static(self):
        """Test legacy static encode method."""
        result = Address.encode("W2FBI")
        expected = (0x161AE1F).to_bytes(6, "big")
        assert result == expected

    def test_legacy_decode_static_int(self):
        """Test legacy static decode method with int."""
        result = Address.decode(0x161AE1F)
        assert result == "W2FBI"

    def test_legacy_decode_static_bytes(self):
        """Test legacy static decode method with bytes."""
        addr_bytes = (0x161AE1F).to_bytes(6, "big")
        result = Address.decode(addr_bytes)
        assert result == "W2FBI"

    def test_legacy_addr_parameter(self):
        """Test legacy addr parameter."""
        addr_bytes = (0x161AE1F).to_bytes(6, "big")
        addr = Address(addr=addr_bytes)
        assert addr.callsign == "W2FBI"


class TestAddressEdgeCases:
    """Test edge cases for Address."""

    def test_max_length_callsign(self):
        """Test 9-character callsign (maximum)."""
        addr = Address(callsign="W2FBI-ABC")
        assert len(addr.callsign) <= 9

    def test_special_characters(self):
        """Test callsign with special characters."""
        addr = Address(callsign="W2FBI/P")
        assert "/" in addr.callsign

    def test_space_in_callsign(self):
        """Test callsign with space (trimmed in alphabet)."""
        # Space is position 0 in alphabet
        addr = Address(callsign=" W2FBI")
        # Leading space should be handled

    def test_must_provide_one(self):
        """Test that at least one parameter must be provided."""
        with pytest.raises(ValueError):
            Address()

    def test_cannot_provide_both(self):
        """Test that callsign and numeric cannot both be provided."""
        with pytest.raises(ValueError):
            Address(callsign="W2FBI", numeric=0x161AE1F)

    def test_invalid_bytes_length(self):
        """Test that wrong bytes length raises error."""
        with pytest.raises(ValueError, match="must be 6 bytes"):
            Address(addr=b"\x00\x00\x00")  # Only 3 bytes

    def test_addr_out_of_range(self):
        """Test that out of range address raises error."""
        with pytest.raises(ValueError, match="must be 0-0xFFFFFFFFFFFF"):
            Address(addr=0x1000000000000)  # 7 bytes worth

    def test_invalid_addr_type(self):
        """Test that invalid addr type raises error."""
        with pytest.raises(TypeError, match="Invalid addr type"):
            Address(addr=[1, 2, 3])  # type: ignore

    def test_index_for_hex(self):
        """Test __index__ method allows use with hex()."""
        addr = Address(callsign="W2FBI")
        assert hex(addr) == "0x161ae1f"

    def test_index_for_bin(self):
        """Test __index__ method allows use with bin()."""
        addr = Address(callsign="W2FBI")
        result = bin(addr)
        assert result.startswith("0b")

    def test_repr(self):
        """Test __repr__ method."""
        addr = Address(callsign="W2FBI")
        r = repr(addr)
        assert "Address" in r
        assert "W2FBI" in r
        assert "0x" in r

    def test_equality_wrong_bytes_length(self):
        """Test equality with bytes of wrong length returns False."""
        addr = Address(callsign="W2FBI")
        assert (addr == b"\x00\x00\x01") is False  # 3 bytes

    def test_equality_invalid_string(self):
        """Test equality with invalid callsign string returns False."""
        addr = Address(callsign="W2FBI")
        # Invalid character should return False, not raise
        assert (addr == "W2FBI$$") is False

    def test_equality_not_implemented(self):
        """Test equality with unsupported type."""
        addr = Address(callsign="W2FBI")
        # Lists and dicts should return False (via NotImplemented)
        assert (addr == [1, 2, 3]) is False
        assert (addr == {"test": 1}) is False


class TestHashAddressEdgeCases:
    """Test hash address edge cases."""

    def test_hash_callsign_too_long(self):
        """Test hash callsign > 8 chars after # raises error."""
        with pytest.raises(ValueError, match="Hash callsign too long"):
            encode_callsign("#ABCDEFGHI")  # 9 chars after #

    def test_hash_callsign_invalid_char(self):
        """Test hash callsign with invalid char raises error."""
        with pytest.raises(ValueError, match="Invalid character"):
            encode_callsign("#TEST$")


class TestDecodeAddressErrors:
    """Test decode_callsign error cases."""

    def test_decode_invalid_address_range(self):
        """Test decoding address in invalid range raises error."""
        # Address between HASH_ADDRESS_MAX and BROADCAST_ADDRESS is invalid
        # HASH_ADDRESS_MAX = 40^9 + 40^8 - 1 = 268,697,599,999
        # BROADCAST_ADDRESS = 0xFFFFFFFFFFFF = 281,474,976,710,655
        invalid_addr = HASH_ADDRESS_MAX + 1000
        with pytest.raises(ValueError, match="Invalid address"):
            decode_callsign(invalid_addr)
