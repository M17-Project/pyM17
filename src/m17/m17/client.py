#!/usr/bin/env python
import sys

from .apps import voip

if __name__ == "__main__":
    print(sys.argv)
    voip(*sys.argv[1:])
