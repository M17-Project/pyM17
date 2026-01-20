import unittest

from m17.address import Address


class TestAddress(unittest.TestCase):
    """Tests for the Address class"""

    def setUp(self):
        self.me = Address(callsign="W2FBI")
        self.ref = Address(callsign="XLX307 D")

    def test_string_compare(self):
        """Test that a string compares to the callsign"""
        self.assertEqual(self.me, "W2FBI")

    def test_num_compare(self):
        """Test that a number compares to the address"""
        self.assertEqual(self.me, 23178783)

    def test_compare(self):
        """Test that an Address object compares to another Address object"""
        me2 = Address(addr=23178783)
        self.assertEqual(self.me, me2)

    def test_not_equal(self):
        """Test that an Address object compares to another Address object"""
        me2 = Address(addr=23178784)
        self.assertNotEqual(self.me, me2)

    def test_bytes(self):
        """Test that an Address object can be compared to bytes"""
        print(bytes(self.me).hex())
        self.assertEqual(bytes(self.me), b"\x00\x00\x01a\xae\x1f")
