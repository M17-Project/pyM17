"""
M17 LICH (Link Information Channel) Frame Handling

The LICH transmits the Link Setup Frame incrementally during a stream.
Each stream frame contains a 6-byte LICH chunk, which is 1/5 of the
full 28-byte LSF (plus 2 reserved bytes = 30 bytes total for chunking).

Over 5 consecutive frames, the complete LSF can be reconstructed.

For RF transmission, each 48-bit (6-byte) LICH chunk is encoded
with Golay(24,12) to produce 96 bits of protected data.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Optional

from m17.core.address import Address
from m17.frames.lsf import LinkSetupFrame

__all__ = ["LICHFrame", "LICHChunk", "LICHCollector"]


@dataclass
class LICHChunk:
    """
    A single LICH chunk (6 bytes / 48 bits).

    Each chunk represents 1/5 of the Link Setup Frame data.

    Attributes:
        data: 6-byte chunk data.
        index: Chunk index (0-4).
    """

    data: bytes = field(default_factory=lambda: bytes(6))
    index: int = 0

    def __post_init__(self) -> None:
        """Validate and normalize fields."""
        if len(self.data) != 6:
            if len(self.data) < 6:
                object.__setattr__(self, "data", self.data + bytes(6 - len(self.data)))
            else:
                object.__setattr__(self, "data", self.data[:6])

        if not 0 <= self.index <= 4:
            raise ValueError(f"Chunk index must be 0-4, got {self.index}")

    def __bytes__(self) -> bytes:
        """Return chunk data."""
        return self.data

    def __str__(self) -> str:
        """Return string representation."""
        return f"LICHChunk[{self.index}]: {self.data.hex()}"


@dataclass
class LICHFrame:
    """
    LICH Frame (Link Information Channel).

    This is the legacy name for what is essentially the Link Setup Frame
    when used in the context of stream frame LICH chunks.

    Maintained for backward compatibility with existing code.

    Attributes:
        dst: Destination address.
        src: Source address.
        stream_type: TYPE field value.
        nonce: META/nonce field (14 bytes).
    """

    dst: Address
    src: Address
    stream_type: int = 0x0005
    nonce: bytes = field(default_factory=lambda: bytes(14))

    # Struct for packing: dst(6) + src(6) + type(2) + nonce(14) = 28 bytes
    _STRUCT = struct.Struct(">6s6sH14s")

    def __post_init__(self) -> None:
        """Validate and normalize fields."""
        # Convert string callsigns to Address if needed
        if isinstance(self.dst, str):
            object.__setattr__(self, "dst", Address(callsign=self.dst))
        if isinstance(self.src, str):
            object.__setattr__(self, "src", Address(callsign=self.src))

        # Ensure nonce is exactly 14 bytes
        if len(self.nonce) != 14:
            if len(self.nonce) < 14:
                object.__setattr__(
                    self, "nonce", self.nonce + bytes(14 - len(self.nonce))
                )
            else:
                object.__setattr__(self, "nonce", self.nonce[:14])

    @classmethod
    def from_lsf(cls, lsf: LinkSetupFrame) -> LICHFrame:
        """
        Create LICHFrame from LinkSetupFrame.

        Args:
            lsf: Link Setup Frame.

        Returns:
            LICHFrame with same data.
        """
        return cls(
            dst=lsf.dst,
            src=lsf.src,
            stream_type=lsf.type_field,
            nonce=lsf.meta,
        )

    def to_lsf(self) -> LinkSetupFrame:
        """
        Convert to LinkSetupFrame.

        Returns:
            LinkSetupFrame with same data.
        """
        return LinkSetupFrame(
            dst=self.dst,
            src=self.src,
            type_field=self.stream_type,
            meta=self.nonce,
        )

    def to_bytes(self) -> bytes:
        """
        Serialize LICH to bytes.

        Returns:
            28-byte LICH data.
        """
        return self._STRUCT.pack(
            bytes(self.dst),
            bytes(self.src),
            self.stream_type,
            self.nonce,
        )

    def pack(self) -> bytes:
        """Serialize (legacy method)."""
        return self.to_bytes()

    def __bytes__(self) -> bytes:
        """Return serialized LICH."""
        return self.to_bytes()

    @classmethod
    def from_bytes(cls, data: bytes) -> LICHFrame:
        """
        Parse LICH from bytes.

        Args:
            data: 28 bytes of LICH data.

        Returns:
            Parsed LICHFrame.
        """
        if len(data) != 28:
            raise ValueError(f"LICH must be 28 bytes, got {len(data)}")

        dst_bytes, src_bytes, stream_type, nonce = cls._STRUCT.unpack(data)

        return cls(
            dst=Address(addr=dst_bytes),
            src=Address(addr=src_bytes),
            stream_type=stream_type,
            nonce=nonce,
        )

    @classmethod
    def unpack(cls, data: bytes) -> LICHFrame:
        """Parse LICH (legacy method)."""
        return cls.from_bytes(data)

    def chunks(self, chunk_size: int = 6) -> List[bytes]:
        """
        Split LICH into chunks for stream transmission.

        The 28-byte LICH is padded to 30 bytes and split into 5 chunks.

        Args:
            chunk_size: Size of each chunk (default 6).

        Returns:
            List of 5 byte chunks.
        """
        data = self.to_bytes()
        # Pad to 30 bytes for even splitting into 5 chunks
        data = data + bytes(2)  # 2 reserved/padding bytes
        return [data[i : i + chunk_size] for i in range(0, 30, chunk_size)]

    def get_chunk(self, frame_number: int) -> bytes:
        """
        Get the LICH chunk for a specific frame number.

        Args:
            frame_number: Frame number to determine chunk index.

        Returns:
            6-byte LICH chunk for this frame.
        """
        chunks = self.chunks()
        return chunks[frame_number % 5]

    def get_pack_values(self) -> list:
        """Get values for struct packing (legacy compatibility)."""
        return [
            *bytes(self.dst),
            *bytes(self.src),
            self.stream_type,
            *self.nonce,
        ]

    def __str__(self) -> str:
        """Return string representation."""
        return f"LICH: {self.src.callsign} -> {self.dst.callsign} [type=0x{self.stream_type:04x}]"

    def __eq__(self, other: object) -> bool:
        """Compare LICH frames."""
        if isinstance(other, LICHFrame):
            return bytes(self) == bytes(other)
        if isinstance(other, bytes):
            return bytes(self) == other
        return NotImplemented

    @staticmethod
    def dict_from_bytes(data: bytes) -> dict:
        """
        Parse LICH to dictionary (legacy method).

        Args:
            data: 28 bytes of LICH data.

        Returns:
            Dictionary with LICH fields.
        """
        lich = LICHFrame.from_bytes(data)
        return {
            "src": lich.src,
            "dst": lich.dst,
            "stream_type": lich.stream_type,
            "nonce": lich.nonce,
        }


class LICHCollector:
    """
    Collects LICH chunks to reconstruct the full Link Setup Frame.

    As stream frames arrive with their 6-byte LICH chunks, this class
    tracks which chunks have been received and reconstructs the LSF
    once all 5 chunks are available.
    """

    def __init__(self) -> None:
        """Initialize collector."""
        self._chunks: List[Optional[bytes]] = [None] * 5
        self._complete: bool = False

    def add_chunk(self, chunk: bytes, frame_number: int) -> bool:
        """
        Add a LICH chunk.

        Args:
            chunk: 6-byte LICH chunk.
            frame_number: Frame number to determine chunk index.

        Returns:
            True if all chunks have been received.
        """
        if len(chunk) != 6:
            raise ValueError(f"Chunk must be 6 bytes, got {len(chunk)}")

        index = frame_number % 5
        self._chunks[index] = chunk

        # Check if all chunks received
        self._complete = all(c is not None for c in self._chunks)
        return self._complete

    @property
    def is_complete(self) -> bool:
        """Check if all chunks have been received."""
        return self._complete

    def get_lsf(self) -> Optional[LinkSetupFrame]:
        """
        Get the reconstructed Link Setup Frame.

        Returns:
            LinkSetupFrame if complete, None otherwise.
        """
        if not self._complete:
            return None

        # Concatenate chunks (first 28 bytes, ignoring 2-byte padding)
        data = b"".join(c for c in self._chunks if c is not None)[:28]
        return LinkSetupFrame.from_bytes(data)

    def get_lich(self) -> Optional[LICHFrame]:
        """
        Get the reconstructed LICH (legacy method).

        Returns:
            LICHFrame if complete, None otherwise.
        """
        if not self._complete:
            return None

        data = b"".join(c for c in self._chunks if c is not None)[:28]
        return LICHFrame.from_bytes(data)

    def reset(self) -> None:
        """Reset the collector for a new stream."""
        self._chunks = [None] * 5
        self._complete = False

    @property
    def chunks_received(self) -> int:
        """Get count of chunks received."""
        return sum(1 for c in self._chunks if c is not None)

    @staticmethod
    def recover_from_frames(frames: List[bytes]) -> Optional[bytes]:
        """
        Recover LICH bytes from a list of stream frames.

        Legacy static method for backward compatibility.

        Args:
            frames: List of stream frame bytes.

        Returns:
            28-byte LICH data if recoverable, None otherwise.
        """
        collector = LICHCollector()

        for i, frame_bytes in enumerate(frames):
            if len(frame_bytes) >= 6:
                chunk = frame_bytes[:6]
                if collector.add_chunk(chunk, i):
                    break

        if collector.is_complete:
            lsf = collector.get_lsf()
            return bytes(lsf) if lsf else None

        return None
