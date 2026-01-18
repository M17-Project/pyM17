"""
pyM17 - Python M17 Protocol Library

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

__version__ = "1.0.0"

# =============================================================================
# Modern API - New module structure
# =============================================================================

# Core components
from m17.core import (
    # CRC
    crc_m17,
    M17_CRC_POLY,
    # Address
    Address,
    # Types
    M17Type,
    M17DataType,
    M17EncryptionType,
    M17EncryptionSubtype,
    M17MetaType,
    ChannelAccessNumber,
    # Constants
    SYNC_LSF,
    SYNC_STREAM,
    SYNC_PACKET,
    SYNC_BERT,
    EOT_MARKER,
    CALLSIGN_ALPHABET,
    M17_MAGIC_NUMBER,
    DEFAULT_PORT,
    BROADCAST_ADDRESS,
)

# Frame types
from m17.frames import (
    LinkSetupFrame,
    StreamFrame,
    PacketFrame,
    IPFrame,
    LICHFrame,
    LICHChunk,
    M17Payload,
    MetaPosition,
    MetaExtendedCallsign,
    MetaNonce,
)

# =============================================================================
# Legacy API - Backward compatibility with existing code
# =============================================================================

# Legacy imports from old locations (deprecated, will be removed in v2.0)
# Import old modules to ensure backward compatibility
try:
    from m17.address import Address as _LegacyAddress
except ImportError:
    pass

try:
    from m17.frames import (
        LICHFrame as _LegacyLICHFrame,
        RegularFrame,
        IPFrame as _LegacyIPFrame,
        M17Payload as _LegacyM17Payload,
    )
except ImportError:
    # If old frames module fails, RegularFrame comes from new module
    RegularFrame = StreamFrame

try:
    from m17.framer import M17IPFramer, M17RFFramer
except ImportError:
    # Provide stub implementations if framer not available
    M17IPFramer = None
    M17RFFramer = None

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