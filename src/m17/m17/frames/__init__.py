"""
M17 Frame Definitions

This module contains frame structures for M17 protocol:
- Link Setup Frame (LSF)
- Stream frames
- Packet frames
- IP frames
- LICH chunks
"""

from m17.frames.lsf import (
    LinkSetupFrame,
    MetaPosition,
    MetaExtendedCallsign,
    MetaNonce,
    DataSource,
    StationType,
    ValidityField,
)
from m17.frames.stream import StreamFrame, M17Payload

# Legacy alias
RegularFrame = StreamFrame  # Backward compatibility
from m17.frames.packet import PacketFrame
from m17.frames.ip import IPFrame
from m17.frames.lich import LICHFrame, LICHChunk

__all__ = [
    # LSF
    "LinkSetupFrame",
    "MetaPosition",
    "MetaExtendedCallsign",
    "MetaNonce",
    "DataSource",
    "StationType",
    "ValidityField",
    # Stream
    "StreamFrame",
    "M17Payload",
    "RegularFrame",  # Legacy alias for StreamFrame
    # Packet
    "PacketFrame",
    # IP
    "IPFrame",
    # LICH
    "LICHFrame",
    "LICHChunk",
]
