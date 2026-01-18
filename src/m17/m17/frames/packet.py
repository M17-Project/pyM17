"""
M17 Packet Frame Definitions

Packet frames carry non-real-time data in a self-contained format.
Each packet contains:
- 25 bytes of data
- 1 byte with End of Packet flag (1 bit) and byte count (5 bits)

Total: 26 bytes per packet chunk, encoded to 368 bits with FEC.

Supports M17 v2.0.3 and v3.0.0 (with TLE packet type).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Optional
from enum import IntEnum

from m17.core.crc import crc_m17
from m17.core.constants import (
    PACKET_PROTOCOL_RAW,
    PACKET_PROTOCOL_AX25,
    PACKET_PROTOCOL_APRS,
    PACKET_PROTOCOL_6LOWPAN,
    PACKET_PROTOCOL_IPV4,
    PACKET_PROTOCOL_SMS,
    PACKET_PROTOCOL_WINLINK,
    PACKET_PROTOCOL_TLE,
)

__all__ = ["PacketFrame", "PacketChunk", "PacketProtocol", "TLEPacket"]


class PacketProtocol(IntEnum):
    """Packet protocol identifiers."""

    RAW = PACKET_PROTOCOL_RAW
    AX25 = PACKET_PROTOCOL_AX25
    APRS = PACKET_PROTOCOL_APRS
    LOWPAN_6 = PACKET_PROTOCOL_6LOWPAN
    IPV4 = PACKET_PROTOCOL_IPV4
    SMS = PACKET_PROTOCOL_SMS
    WINLINK = PACKET_PROTOCOL_WINLINK
    TLE = PACKET_PROTOCOL_TLE


@dataclass
class PacketChunk:
    """
    A single chunk of packet data.

    Each chunk contains up to 25 bytes of data plus a control byte
    that indicates whether this is the last chunk and how many
    bytes are valid in the last chunk.

    Attributes:
        data: Up to 25 bytes of payload data.
        is_last: True if this is the final chunk.
        byte_count: Number of valid bytes in final chunk (0-25).
    """

    data: bytes = field(default_factory=lambda: bytes(25))
    is_last: bool = False
    byte_count: int = 25

    def __post_init__(self) -> None:
        """Validate and normalize fields."""
        # Validate byte count
        if not 0 <= self.byte_count <= 25:
            raise ValueError(f"Byte count must be 0-25, got {self.byte_count}")

        # Pad or truncate data to 25 bytes
        if len(self.data) < 25:
            object.__setattr__(
                self, "data", self.data + bytes(25 - len(self.data))
            )
        elif len(self.data) > 25:
            object.__setattr__(self, "data", self.data[:25])

    @property
    def control_byte(self) -> int:
        """
        Get the control byte.

        Format: [EOP:1][BC:5][Reserved:2]
        - EOP: End of Packet flag (1 = last chunk)
        - BC: Byte count in last chunk (0-25)
        """
        eop = 0x80 if self.is_last else 0x00
        bc = (self.byte_count & 0x1F) << 2
        return eop | bc

    @property
    def valid_data(self) -> bytes:
        """Get only the valid bytes from this chunk."""
        if self.is_last:
            return self.data[: self.byte_count]
        return self.data

    def to_bytes(self) -> bytes:
        """
        Serialize chunk to 26 bytes.

        Returns:
            26-byte serialized chunk.
        """
        return self.data + bytes([self.control_byte])

    def __bytes__(self) -> bytes:
        """Return serialized chunk."""
        return self.to_bytes()

    @classmethod
    def from_bytes(cls, data: bytes) -> PacketChunk:
        """
        Parse chunk from bytes.

        Args:
            data: 26 bytes of chunk data.

        Returns:
            Parsed PacketChunk.
        """
        if len(data) != 26:
            raise ValueError(f"Chunk must be 26 bytes, got {len(data)}")

        chunk_data = bytes(data[:25])
        control = data[25]

        is_last = (control & 0x80) != 0
        byte_count = (control >> 2) & 0x1F

        return cls(data=chunk_data, is_last=is_last, byte_count=byte_count)

    def __str__(self) -> str:
        """Return string representation."""
        last = " [LAST]" if self.is_last else ""
        return f"PacketChunk[{self.byte_count}]{last}: {self.valid_data.hex()}"


@dataclass
class PacketFrame:
    """
    M17 Packet Frame.

    Represents a complete packet which may span multiple chunks.
    Includes the full LSF followed by one or more data chunks with CRC.

    Attributes:
        chunks: List of PacketChunk objects.
    """

    chunks: List[PacketChunk] = field(default_factory=list)

    @classmethod
    def from_data(cls, data: bytes) -> PacketFrame:
        """
        Create a packet frame from raw data.

        Splits data into 25-byte chunks and adds control bytes.

        Args:
            data: Raw data bytes to packetize.

        Returns:
            PacketFrame with chunked data.
        """
        chunks = []

        # Split data into 25-byte chunks
        for i in range(0, len(data), 25):
            chunk_data = data[i : i + 25]
            is_last = i + 25 >= len(data)
            byte_count = len(chunk_data) if is_last else 25

            chunk = PacketChunk(
                data=chunk_data, is_last=is_last, byte_count=byte_count
            )
            chunks.append(chunk)

        # If no data, create single empty last chunk
        if not chunks:
            chunks.append(PacketChunk(is_last=True, byte_count=0))

        return cls(chunks=chunks)

    def get_data(self) -> bytes:
        """
        Extract the full data from all chunks.

        Returns:
            Concatenated valid data from all chunks.
        """
        data = bytearray()
        for chunk in self.chunks:
            data.extend(chunk.valid_data)
        return bytes(data)

    def calculate_crc(self) -> int:
        """
        Calculate CRC for the entire packet data.

        Returns:
            16-bit CRC value.
        """
        return crc_m17(self.get_data())

    @property
    def total_chunks(self) -> int:
        """Get total number of chunks."""
        return len(self.chunks)

    @property
    def total_bytes(self) -> int:
        """Get total number of data bytes."""
        return len(self.get_data())

    def to_bytes_list(self) -> List[bytes]:
        """
        Serialize all chunks to a list of byte arrays.

        Returns:
            List of 26-byte chunk serializations.
        """
        return [bytes(chunk) for chunk in self.chunks]

    def __str__(self) -> str:
        """Return string representation."""
        return f"PacketFrame: {self.total_chunks} chunks, {self.total_bytes} bytes"

    def __iter__(self):
        """Iterate over chunks."""
        return iter(self.chunks)

    def __len__(self) -> int:
        """Return number of chunks."""
        return len(self.chunks)

    def __getitem__(self, index: int) -> PacketChunk:
        """Get chunk by index."""
        return self.chunks[index]


@dataclass
class TLEPacket:
    """
    M17 v3.0.0 TLE (Two-Line Element) Packet.

    Contains satellite orbital data in TLE format.
    The TLE format consists of 3 lines:
    - Line 0: Satellite name (up to 24 characters)
    - Line 1: TLE line 1 (69 characters)
    - Line 2: TLE line 2 (69 characters)

    Total: ~162+ characters depending on satellite name.

    Format:
    - Protocol identifier (0x07) - 1 byte
    - TLE data as ASCII text (lines separated by 0x0A)
    - Null terminator (0x00) after last line
    - CRC-16 - 2 bytes
    """

    satellite_name: str = ""
    tle_line1: str = ""
    tle_line2: str = ""

    # Standard TLE line lengths
    _TLE_LINE_LENGTH: int = 69

    def __post_init__(self) -> None:
        """Validate TLE data."""
        # Basic validation
        if self.tle_line1 and len(self.tle_line1) != self._TLE_LINE_LENGTH:
            # Allow non-standard lengths but warn in production
            pass
        if self.tle_line2 and len(self.tle_line2) != self._TLE_LINE_LENGTH:
            pass

    @property
    def is_valid(self) -> bool:
        """Check if TLE data appears valid."""
        if not self.tle_line1 or not self.tle_line2:
            return False

        # Basic format checks
        if len(self.tle_line1) != self._TLE_LINE_LENGTH:
            return False
        if len(self.tle_line2) != self._TLE_LINE_LENGTH:
            return False

        # Line 1 should start with '1 '
        if not self.tle_line1.startswith("1 "):
            return False

        # Line 2 should start with '2 '
        if not self.tle_line2.startswith("2 "):
            return False

        return True

    def to_bytes(self) -> bytes:
        """
        Encode TLE packet to bytes.

        Returns:
            Encoded packet with protocol ID, TLE data, null terminator, and CRC.
        """
        # Build TLE text with newlines
        lines = [self.satellite_name, self.tle_line1, self.tle_line2]
        tle_text = "\n".join(lines)

        # Encode as ASCII
        tle_bytes = tle_text.encode("ascii", errors="replace")

        # Build packet: protocol_id + tle_data + null
        packet_data = bytes([PACKET_PROTOCOL_TLE]) + tle_bytes + b"\x00"

        # Calculate CRC over packet data
        crc = crc_m17(packet_data)

        return packet_data + crc.to_bytes(2, "big")

    @classmethod
    def from_bytes(cls, data: bytes) -> "TLEPacket":
        """
        Parse TLE packet from bytes.

        Args:
            data: Encoded TLE packet bytes.

        Returns:
            Parsed TLEPacket.

        Raises:
            ValueError: If packet is invalid or CRC fails.
        """
        if len(data) < 4:  # Minimum: protocol + null + CRC
            raise ValueError(f"TLE packet too short: {len(data)} bytes")

        # Check protocol identifier
        if data[0] != PACKET_PROTOCOL_TLE:
            raise ValueError(f"Invalid protocol ID: 0x{data[0]:02x}, expected 0x{PACKET_PROTOCOL_TLE:02x}")

        # Verify CRC
        packet_data = data[:-2]
        received_crc = int.from_bytes(data[-2:], "big")
        calculated_crc = crc_m17(packet_data)

        if received_crc != calculated_crc:
            raise ValueError(
                f"CRC mismatch: received 0x{received_crc:04x}, calculated 0x{calculated_crc:04x}"
            )

        # Extract TLE text (skip protocol ID, strip null terminator)
        tle_bytes = packet_data[1:]
        if tle_bytes.endswith(b"\x00"):
            tle_bytes = tle_bytes[:-1]

        try:
            tle_text = tle_bytes.decode("ascii")
        except UnicodeDecodeError:
            tle_text = tle_bytes.decode("ascii", errors="replace")

        # Split into lines
        lines = tle_text.split("\n")

        satellite_name = lines[0] if len(lines) > 0 else ""
        tle_line1 = lines[1] if len(lines) > 1 else ""
        tle_line2 = lines[2] if len(lines) > 2 else ""

        return cls(
            satellite_name=satellite_name,
            tle_line1=tle_line1,
            tle_line2=tle_line2,
        )

    def to_packet_frame(self) -> PacketFrame:
        """
        Convert to a PacketFrame for transmission.

        Returns:
            PacketFrame containing the TLE data.
        """
        return PacketFrame.from_data(self.to_bytes())

    @classmethod
    def from_packet_frame(cls, frame: PacketFrame) -> "TLEPacket":
        """
        Parse TLE from a PacketFrame.

        Args:
            frame: PacketFrame containing TLE data.

        Returns:
            Parsed TLEPacket.
        """
        return cls.from_bytes(frame.get_data())

    def __str__(self) -> str:
        """Return string representation."""
        valid = "valid" if self.is_valid else "invalid"
        return f"TLEPacket({self.satellite_name}, {valid})"

    def to_tle_string(self) -> str:
        """
        Return the TLE in standard 3-line format.

        Returns:
            TLE string with newlines.
        """
        return f"{self.satellite_name}\n{self.tle_line1}\n{self.tle_line2}"
