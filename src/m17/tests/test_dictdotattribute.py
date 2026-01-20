import unittest

from m17.misc import DictDotAttribute


class TestNestedDictDotAttribute(unittest.TestCase):
    """Test the DictDotAttribute class"""

    def test_get(self):
        """Test getting a value from a DictDotAttribute"""
        x = DictDotAttribute({"abc": {"fed": "out"}})
        self.assertEqual(x.abc.fed, "out")

    def test_set(self):
        """Test setting a value in a DictDotAttribute"""
        x = DictDotAttribute({"abc": {"fed": "out"}})
        x.abc.fed = "in"
        self.assertEqual(x.abc.fed, "in")
