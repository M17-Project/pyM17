import sys
import string
import unittest

import bitstruct

from .misc import _x
callsign_alphabet = " " + string.ascii_uppercase + string.digits + "-/." 
#"." is TBD
# print("Alphabet: %s"%(callsign_alphabet))
# print("len(Alphabet): %d"%(len(callsign_alphabet)))


class test_address(unittest.TestCase):
    def setUp(self):
        self.me = Address(callsign="W2FBI")
        self.ref = Address(callsign="XLX307 D")
    def test_string_compare(self):
        self.assertEqual(self.me, "W2FBI")
    def test_num_compare(self):
        self.assertEqual(self.me, 23178783)
    def test_compare(self):
        me2 = Address(addr=23178783)
        self.assertEqual(self.me, me2)
    def test_not_equal(self):
        me2 = Address(addr=23178784)
        self.assertNotEqual(self.me,me2)
    def test_bytes(self):
        self.assertEqual(bytes(self.me), b'\x00\x00\x01a\xae\x1f')

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
    def __init__(self, **kwargs):
        for k,v in kwargs.items():
            if k in ["addr","callsign"]:
                setattr(self,k,v)
        self.callsign = self.callsign.upper() if hasattr(self,"callsign") else self.decode(self.addr)
        self.addr = self.addr if hasattr(self,"addr") else self.encode(self.callsign)

    def __str__(self):
        return "%s == 0x%06x"%(self.callsign,self.addr)
    def __bytes__(self):
        return bitstruct.pack("u48",self.addr)

    def __index__(self):
        return self.addr

    def __eq__(self, compareto):
        if type(compareto) == type(""):
            if compareto.isdigit(): #yeah, gross.
                return int(compareto) == self.addr
            else: 
                return compareto.upper() == self.callsign
        elif type(compareto) == type(1):
            return compareto == self.addr
        elif type(compareto) == type(self):
            return int(self) == int(compareto)
        else:
            return False

    @staticmethod
    def to_dmr_id(something):
        # if no db:
        # url = "https://database.radioid.net/static/users.json"
        # requests.get()
        #if db but not found, _check once_ using https://database.radioid.net/api/dmr/user/?id=3125404
        #return an Address encoded for DMR using database lookup?
        #or jsut the ID as an int?
        ...
    @staticmethod
    def from_dmr_id(dmr_int):
        #return an Address encoded for callsign using dmr database lookup to get callsign
        ...
    def is_dmr_id(self):
        return self.callsign.startswith("D") and self.callsign[1:].isdigit()
    def is_dmr_talkgroup(self):
        return any(
                self.is_brandmeister_tg()
                )
    def is_brandmeister_tg(self):
        return self.callsign.startswith("BM") and self.callsign[1:].isdigit()
    def is_dstar_reflector(self):
        return self.callsign.startswith("REF")

    @staticmethod
    def encode(callsign):
        num = 0
        for char in callsign.upper()[::-1]:
            charidx = callsign_alphabet.index(char)
            num *= 40
            num += charidx
            if num >= 40**9:
                raise(Exception("Invalid callsign"))
        return num
    
    @staticmethod
    def decode(addr):
        num = addr
        if num >= 40**9:
            raise(Exception("Not a callsign"))
        chars = []
        while num > 0:
            idx = int(num%40)
            c =  callsign_alphabet[idx] 
            chars.append(c)
            # print(num,idx,c)
            num //= 40
        callsign = "".join(chars)
        return callsign


def show_help():
    print("""
Provide callsigns on the command line and they will be translated into M17 addresses
    """)
if __name__ == "__main__":
    if len(sys.argv) <= 1:
        show_help()
    else:
        for each in sys.argv[1:]:
            print(Address(callsign=each))
