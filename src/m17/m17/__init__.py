"""pyM17 - Python M17 Protocol Library

A modern Python implementation of the M17 digital radio protocol,
compliant with M17 specification v2.0.3.

This library provides:
- Core protocol components (CRC, addressing, type fields)
- Frame handling (LSF, stream, packet, IP frames)
- FEC codec (Golay, convolutional, Viterbi)
- Network clients (reflector, DHT, P2P)
- Audio processing (Codec2 integration)

Basic Usage:
    from m17 import Address, IPFrame

    # Create an address
    addr = Address(callsign="W2FBI")
    print(f"Encoded: {hex(addr.numeric)}")

    # Parse an IP frame
    frame = IPFrame.from_bytes(data)
    print(f"{frame.src} -> {frame.dst}")

For more details, see the submodules:
- m17.core: Core protocol components
- m17.frames: Frame definitions
- m17.codec: FEC encoding/decoding
- m17.net: Network clients
- m17.audio: Audio processing
"""

import logging

__version__ = "0.1.4"

logger = logging.getLogger(__name__)

# =============================================================================
# Modern API - New module structure
# =============================================================================

# Core components
from m17.core import (
    BROADCAST_ADDRESS,
    CALLSIGN_ALPHABET,
    DEFAULT_PORT,
    EOT_MARKER,
    M17_CRC_POLY,
    M17_MAGIC_NUMBER,
    SYNC_BERT,
    # Constants
    SYNC_LSF,
    SYNC_PACKET,
    SYNC_STREAM,
    # Address
    Address,
    ChannelAccessNumber,
    M17DataType,
    M17EncryptionSubtype,
    M17EncryptionType,
    M17MetaType,
    # Types
    M17Type,
    # CRC
    crc_m17,
)

# Frame types
from m17.frames import (
    IPFrame,
    LICHChunk,
    LICHFrame,
    LinkSetupFrame,
    M17Payload,
    MetaExtendedCallsign,
    MetaNonce,
    MetaPosition,
    PacketFrame,
    StreamFrame,
)

# =============================================================================
# Legacy API - Backward compatibility with existing code
# =============================================================================

# Legacy imports from old locations (deprecated, will be removed in v1.0)
# Import old modules to ensure backward compatibility
try:
    from m17.address import Address as _LegacyAddress
except ImportError as e:
    logger.debug("Legacy m17.address module not available: %s", e)

try:
    from m17.frames import (
        IPFrame as _LegacyIPFrame,
    )
    from m17.frames import (
        LICHFrame as _LegacyLICHFrame,
    )
    from m17.frames import (
        M17Payload as _LegacyM17Payload,
    )
    from m17.frames import (
        RegularFrame,
    )
except ImportError as e:
    # If old frames module fails, RegularFrame comes from new module
    logger.debug("Legacy m17.frames imports not available, using StreamFrame: %s", e)
    RegularFrame = StreamFrame

# Legacy framer classes (deprecated, will be removed in v1.0)
from m17.framer import M17IPFramer, M17RFFramer

# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Version
    "__version__",
    # Core - CRC
    "crc_m17",
    "M17_CRC_POLY",
    # Core - Address
    "Address",
    # Core - Types
    "M17Type",
    "M17DataType",
    "M17EncryptionType",
    "M17EncryptionSubtype",
    "M17MetaType",
    "ChannelAccessNumber",
    # Core - Constants
    "SYNC_LSF",
    "SYNC_STREAM",
    "SYNC_PACKET",
    "SYNC_BERT",
    "EOT_MARKER",
    "CALLSIGN_ALPHABET",
    "M17_MAGIC_NUMBER",
    "DEFAULT_PORT",
    "BROADCAST_ADDRESS",
    # Frames
    "LinkSetupFrame",
    "StreamFrame",
    "PacketFrame",
    "IPFrame",
    "LICHFrame",
    "LICHChunk",
    "M17Payload",
    "MetaPosition",
    "MetaExtendedCallsign",
    "MetaNonce",
    # Legacy (deprecated)
    "RegularFrame",
    "M17IPFramer",
    "M17RFFramer",
]
