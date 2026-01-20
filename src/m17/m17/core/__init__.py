"""M17 Core Protocol Components

This module contains the fundamental building blocks for M17 protocol:
- CRC-16 calculation
- Address encoding/decoding
- TYPE field definitions
- Protocol constants
"""

from m17.core.address import Address
from m17.core.constants import (
    BROADCAST_ADDRESS,
    CALLSIGN_ALPHABET,
    DEFAULT_PORT,
    EOT_MARKER,
    HASH_ADDRESS_MAX,
    HASH_ADDRESS_MIN,
    M17_MAGIC_NUMBER,
    MAX_CALLSIGN_VALUE,
    SYM_PER_FRA,
    SYM_PER_PLD,
    SYM_PER_SWD,
    SYNC_BERT,
    SYNC_LSF,
    SYNC_PACKET,
    SYNC_STREAM,
)
from m17.core.crc import M17_CRC_POLY, crc_m17
from m17.core.types import (
    ChannelAccessNumber,
    M17DataType,
    M17EncryptionSubtype,
    M17EncryptionType,
    M17MetaType,
    M17Type,
)

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
