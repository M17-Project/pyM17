"""Sanity Check Script (Legacy Module)

This script checks if the required optional modules are installed and working properly.

.. deprecated:: 0.1.1
    This module is deprecated. Use ``poetry install -E audio`` to install
    audio dependencies, which will validate the installation.
"""
import sys
import warnings

# Emit deprecation warning on module import
warnings.warn(
    "m17.sanity_check is deprecated. Use 'poetry install -E audio' to install dependencies.",
    DeprecationWarning,
    stacklevel=2,
)

if __name__ == "__main__":
    try:
        import numpy  # noqa: F401
        import pycodec2  # noqa: F401
        import soundcard as sc  # noqa: F401

        print("Successfully imported pycodec2 and soundcard modules, everything should work.")
        sys.exit(0)
    except Exception as e:
        print(f"Import error: {e}")
        print(
            "Could not import pycodec2 and soundcard modules. "
            "Install with: pip install m17[audio]"
        )
        sys.exit(1)
