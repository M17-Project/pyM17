import unittest
import doctest

from m17 import address, frames, framer, misc
def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(address))
    tests.addTests(doctest.DocTestSuite(frames))
    tests.addTests(doctest.DocTestSuite(framer))
    tests.addTests(doctest.DocTestSuite(misc))
    return tests

