"""
M17 Packet Frame Definitions

Packet frames carry non-real-time data in a self-contained format.
Each packet contains:
- 25 bytes of data
- 1 byte with End of Packet flag (1 bit) and byte count (5 bits)

Total: 26 bytes per packet chunk, encoded to 368 bits with FEC.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Optional

from m17.core.crc import crc_m17

__all__ = ["PacketFrame", "PacketChunk"]


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
