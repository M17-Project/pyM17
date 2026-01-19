"""
M17 Stream Frame Definitions

Stream frames carry real-time voice and/or data content.
Each frame contains:
- LICH chunk (6 bytes) - portion of the Link Setup Frame
- Frame Number (2 bytes) - counter and EOT flag
- Payload (16 bytes) - voice/data content
- CRC (2 bytes) - for RF frames

Note: IP frames have a different structure (see ip.py).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Optional, Union

from m17.core.crc import crc_m17
from m17.core.constants import EOT_MARKER

__all__ = ["M17Payload", "StreamFrame"]


@dataclass
class M17Payload:
    """
    M17 Stream Payload.

    Contains frame number, payload data, and optional CRC.

    Attributes:
        frame_number: 16-bit frame counter (MSB indicates EOT).
        payload: 16-byte (128-bit) payload data.
        crc: Optional 16-bit CRC for RF frames.
    """

    frame_number: int = 0
    payload: bytes = field(default_factory=lambda: bytes(16))
    crc: int = 0

    _STRUCT = struct.Struct(">H16sH")  # Big-endian: frame_num(2) + payload(16) + crc(2)

    def __post_init__(self) -> None:
        """Validate and normalize fields."""
        # Ensure payload is exactly 16 bytes
        if len(self.payload) != 16:
            if len(self.payload) < 16:
                object.__setattr__(
                    self, "payload", self.payload + bytes(16 - len(self.payload))
                )
            else:
                object.__setattr__(self, "payload", self.payload[:16])

        # Validate frame number
        if not 0 <= self.frame_number <= 0xFFFF:
            raise ValueError(f"Frame number must be 0-65535, got {self.frame_number}")

    @property
    def is_last_frame(self) -> bool:
        """Check if this is the last frame (EOT)."""
        return (self.frame_number & 0x8000) != 0

    @property
    def sequence_number(self) -> int:
        """Get the actual sequence number (without EOT flag)."""
        return self.frame_number & 0x7FFF

    def set_last_frame(self, is_last: bool = True) -> None:
        """Set the EOT flag."""
        if is_last:
            self.frame_number |= 0x8000
        else:
            self.frame_number &= 0x7FFF

    def calculate_crc(self, lich_chunk: bytes) -> int:
        """
        Calculate CRC for this payload with its LICH chunk.

        Args:
            lich_chunk: 6-byte LICH chunk for this frame.

        Returns:
            16-bit CRC value.
        """
        data = lich_chunk + self.frame_number.to_bytes(2, "big") + self.payload
        return crc_m17(data)

    def to_bytes(self) -> bytes:
        """
        Serialize payload to bytes.

        Returns:
            20-byte serialized payload (frame_num + payload + crc).
        """
        return self._STRUCT.pack(self.frame_number, self.payload, self.crc)

    def to_bytes_without_crc(self) -> bytes:
        """
        Serialize payload without CRC.

        Returns:
            18-byte serialized payload (frame_num + payload).
        """
        return self.frame_number.to_bytes(2, "big") + self.payload

    def __bytes__(self) -> bytes:
        """Return serialized payload."""
        return self.to_bytes()

    @classmethod
    def from_bytes(cls, data: bytes, has_crc: bool = True) -> M17Payload:
        """
        Parse payload from bytes.

        Args:
            data: 18 or 20 bytes of payload data.
            has_crc: True if data includes 2-byte CRC.

        Returns:
            Parsed M17Payload.
        """
        if has_crc:
            if len(data) != 20:
                raise ValueError(f"Payload with CRC must be 20 bytes, got {len(data)}")
            frame_number, payload, crc = cls._STRUCT.unpack(data)
        else:
            if len(data) != 18:
                raise ValueError(f"Payload without CRC must be 18 bytes, got {len(data)}")
            frame_number = int.from_bytes(data[0:2], "big")
            payload = bytes(data[2:18])
            crc = 0

        return cls(frame_number=frame_number, payload=payload, crc=crc)

    def __str__(self) -> str:
        """Return string representation."""
        eot = " [EOT]" if self.is_last_frame else ""
        return f"Payload[{self.sequence_number}]{eot}: {self.payload.hex()}"

    def __eq__(self, other: object) -> bool:
        """Compare payloads."""
        if isinstance(other, M17Payload):
            return (
                self.frame_number == other.frame_number
                and self.payload == other.payload
            )
        if isinstance(other, bytes):
            return bytes(self) == other
        return NotImplemented


@dataclass
class StreamFrame:
    """
    M17 Stream Frame (RF format).

    Contains LICH chunk + payload for over-the-air transmission.
    This is the format used after FEC encoding for RF.

    Attributes:
        lich_chunk: 6-byte LICH chunk.
        payload: M17Payload with frame data.
    """

    # Class constants
    payload_sz: int = 16  # 16 bytes of payload data

    lich_chunk: bytes = field(default_factory=lambda: bytes(6))
    payload: M17Payload = field(default_factory=M17Payload)

    _STRUCT = struct.Struct(">6sH16sH")  # lich(6) + fn(2) + payload(16) + crc(2)

    def __post_init__(self) -> None:
        """Validate and normalize fields."""
        # Ensure LICH chunk is exactly 6 bytes
        if len(self.lich_chunk) != 6:
            if len(self.lich_chunk) < 6:
                object.__setattr__(
                    self,
                    "lich_chunk",
                    self.lich_chunk + bytes(6 - len(self.lich_chunk)),
                )
            else:
                object.__setattr__(self, "lich_chunk", self.lich_chunk[:6])

    @property
    def frame_number(self) -> int:
        """Get frame number from payload."""
        return self.payload.frame_number

    @property
    def is_last_frame(self) -> bool:
        """Check if this is the last frame."""
        return self.payload.is_last_frame

    def calculate_crc(self) -> int:
        """Calculate CRC for this frame."""
        return self.payload.calculate_crc(self.lich_chunk)

    def to_bytes(self) -> bytes:
        """
        Serialize frame to bytes.

        Returns:
            26-byte serialized frame.
        """
        crc = self.calculate_crc()
        return self._STRUCT.pack(
            self.lich_chunk,
            self.payload.frame_number,
            self.payload.payload,
            crc,
        )

    def __bytes__(self) -> bytes:
        """Return serialized frame."""
        return self.to_bytes()

    @classmethod
    def from_bytes(cls, data: bytes) -> StreamFrame:
        """
        Parse stream frame from bytes.

        Args:
            data: 26 bytes of frame data.

        Returns:
            Parsed StreamFrame.
        """
        if len(data) != 26:
            raise ValueError(f"Stream frame must be 26 bytes, got {len(data)}")

        lich_chunk, frame_number, payload_data, crc = cls._STRUCT.unpack(data)

        payload = M17Payload(
            frame_number=frame_number, payload=payload_data, crc=crc
        )

        return cls(lich_chunk=lich_chunk, payload=payload)

    @classmethod
    def from_bytes_legacy(cls, data: bytes) -> StreamFrame:
        """
        Parse stream frame from legacy format (18 bytes without CRC).

        Args:
            data: 18 bytes of frame data.

        Returns:
            Parsed StreamFrame.
        """
        if len(data) != 18:
            raise ValueError(f"Legacy frame must be 18 bytes, got {len(data)}")

        lich_chunk = bytes(data[0:6])
        frame_number = int.from_bytes(data[6:8], "big")
        payload_data = bytes(data[8:18])

        # Calculate CRC
        payload = M17Payload(frame_number=frame_number, payload=payload_data)
        crc = payload.calculate_crc(lich_chunk)
        payload.crc = crc

        return cls(lich_chunk=lich_chunk, payload=payload)

    def __str__(self) -> str:
        """Return string representation."""
        return f"StreamFrame[{self.payload.sequence_number}]: lich={self.lich_chunk.hex()}"

    def __eq__(self, other: object) -> bool:
        """Compare frames."""
        if isinstance(other, StreamFrame):
            return self.lich_chunk == other.lich_chunk and self.payload == other.payload
        if isinstance(other, bytes):
            return bytes(self) == other
        return NotImplemented
