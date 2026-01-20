"""
Test the encoding and decoding of M17 frames.

Updated for modernized pyM17 API (v0.1.x).
"""
import unittest

from m17.core.address import Address
from m17.misc import example_bytes
from m17.frames import LICHFrame, StreamFrame, IPFrame, M17Payload
from m17.frames.lsf import LinkSetupFrame


class test_frame_encodings(unittest.TestCase):
    """
    Test the encoding and decoding of M17 frames.
    """
    def test_lich(self):
        """
        Test encoding and decoding of LICH frames.
        """
        lich = LICHFrame(
            dst=Address(callsign="SP5WWP"),
            src=Address(callsign="W2FBI"),
            stream_type=5,
            nonce=bytes(example_bytes(14)),
        )
        bl = bytes(lich)
        lich2 = LICHFrame.from_bytes(bl)
        assert lich == lich2

    def test_stream_frame(self):
        """
        Test encoding and decoding of stream frames (formerly RegularFrame).
        """
        lich = LICHFrame(
            dst=Address(callsign="SP5WWP"),
            src=Address(callsign="W2FBI"),
            stream_type=5,
            nonce=bytes(example_bytes(14)),
        )

        # StreamFrame uses lich_chunk (6 bytes) not full LICH
        lich_chunk = lich.get_chunk(0)
        m17_payload = M17Payload(frame_number=1, payload=bytes(example_bytes(16)))

        x = StreamFrame(lich_chunk=lich_chunk, payload=m17_payload)
        y = bytes(x)
        z = StreamFrame.from_bytes(y)
        assert z == x

    def test_ip_frame(self):
        """
        Test encoding and decoding of IP frames.
        """
        # IPFrame uses LinkSetupFrame (lsf) instead of LICHFrame
        lsf = LinkSetupFrame(
            dst=Address(callsign="SP5WWP"),
            src=Address(callsign="W2FBI"),
            type_field=5,
            meta=bytes(example_bytes(14)),
        )

        m17_payload = M17Payload(frame_number=1, payload=bytes(example_bytes(16)))

        x = IPFrame(
            stream_id=0xf00d,
            lsf=lsf,
            payload=m17_payload
        )
        y = bytes(x)
        z = IPFrame.from_bytes(y)
        assert z == x
