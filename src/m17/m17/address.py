"""
M17 Addressing
"""
import sys
import struct
from typing import Union


from m17.const import CALLSIGN_ALPHABET, M17_ADDRESS_LAYOUT_STRUCT
M17AddressLayout = struct.Struct(M17_ADDRESS_LAYOUT_STRUCT)


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

    def __init__(self, addr: bytes=None, callsign: str=None):
        if addr is None and callsign is None:
            raise ValueError("Must provide either addr or callsign")

        self.callsign = callsign.upper() if callsign else self.decode(addr)
        self.addr = addr if addr else self.encode(callsign)

        if isinstance(self.addr, int):
            self.addr = self.addr.to_bytes(6, "big")

    def __str__(self):
        int_addr = int.from_bytes(self.addr, "big")
        return f"{self.callsign} == 0x{int_addr:06x}"

    def __bytes__(self):
        return M17AddressLayout.pack(*self.addr)

    def __index__(self):
        return int.from_bytes(self.addr, "big")

    def __eq__(self, compareto):
        if isinstance(compareto, str):
            return int(compareto) == self.addr if compareto.isdigit() else compareto.upper() == self.callsign

        if isinstance(compareto, int):
            return compareto == int(self)

        if isinstance(compareto, Address):
            return int(self) == int(compareto)

        return False

    @staticmethod
    def to_dmr_id(something):
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
    def from_dmr_id(dmr_int):
        """
        Convert a DMR ID to a callsign
        """
        # return an Address encoded for callsign using dmr database lookup to get callsign
        ...

    def is_dmr_id(self):
        """
        Is this a DMR ID?
        """
        return self.callsign.startswith("D") and self.callsign[1:].isdigit()

    def is_dmr_talkgroup(self):
        """
        Is this a DMR talkgroup?
        """
        return self.is_brandmeister_tg()

    def is_brandmeister_tg(self):
        """
        Is this a Brandmeister talkgroup?
        """
        return self.callsign.startswith("BM") and self.callsign[1:].isdigit()

    def is_dstar_reflector(self):
        """
        Is this a D-Star reflector?
        """
        return self.callsign.startswith("REF")

    @staticmethod
    def encode(callsign):
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
    def decode(addr: AddressParam):
        """
        Decode an address into a callsign
        """
        num = addr
        if isinstance(addr, bytes):
            num = int.from_bytes(addr, "big")

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


def show_help():
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
