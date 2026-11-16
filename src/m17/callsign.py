"""Callsign (address) encoding: base-40 text to 48-bit values and back.

Up to 9 characters from ``" ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-/."``,
lowercase is accepted. A leading ``#`` selects the hash address space
(8 more characters), ``@ALL`` is the broadcast address. Other characters
encode as a space, as the specification requires.
"""

CHARSET = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-/."
BROADCAST = 0xFFFFFFFFFFFF
_U40_9 = 40**9  # start of the hash address space
_U40_9_8 = 40**9 + 40**8  # start of the reserved space


def encode_callsign(text: str) -> int:
    """Encode a callsign to its 48-bit value. Raises ValueError above 9 characters."""
    if len(text) > 9:
        raise ValueError(f"callsign longer than 9 characters: {text!r}")
    if text == "@ALL":
        return BROADCAST
    start = 1 if text.startswith("#") else 0
    value = 0
    for c in reversed(text[start:].upper()):
        value = value * 40 + max(CHARSET.find(c), 0)
    return value + (_U40_9 if start else 0)


def decode_callsign(value: int) -> str:
    """Decode a 48-bit value. Returns "" for 0 and for the reserved range."""
    prefix = ""
    if value >= _U40_9:
        if value == BROADCAST:
            return "@ALL"
        if value >= _U40_9_8:
            return ""
        prefix, value = "#", value - _U40_9
    chars = []
    while value:
        value, digit = divmod(value, 40)
        chars.append(CHARSET[digit])
    return prefix + "".join(chars)


def callsign_to_bytes(text: str) -> bytes:
    """Encode a callsign to the 6 big-endian bytes used in frames."""
    return encode_callsign(text).to_bytes(6, "big")


def callsign_from_bytes(data: bytes) -> str:
    """Decode 6 big-endian bytes to a callsign."""
    return decode_callsign(int.from_bytes(data[:6], "big"))
