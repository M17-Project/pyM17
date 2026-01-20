"""
M17 Protocol Constants

Contains sync words, frame sizes, and other protocol constants.
Supports M17 specification v2.0.3 and v3.0.0.
"""

from __future__ import annotations

import string

__all__ = [
    # Sync words (16-bit)
    "SYNC_LSF",
    "SYNC_STREAM",
    "SYNC_PACKET",
    "SYNC_BERT",
    "EOT_MARKER",
    # Frame dimensions
    "SYM_PER_SWD",
    "SYM_PER_PLD",
    "SYM_PER_FRA",
    # LSF sizes
    "LSF_SIZE",
    "LSF_SIZE_WITH_CRC",
    # Payload sizes
    "PAYLOAD_SIZE_BITS",
    "PAYLOAD_SIZE_BYTES",
    "LICH_CHUNK_SIZE",
    # IP frame sizes
    "IP_FRAME_SIZE",
    # Address constants
    "CALLSIGN_ALPHABET",
    "MAX_CALLSIGN_VALUE",
    "BROADCAST_ADDRESS",
    "HASH_ADDRESS_MIN",
    "HASH_ADDRESS_MAX",
    # Network
    "M17_MAGIC_NUMBER",
    "DEFAULT_PORT",
    "DEFAULT_DHT_PORT",
    "get_reflector_host",
    # Packet Protocol Identifiers (v3.0.0)
    "PACKET_PROTOCOL_RAW",
    "PACKET_PROTOCOL_AX25",
    "PACKET_PROTOCOL_APRS",
    "PACKET_PROTOCOL_6LOWPAN",
    "PACKET_PROTOCOL_IPV4",
    "PACKET_PROTOCOL_SMS",
    "PACKET_PROTOCOL_WINLINK",
    "PACKET_PROTOCOL_TLE",
    # Frame layout structs (for backward compatibility)
    "M17_ADDRESS_LAYOUT_STRUCT",
    "M17_PAYLOAD_LAYOUT_STRUCT",
    "LICH_FRAME_LAYOUT_STRUCT",
    "LICH_FRAME_CRC_LAYOUT_STRUCT",
    "REGULAR_FRAME_LAYOUT_STRUCT",
    "IP_FRAME_LAYOUT_STRUCT",
]

# ============================================================================
# Sync Words (16-bit values)
# ============================================================================

# Link Setup Frame sync word
SYNC_LSF: int = 0x55F7

# Stream frame sync word
SYNC_STREAM: int = 0xFF5D

# Packet frame sync word
SYNC_PACKET: int = 0x75FF

# BERT (Bit Error Rate Test) sync word
SYNC_BERT: int = 0xDF55

# End of Transmission marker (replaces last frame's frame counter MSB)
EOT_MARKER: int = 0x555D

# ============================================================================
# Frame Dimensions (in symbols/bits)
# ============================================================================

# Symbols per sync word
SYM_PER_SWD: int = 8

# Symbols per payload (184 symbols = 368 bits)
SYM_PER_PLD: int = 184

# Total symbols per frame (sync + payload)
SYM_PER_FRA: int = SYM_PER_SWD + SYM_PER_PLD  # 192

# ============================================================================
# Link Setup Frame (LSF) Sizes
# ============================================================================

# LSF size without CRC (28 bytes)
# DST(6) + SRC(6) + TYPE(2) + META(14)
LSF_SIZE: int = 28

# LSF size with CRC (30 bytes)
LSF_SIZE_WITH_CRC: int = 30

# ============================================================================
# Payload Sizes
# ============================================================================

# Payload size in bits (after FEC decoding)
PAYLOAD_SIZE_BITS: int = 128

# Payload size in bytes
PAYLOAD_SIZE_BYTES: int = PAYLOAD_SIZE_BITS // 8  # 16

# LICH chunk size (6 bytes = 48 bits)
LICH_CHUNK_SIZE: int = 6

# ============================================================================
# IP Frame Size
# ============================================================================

# IP frame total size: MAGIC(4) + SID(2) + LICH(28) + FN(2) + PAYLOAD(16) + CRC(2) = 54 bytes
IP_FRAME_SIZE: int = 54

# ============================================================================
# Address Constants
# ============================================================================

# Base-40 callsign alphabet
# Space, A-Z, 0-9, -, /, .
CALLSIGN_ALPHABET: str = " " + string.ascii_uppercase + string.digits + "-/."

# Maximum value for regular callsign encoding (40^9 - 1)
MAX_CALLSIGN_VALUE: int = 40**9 - 1  # 262,143,999,999

# Broadcast address (all 1s)
BROADCAST_ADDRESS: int = 0xFFFFFFFFFFFF

# Hash-prefixed address range (for #-prefixed callsigns)
# Range: 40^9 to 40^9 + 40^8 - 1
HASH_ADDRESS_MIN: int = 40**9
HASH_ADDRESS_MAX: int = 40**9 + 40**8 - 1

# ============================================================================
# Network Constants
# ============================================================================

# M17 magic number for IP frames
M17_MAGIC_NUMBER: bytes = b"M17 "

# Default M17 UDP port
DEFAULT_PORT: int = 17000

# Default DHT port
DEFAULT_DHT_PORT: int = 17001

def get_reflector_host(refname: str, domain: str) -> str:
    """
    Convert a reflector name to a hostname.

    Args:
        refname: Reflector name (e.g., "M17-ABC").
        domain: Reflector domain suffix (required, e.g., "m17ref.example.com").

    Returns:
        Full hostname (e.g., "M17-ABC.m17ref.example.com").
    """
    return f"{refname}.{domain}"

# ============================================================================
# Struct Layout Strings (for backward compatibility)
# ============================================================================

# Address layout (6 bytes)
M17_ADDRESS_LAYOUT_STRUCT: str = "6B"

# Payload layout: Frame Number (2B) + Payload (8B) + CRC (2B) = 12 bytes
M17_PAYLOAD_LAYOUT_STRUCT: str = "H 8B H"

# LICH frame layout: DST(6B) + SRC(6B) + TYPE(2B) + META(14B) = 28 bytes
LICH_FRAME_LAYOUT_STRUCT: str = "6B 6B H 14B"

# LICH frame with CRC: LICH(28B) + CRC(2B) = 30 bytes
LICH_FRAME_CRC_LAYOUT_STRUCT: str = f"{LICH_FRAME_LAYOUT_STRUCT} H"

# Regular frame layout: LICH_CHUNK(6B) + PAYLOAD(12B) = 18 bytes
REGULAR_FRAME_LAYOUT_STRUCT: str = f"6B {M17_PAYLOAD_LAYOUT_STRUCT}"

# IP frame layout: MAGIC(4B) + SID(2B) + LICH(28B) + PAYLOAD(12B) = 46 bytes
# Note: This matches existing implementation
IP_FRAME_LAYOUT_STRUCT: str = f"4B H {LICH_FRAME_LAYOUT_STRUCT} {M17_PAYLOAD_LAYOUT_STRUCT}"

# ============================================================================
# Packet Protocol Identifiers (v3.0.0)
# ============================================================================

# Raw data (no protocol)
PACKET_PROTOCOL_RAW: int = 0x00

# AX.25 protocol
PACKET_PROTOCOL_AX25: int = 0x01

# APRS protocol
PACKET_PROTOCOL_APRS: int = 0x02

# 6LoWPAN (IPv6 over Low-Power Wireless)
PACKET_PROTOCOL_6LOWPAN: int = 0x03

# IPv4 protocol
PACKET_PROTOCOL_IPV4: int = 0x04

# SMS (Short Message Service)
PACKET_PROTOCOL_SMS: int = 0x05

# Winlink protocol
PACKET_PROTOCOL_WINLINK: int = 0x06

# TLE (Two-Line Element) - v3.0.0 addition for satellite orbital data
PACKET_PROTOCOL_TLE: int = 0x07
