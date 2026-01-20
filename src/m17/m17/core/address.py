"""M17 Address Encoding/Decoding

Handles Base-40 callsign encoding per M17 specification v2.0.3.

Features:
- Standard callsign encoding (up to 9 characters)
- Hash-prefixed address support (#-prefixed callsigns)
- Broadcast address (@ALL)
- Dataclass-based implementation with full type hints

Address Ranges:
- Regular callsigns: 0 to 40^9-1 (262,143,999,999)
- Hash-prefixed: 40^9 to 40^9+40^8-1
- Broadcast (@ALL): 0xFFFFFFFFFFFF
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from m17.core.constants import (
    BROADCAST_ADDRESS,
    CALLSIGN_ALPHABET,
    HASH_ADDRESS_MAX,
    HASH_ADDRESS_MIN,
    MAX_CALLSIGN_VALUE,
)

__all__ = ["Address", "encode_callsign", "decode_callsign"]


@dataclass(frozen=True, slots=True)
class Address:
    """M17 Address representation.

    Can be instantiated with either a numeric address or a callsign string.

    Examples
    --------
        >>> addr = Address(callsign="W2FBI")
        >>> addr.callsign
        'W2FBI'
        >>> hex(addr.numeric)
        '0x161ae1f'

        >>> addr2 = Address(numeric=0x161ae1f)
        >>> addr2.callsign
        'W2FBI'

        >>> broadcast = Address(callsign="@ALL")
        >>> broadcast.is_broadcast
        True
    """

    _value: int  # Internal numeric value (6 bytes max)

    def __init__(
        self,
        *,
        addr: Union[int, bytes, None] = None,
        callsign: Union[str, None] = None,
        numeric: Union[int, None] = None,
    ) -> None:
        """Create an Address from either numeric value or callsign.

        Args:
        ----
            addr: Numeric address as int or 6-byte big-endian bytes (legacy).
            callsign: Callsign string to encode.
            numeric: Numeric address as int (preferred over addr).

        Raises:
        ------
            ValueError: If neither or both addr/callsign provided, or invalid values.
        """
        # Handle the numeric parameter
        if numeric is not None:
            addr = numeric

        if addr is None and callsign is None:
            raise ValueError("Must provide either addr/numeric or callsign")

        if addr is not None and callsign is not None:
            raise ValueError("Provide only one of addr/numeric or callsign, not both")

        if callsign is not None:
            value = encode_callsign(callsign)
        elif isinstance(addr, bytes):
            if len(addr) != 6:
                raise ValueError(f"Address bytes must be 6 bytes, got {len(addr)}")
            value = int.from_bytes(addr, "big")
        elif isinstance(addr, int):
            if not 0 <= addr <= 0xFFFFFFFFFFFF:
                raise ValueError(f"Address must be 0-0xFFFFFFFFFFFF, got {hex(addr)}")
            value = addr
        else:
            raise TypeError(f"Invalid addr type: {type(addr)}")

        object.__setattr__(self, "_value", value)

    @property
    def numeric(self) -> int:
        """Get the numeric address value."""
        return self._value

    @property
    def addr(self) -> bytes:
        """Get the address as 6-byte big-endian bytes (legacy compatibility)."""
        return self._value.to_bytes(6, "big")

    @property
    def callsign(self) -> str:
        """Get the decoded callsign string."""
        return decode_callsign(self._value)

    @property
    def is_broadcast(self) -> bool:
        """Check if this is the broadcast address (@ALL)."""
        return self._value == BROADCAST_ADDRESS

    @property
    def is_hash_address(self) -> bool:
        """Check if this is a hash-prefixed address."""
        return HASH_ADDRESS_MIN <= self._value <= HASH_ADDRESS_MAX

    @property
    def is_regular(self) -> bool:
        """Check if this is a regular callsign address."""
        return self._value <= MAX_CALLSIGN_VALUE

    def __bytes__(self) -> bytes:
        """Return 6-byte big-endian representation."""
        return self.addr

    def __int__(self) -> int:
        """Return numeric value."""
        return self._value

    def __index__(self) -> int:
        """Support use in hex(), bin(), etc."""
        return self._value

    def __str__(self) -> str:
        """Return callsign string representation."""
        return self.callsign

    def __repr__(self) -> str:
        """Return detailed representation."""
        return f"Address(callsign={self.callsign!r}, numeric=0x{self._value:012x})"

    def __eq__(self, other: object) -> bool:
        """Compare with another Address, int, bytes, or string."""
        if isinstance(other, Address):
            return self._value == other._value
        if isinstance(other, int):
            return self._value == other
        if isinstance(other, bytes):
            if len(other) == 6:
                return self._value == int.from_bytes(other, "big")
            return False
        if isinstance(other, str):
            try:
                return self._value == encode_callsign(other)
            except ValueError:
                return False
        return NotImplemented

    def __hash__(self) -> int:
        """Return hash for use in sets/dicts."""
        return hash(self._value)

    # Legacy static methods for backward compatibility
    @staticmethod
    def encode(callsign: str) -> bytes:
        """Encode a callsign to 6-byte address (legacy method).

        Args:
        ----
            callsign: Callsign string.

        Returns:
        -------
            6-byte big-endian address.
        """
        return encode_callsign(callsign).to_bytes(6, "big")

    @staticmethod
    def decode(addr: Union[int, bytes]) -> str:
        """Decode an address to callsign string (legacy method).

        Args:
        ----
            addr: Numeric address or 6-byte bytes.

        Returns:
        -------
            Callsign string.
        """
        if isinstance(addr, bytes):
            addr = int.from_bytes(addr, "big")
        return decode_callsign(addr)


def encode_callsign(callsign: str) -> int:
    """Encode a callsign string to numeric address.

    Supports:
    - Regular callsigns (A-Z, 0-9, space, -, /, .)
    - Broadcast address (@ALL)
    - Hash-prefixed callsigns (#SOMETHING)

    Args:
    ----
        callsign: Callsign string (max 9 chars for regular, 8 for hash-prefixed).

    Returns:
    -------
        48-bit numeric address.

    Raises:
    ------
        ValueError: If callsign is invalid or too long.

    Examples:
    --------
        >>> hex(encode_callsign("W2FBI"))
        '0x161ae1f'
        >>> encode_callsign("@ALL") == 0xFFFFFFFFFFFF
        True
    """
    callsign = callsign.upper().strip()

    # Handle broadcast address
    if callsign == "@ALL":
        return BROADCAST_ADDRESS

    # Handle hash-prefixed addresses
    if callsign.startswith("#"):
        return _encode_hash_callsign(callsign[1:])

    # Regular callsign encoding
    if len(callsign) > 9:
        raise ValueError(f"Callsign too long: {callsign!r} (max 9 chars)")

    num = 0
    for char in reversed(callsign):
        try:
            char_idx = CALLSIGN_ALPHABET.index(char)
        except ValueError as err:
            raise ValueError(f"Invalid character in callsign: {char!r}") from err
        num = num * 40 + char_idx

    if num > MAX_CALLSIGN_VALUE:
        raise ValueError(f"Encoded callsign exceeds maximum value: {callsign!r}")

    return num


def _encode_hash_callsign(callsign: str) -> int:
    """Encode a hash-prefixed callsign (without the # prefix).

    Hash-prefixed addresses use a reduced range for the callsign
    portion (max 8 chars) offset by 40^9.

    Args:
    ----
        callsign: Callsign without the # prefix.

    Returns:
    -------
        Numeric address in hash-address range.
    """
    if len(callsign) > 8:
        raise ValueError(f"Hash callsign too long: #{callsign!r} (max 8 chars after #)")

    num = 0
    for char in reversed(callsign):
        try:
            char_idx = CALLSIGN_ALPHABET.index(char)
        except ValueError as err:
            raise ValueError(f"Invalid character in callsign: {char!r}") from err
        num = num * 40 + char_idx

    return HASH_ADDRESS_MIN + num


def decode_callsign(addr: int) -> str:
    """Decode a numeric address to callsign string.

    Args:
    ----
        addr: 48-bit numeric address.

    Returns:
    -------
        Callsign string.

    Raises:
    ------
        ValueError: If address is invalid.

    Examples:
    --------
        >>> decode_callsign(0x161ae1f)
        'W2FBI'
        >>> decode_callsign(0xFFFFFFFFFFFF)
        '@ALL'
    """
    # Handle broadcast address
    if addr == BROADCAST_ADDRESS:
        return "@ALL"

    # Handle hash-prefixed addresses
    if HASH_ADDRESS_MIN <= addr <= HASH_ADDRESS_MAX:
        return "#" + _decode_base40(addr - HASH_ADDRESS_MIN)

    # Handle regular addresses
    if addr > MAX_CALLSIGN_VALUE:
        raise ValueError(f"Invalid address: {hex(addr)}")

    return _decode_base40(addr)


def _decode_base40(num: int) -> str:
    """Decode a base-40 encoded number to string.

    Args:
    ----
        num: Base-40 encoded number.

    Returns:
    -------
        Decoded string.
    """
    if num == 0:
        return ""

    chars = []
    while num > 0:
        idx = num % 40
        chars.append(CALLSIGN_ALPHABET[idx])
        num //= 40

    return "".join(chars)
