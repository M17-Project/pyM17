"""
M17 Core Protocol Components

This module contains the fundamental building blocks for M17 protocol:
- CRC-16 calculation
- Address encoding/decoding
- TYPE field definitions
- Protocol constants
"""

from m17.core.crc import crc_m17, M17_CRC_POLY
from m17.core.types import (
    M17Type,
    M17DataType,
    M17EncryptionType,
    M17EncryptionSubtype,
    M17MetaType,
    ChannelAccessNumber,
)
from m17.core.constants import (
    SYNC_LSF,
    SYNC_STREAM,
    SYNC_PACKET,
    SYNC_BERT,
    EOT_MARKER,
    SYM_PER_SWD,
    SYM_PER_PLD,
    SYM_PER_FRA,
    CALLSIGN_ALPHABET,
    M17_MAGIC_NUMBER,
    DEFAULT_PORT,
    BROADCAST_ADDRESS,
    MAX_CALLSIGN_VALUE,
    HASH_ADDRESS_MIN,
    HASH_ADDRESS_MAX,
)
from m17.core.address import Address

__all__ = [
    # CRC
    "crc_m17",
    "M17_CRC_POLY",
    # Types
    "M17Type",
    "M17DataType",
    "M17EncryptionType",
    "M17EncryptionSubtype",
    "M17MetaType",
    "ChannelAccessNumber",
    # Constants
    "SYNC_LSF",
    "SYNC_STREAM",
    "SYNC_PACKET",
    "SYNC_BERT",
    "EOT_MARKER",
    "SYM_PER_SWD",
    "SYM_PER_PLD",
    "SYM_PER_FRA",
    "CALLSIGN_ALPHABET",
    "M17_MAGIC_NUMBER",
    "DEFAULT_PORT",
    "BROADCAST_ADDRESS",
    "MAX_CALLSIGN_VALUE",
    "HASH_ADDRESS_MIN",
    "HASH_ADDRESS_MAX",
    # Address
    "Address",
]
