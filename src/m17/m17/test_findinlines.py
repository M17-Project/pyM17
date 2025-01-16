import unittest
from m17 import address, frames, framer, misc, blocks

def load_tests(loader, standard_tests, pattern):
    """
    misc is small, unconnected things, so tests make more sense inline,
    next to the thing tested.
    This proxies the test loader to that file.
    """
    lm = unittest.defaultTestLoader.loadTestsFromModule
    module_list = [
            misc,
            address,
            blocks,
            ]
    x = unittest.TestSuite([lm(x) for x in module_list])
    return unittest.TestSuite(x)

