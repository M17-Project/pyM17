"""
M17 Addressing (Legacy Module)

.. deprecated:: 0.1.1
    This module is deprecated. Use :mod:`m17.core.address` instead.

    Example migration::

        # Old import (deprecated)
        from m17.address import Address

        # New import (preferred)
        from m17.core.address import Address
"""
from __future__ import annotations

import sys
import struct
import warnings
from typing import Any, Optional, Union


from m17.const import CALLSIGN_ALPHABET, M17_ADDRESS_LAYOUT_STRUCT
M17AddressLayout = struct.Struct(M17_ADDRESS_LAYOUT_STRUCT)

# Emit deprecation warning on module import
warnings.warn(
    "m17.address is deprecated and will be removed in v1.0. "
    "Use m17.core.address instead.",
    DeprecationWarning,
    stacklevel=2,
)


AddressParam = Union[int, bytes]


class Address:
    """
    Call with either "addr" or "callsign" to instantiate, e.g.

    >>> from m17.address import Address
    >>> Address(callsign="W2FBI").addr
    23178783

    You can get the hex version using Python's hex()
    >>> hex( 23178783 )
    '0x161ae1f'

    >>> from m17.address import Address
    >>> Address(addr=23178783).callsign
    'W2FBI'

    You can also use it directly, e.g.
    >>> from m17.address import Address
    >>> Address.encode("W2FBI")
    23178783
    >>> Address.decode(23178783)
    'W2FBI'

    Equality tests work like you might hope:
    >>> Address(callsign="W2FBI") == "W2FBI"
    True
    >>> Address(callsign="W2FBI") == 23178783
    True
    >>> Address(callsign="W2FBI") == Address.encode("W2FBI")
    True
    >>> Address(callsign="W2FBI") == Address(addr=23178783)
    True

    """

    def __init__(
        self,
        addr: Optional[Union[bytes, int]] = None,
        callsign: Optional[str] = None
    ) -> None:
        if addr is None and callsign is None:
            raise ValueError("Must provide either addr or callsign")

        self.callsign = callsign.upper() if callsign else self.decode(addr)  # type: ignore[arg-type]
        addr_result = addr if addr else self.encode(callsign)  # type: ignore[arg-type]

        if isinstance(addr_result, int):
            self.addr = addr_result.to_bytes(6, "big")
        else:
            self.addr = addr_result

    def __str__(self) -> str:
        int_addr = int.from_bytes(self.addr, "big")
        return f"{self.callsign} == 0x{int_addr:06x}"

    def __bytes__(self) -> bytes:
        return M17AddressLayout.pack(*self.addr)

    def __index__(self) -> int:
        return int.from_bytes(self.addr, "big")

    def __eq__(self, compareto: object) -> bool:
        if isinstance(compareto, str):
            return int(compareto) == int.from_bytes(self.addr, "big") if compareto.isdigit() else compareto.upper() == self.callsign

        if isinstance(compareto, int):
            return compareto == int(self)

        if isinstance(compareto, Address):
            return int(self) == int(compareto)

        return False

    @staticmethod
    def to_dmr_id(something: Any) -> None:
        """
        Convert a callsign to a DMR ID
        """
        # if no db:
        # url = "https://database.radioid.net/static/users.json"
        # requests.get()
        # if db but not found, _check once_ using https://database.radioid.net/api/dmr/user/?id=3125404
        # return an Address encoded for DMR using database lookup?
        # or jsut the ID as an int?
        ...

    @staticmethod
    def from_dmr_id(dmr_int: int) -> None:
        """
        Convert a DMR ID to a callsign
        """
        # return an Address encoded for callsign using dmr database lookup to get callsign
        ...

    def is_dmr_id(self) -> bool:
        """
        Is this a DMR ID?
        """
        return self.callsign.startswith("D") and self.callsign[1:].isdigit()

    def is_dmr_talkgroup(self) -> bool:
        """
        Is this a DMR talkgroup?
        """
        return self.is_brandmeister_tg()

    def is_brandmeister_tg(self) -> bool:
        """
        Is this a Brandmeister talkgroup?
        """
        return self.callsign.startswith("BM") and self.callsign[1:].isdigit()

    def is_dstar_reflector(self) -> bool:
        """
        Is this a D-Star reflector?
        """
        return self.callsign.startswith("REF")

    @staticmethod
    def encode(callsign: str) -> bytes:
        """
        Encode a callsign into an address
        """
        num = 0
        for char in callsign.upper()[::-1]:
            charidx = CALLSIGN_ALPHABET.index(char)
            num *= 40
            num += charidx
            if num >= 40 ** 9:
                raise ValueError("Invalid callsign")
        return num.to_bytes(6, "big")

    @staticmethod
    def decode(addr: AddressParam) -> str:
        """
        Decode an address into a callsign
        """
        num: int
        if isinstance(addr, bytes):
            num = int.from_bytes(addr, "big")
        else:
            num = addr

        if num >= 40 ** 9:
            raise ValueError("Invalid address")
        chars = []
        while num > 0:
            idx = int(num % 40)
            c = CALLSIGN_ALPHABET[idx]
            chars.append(c)
            # print(num,idx,c)
            num //= 40
        callsign = "".join(chars)
        return callsign


def show_help() -> None:
    """
    Show help
    """
    print("""
Provide callsigns on the command line and they will be translated into M17 addresses
    """)


if __name__ == "__main__":
    if len(sys.argv) <= 1:
        show_help()
    else:
        for each in sys.argv[1:]:
            print(Address(callsign=each))
