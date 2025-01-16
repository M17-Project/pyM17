import unittest

try:
    from address import Address
    from misc import example_bytes
    from frames import initialLICH, regularFrame, ipFrame
except:
    from .address import Address
    from .misc import example_bytes
    from .frames import initialLICH, regularFrame, ipFrame

class test_frame_encodings(unittest.TestCase):
    def test_lich(self):
        lich = initialLICH(
                src=Address(callsign="W2FBI"),
                dst=Address(callsign="SP5WWP"),
                streamtype=5,
                nonce=bytes(example_bytes(14)),
                )
        bl = bytes(lich)
        lich2 = initialLICH.from_bytes(bl)
        assert lich == lich2
    def test_regular_frame(self):
        lich = initialLICH(
                src=Address(callsign="W2FBI"),
                dst=Address(callsign="SP5WWP"),
                streamtype=5,
                nonce=example_bytes(14),
                )
        x = regularFrame(
                LICH=lich,
                frame_number=1,
                payload=example_bytes(16)
                );
        y = bytes(x)
        z = regularFrame.from_bytes(y)
        assert z == x

    def test_ip_frame(self):
        lich = initialLICH(
                src=Address(callsign="W2FBI"),
                dst=Address(callsign="SP5WWP"),
                streamtype=5,
                nonce=example_bytes(14),
                )
        x = ipFrame(
                streamid=0xf00d,
                LICH=lich,
                frame_number=1,
                payload=example_bytes(16)
                );
        y = bytes(x)
        z = ipFrame.from_bytes(y)
        assert z == x
