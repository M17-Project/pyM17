#!/usr/bin/env python
"""
VoIP Simulation Entry Point (Legacy Module)

.. deprecated:: 1.0.0
    This module is deprecated. Use ``python -m m17.apps voipsim`` instead.
"""
import logging
import sys
import warnings

from m17.apps import voipsim

logger = logging.getLogger(__name__)

# Emit deprecation warning on module import
warnings.warn(
    "m17.voipsim is deprecated. Use 'python -m m17.apps voipsim' instead.",
    DeprecationWarning,
    stacklevel=2,
)

if __name__ == "__main__":
    logger.debug("voipsim args: %s", sys.argv)
    voipsim(*sys.argv[1:])
