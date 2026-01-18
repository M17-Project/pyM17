"""
M17 IP Frame Definitions

IP frames are used for M17-over-IP networking (reflectors, etc.).
Each IP frame contains:
- Magic number "M17 " (4 bytes)
- Stream ID (2 bytes)
- Full LICH/LSF data (28 bytes)
- Frame Number (2 bytes)
- Payload (16 bytes)
- CRC (2 bytes)

Total: 54 bytes

This module maintains backward compatibility with the existing IPFrame class.
"""

from __future__ import annotations

import random
import struct
from dataclasses import dataclass, field
from typing import Optional, Union

from m17.core.address import Address
from m17.core.crc import crc_m17
from m17.core.constants import M17_MAGIC_NUMBER
from m17.frames.lsf import LinkSetupFrame
from m17.frames.stream import M17Payload

__all__ = ["IPFrame"]


@dataclass
class IPFrame:
    """
    M17 IP Frame for network transmission.

    This is the format used for M17-over-IP protocols (reflectors, etc.).

    Attributes:
        magic_number: 4-byte magic "M17 ".
        stream_id: 16-bit stream identifier.
        lsf: Full Link Setup Frame data.
        payload: M17Payload with frame data.
    """

    magic_number: bytes = field(default_factory=lambda: M17_MAGIC_NUMBER)
    stream_id: int = 0
    lsf: LinkSetupFrame = field(default_factory=lambda: LinkSetupFrame(
        dst=Address(callsign="@ALL"),
        src=Address(callsign="N0CALL"),
    ))
    payload: M17Payload = field(default_factory=M17Payload)

    # Struct for packing/unpacking
    # 4s: magic, H: stream_id, 6s: dst, 6s: src, H: type, 14s: meta, H: fn, 16s: payload, H: crc
    _STRUCT = struct.Struct(">4sH6s6sH14sH16sH")

    def __post_init__(self) -> None:
        """Validate fields."""
        if len(self.magic_number) != 4:
            raise ValueError(f"Magic number must be 4 bytes, got {len(self.magic_number)}")
        if not 0 <= self.stream_id <= 0xFFFF:
            raise ValueError(f"Stream ID must be 0-65535, got {self.stream_id}")

    @property
    def frame_number(self) -> int:
        """Get frame number."""
        return self.payload.frame_number

    @property
    def is_last_frame(self) -> bool:
        """Check if this is the last frame."""
        return self.payload.is_last_frame

    @property
    def dst(self) -> Address:
        """Get destination address."""
        return self.lsf.dst

    @property
    def src(self) -> Address:
        """Get source address."""
        return self.lsf.src

    @property
    def stream_type(self) -> int:
        """Get stream type from LSF."""
        return self.lsf.type_field

    # Legacy property names for backward compatibility
    @property
    def lich(self) -> LinkSetupFrame:
        """Get LSF (legacy name 'lich')."""
        return self.lsf

    @property
    def m17_payload(self) -> M17Payload:
        """Get payload (legacy name)."""
        return self.payload

    @property
    def nonce(self) -> bytes:
        """Get nonce/META from LSF."""
        return self.lsf.meta

    def calculate_crc(self) -> int:
        """
        Calculate CRC for this IP frame.

        The CRC is calculated over the LICH, frame number, and payload.
        """
        data = (
            bytes(self.lsf.dst)
            + bytes(self.lsf.src)
            + self.lsf.type_field.to_bytes(2, "big")
            + self.lsf.meta
            + self.payload.frame_number.to_bytes(2, "big")
            + self.payload.payload
        )
        return crc_m17(data)

    def to_bytes(self) -> bytes:
        """
        Serialize IP frame to bytes.

        Returns:
            54-byte serialized IP frame.
        """
        crc = self.calculate_crc()
        return self._STRUCT.pack(
            self.magic_number,
            self.stream_id,
            bytes(self.lsf.dst),
            bytes(self.lsf.src),
            self.lsf.type_field,
            self.lsf.meta,
            self.payload.frame_number,
            self.payload.payload,
            crc,
        )

    def pack(self) -> bytes:
        """Serialize IP frame (legacy method)."""
        return self.to_bytes()

    def __bytes__(self) -> bytes:
        """Return serialized IP frame."""
        return self.to_bytes()

    @classmethod
    def from_bytes(cls, data: bytes) -> IPFrame:
        """
        Parse IP frame from bytes.

        Args:
            data: 54 bytes of IP frame data.

        Returns:
            Parsed IPFrame.

        Raises:
            ValueError: If data is wrong size or not an M17 frame.
        """
        if len(data) != 54:
            raise ValueError(f"IP frame must be 54 bytes, got {len(data)}")

        (
            magic,
            stream_id,
            dst_bytes,
            src_bytes,
            type_field,
            meta,
            frame_number,
            payload_data,
            crc,
        ) = cls._STRUCT.unpack(data)

        if magic != M17_MAGIC_NUMBER:
            raise ValueError(f"Invalid magic number: {magic!r}")

        dst = Address(addr=dst_bytes)
        src = Address(addr=src_bytes)

        lsf = LinkSetupFrame(dst=dst, src=src, type_field=type_field, meta=meta)
        payload = M17Payload(frame_number=frame_number, payload=payload_data, crc=crc)

        return cls(
            magic_number=magic,
            stream_id=stream_id,
            lsf=lsf,
            payload=payload,
        )

    @classmethod
    def unpack(cls, data: bytes) -> IPFrame:
        """Parse IP frame (legacy method)."""
        return cls.from_bytes(data)

    @staticmethod
    def is_m17(data: bytes) -> bool:
        """
        Check if bytes are an M17 IP frame.

        Args:
            data: Bytes to check.

        Returns:
            True if starts with M17 magic number.
        """
        return len(data) >= 4 and data[:4] == M17_MAGIC_NUMBER

    @classmethod
    def create(
        cls,
        dst: Union[str, Address],
        src: Union[str, Address],
        stream_id: Optional[int] = None,
        stream_type: int = 0x0005,  # Voice stream, no encryption
        nonce: bytes = b"",
        frame_number: int = 0,
        payload: bytes = b"",
    ) -> IPFrame:
        """
        Create a new IP frame with the given parameters.

        Args:
            dst: Destination callsign or Address.
            src: Source callsign or Address.
            stream_id: Stream ID (random if not specified).
            stream_type: TYPE field value.
            nonce: META/nonce field data.
            frame_number: Frame number.
            payload: Payload data.

        Returns:
            New IPFrame.
        """
        if isinstance(dst, str):
            dst = Address(callsign=dst)
        if isinstance(src, str):
            src = Address(callsign=src)

        if stream_id is None:
            stream_id = random.randint(1, 0xFFFF)

        # Pad nonce to 14 bytes
        if len(nonce) < 14:
            nonce = nonce + bytes(14 - len(nonce))
        elif len(nonce) > 14:
            nonce = nonce[:14]

        # Pad payload to 16 bytes
        if len(payload) < 16:
            payload = payload + bytes(16 - len(payload))
        elif len(payload) > 16:
            payload = payload[:16]

        lsf = LinkSetupFrame(dst=dst, src=src, type_field=stream_type, meta=nonce)
        m17_payload = M17Payload(frame_number=frame_number, payload=payload)

        return cls(stream_id=stream_id, lsf=lsf, payload=m17_payload)

    def get_pack_values(self) -> list:
        """Get values for struct packing (legacy compatibility)."""
        return [
            *self.magic_number,
            self.stream_id,
            *bytes(self.lsf.dst),
            *bytes(self.lsf.src),
            self.lsf.type_field,
            *self.lsf.meta,
            self.payload.frame_number,
            *self.payload.payload,
            self.payload.crc,
        ]

    def __str__(self) -> str:
        """Return string representation."""
        return (
            f"IPFrame[SID={self.stream_id:04x}]: "
            f"{self.lsf.src.callsign} -> {self.lsf.dst.callsign} "
            f"[FN={self.payload.sequence_number}]"
        )

    def __repr__(self) -> str:
        """Return detailed representation."""
        return (
            f"IPFrame(stream_id=0x{self.stream_id:04x}, "
            f"src={self.lsf.src.callsign!r}, dst={self.lsf.dst.callsign!r}, "
            f"type=0x{self.lsf.type_field:04x}, fn={self.payload.frame_number})"
        )

    def __eq__(self, other: object) -> bool:
        """Compare frames."""
        if isinstance(other, IPFrame):
            return bytes(self) == bytes(other)
        if isinstance(other, bytes):
            return bytes(self) == other
        return NotImplemented

    @staticmethod
    def dict_from_bytes(data: bytes) -> dict:
        """
        Parse IP frame to dictionary (legacy method).

        Args:
            data: 54 bytes of IP frame data.

        Returns:
            Dictionary with frame fields.
        """
        frame = IPFrame.from_bytes(data)
        return {
            "magic_number": frame.magic_number,
            "stream_id": frame.stream_id,
            "dst": frame.lsf.dst,
            "src": frame.lsf.src,
            "stream_type": frame.lsf.type_field,
            "nonce": frame.lsf.meta,
            "frame_number": frame.payload.frame_number,
            "payload": frame.payload.payload,
            "crc": frame.payload.crc,
        }
