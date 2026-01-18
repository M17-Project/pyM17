"""
M17 Link Setup Frame (LSF)

The Link Setup Frame is transmitted at the start of a stream and contains:
- Destination address (6 bytes)
- Source address (6 bytes)
- TYPE field (2 bytes)
- META field (14 bytes)
- CRC-16 (2 bytes, optional - not included in IP frames)

Total: 28 bytes without CRC, 30 bytes with CRC

Port from libm17/payload/lsf.c with GNSS position encoding.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, Union

from m17.core.address import Address
from m17.core.crc import crc_m17
from m17.core.types import (
    M17DataType,
    M17EncryptionSubtype,
    M17EncryptionType,
    M17Type,
    build_type_field,
    parse_type_field,
)

__all__ = [
    "LinkSetupFrame",
    "MetaPosition",
    "MetaExtendedCallsign",
    "MetaNonce",
    "DataSource",
    "StationType",
    "ValidityField",
]


class DataSource(IntEnum):
    """GNSS data source type."""

    NONE = 0
    GNSS_FIX = 1
    GNSS_DR = 2  # Dead Reckoning
    GNSS_LAST = 3  # Last known
    USER_INPUT = 4
    EXTERNAL = 5
    RESERVED_6 = 6
    RESERVED_7 = 7
    RESERVED_8 = 8
    RESERVED_9 = 9
    RESERVED_10 = 10
    RESERVED_11 = 11
    RESERVED_12 = 12
    RESERVED_13 = 13
    RESERVED_14 = 14
    RESERVED_15 = 15


class StationType(IntEnum):
    """Transmitting station type."""

    FIXED = 0
    MOBILE = 1
    PORTABLE = 2
    RESERVED_3 = 3
    RESERVED_4 = 4
    RESERVED_5 = 5
    RESERVED_6 = 6
    RESERVED_7 = 7
    RESERVED_8 = 8
    RESERVED_9 = 9
    RESERVED_10 = 10
    RESERVED_11 = 11
    RESERVED_12 = 12
    RESERVED_13 = 13
    RESERVED_14 = 14
    RESERVED_15 = 15


class ValidityField(IntEnum):
    """GNSS data validity field."""

    NONE = 0
    POSITION_VALID = 1
    ALTITUDE_VALID = 2
    POSITION_ALTITUDE_VALID = 3
    SPEED_VALID = 4
    POSITION_SPEED_VALID = 5
    ALTITUDE_SPEED_VALID = 6
    ALL_VALID = 7
    # 8-15 reserved


@dataclass
class MetaPosition:
    """
    GNSS Position META field encoding.

    Encodes latitude, longitude, altitude, speed, and bearing
    into the 14-byte META field per M17 spec v2.0.0+ metric format.
    """

    data_source: DataSource = DataSource.NONE
    station_type: StationType = StationType.FIXED
    validity: ValidityField = ValidityField.ALL_VALID
    latitude: float = 0.0  # Degrees, -90 to +90
    longitude: float = 0.0  # Degrees, -180 to +180
    altitude: float = 0.0  # Meters, -500 to 32267.5
    speed: float = 0.0  # km/h, 0 to 2047.5
    bearing: int = 0  # Degrees, 0-511
    radius: float = 1.0  # Position uncertainty in meters (1, 2, 4, 8, 16, 32, 64, 128)

    def to_bytes(self) -> bytes:
        """
        Encode position data to 14-byte META field.

        Returns:
            14-byte META field.
        """
        tmp = bytearray(14)

        # Byte 0: data_source (4 bits) | station_type (4 bits)
        tmp[0] = ((self.data_source & 0x0F) << 4) | (self.station_type & 0x0F)

        # Byte 1: validity (4 bits) | log2_radius (3 bits) | bearing MSB (1 bit)
        # Calculate log2 radius
        radius_lut = [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0]
        log_r = 7
        for i, r in enumerate(radius_lut):
            if self.radius < r:
                log_r = i
                break

        tmp[1] = (
            ((self.validity & 0x0F) << 4)
            | ((log_r & 0x07) << 1)
            | ((self.bearing >> 8) & 0x01)
        )

        # Byte 2: bearing LSB
        tmp[2] = self.bearing & 0xFF

        # Bytes 3-5: latitude (24-bit signed, scaled)
        lat_scaled = int(self.latitude / 90.0 * 8388607.0)
        lat_scaled = max(-8388608, min(8388607, lat_scaled))
        lat_bytes = lat_scaled.to_bytes(3, "big", signed=True)
        tmp[3:6] = lat_bytes

        # Bytes 6-8: longitude (24-bit signed, scaled)
        lon_scaled = int(self.longitude / 180.0 * 8388607.0)
        lon_scaled = max(-8388608, min(8388607, lon_scaled))
        lon_bytes = lon_scaled.to_bytes(3, "big", signed=True)
        tmp[6:9] = lon_bytes

        # Bytes 9-10: altitude (16-bit, offset by 500m, scaled by 0.5m)
        alt_scaled = int((500.0 + self.altitude) * 2.0)
        alt_scaled = max(0, min(65535, alt_scaled))
        tmp[9] = (alt_scaled >> 8) & 0xFF
        tmp[10] = alt_scaled & 0xFF

        # Bytes 11-12: speed (12 bits, scaled by 0.5 km/h) + 4 bits reserved
        spd_scaled = int(self.speed * 2.0)
        spd_scaled = max(0, min(4095, spd_scaled))
        tmp[11] = (spd_scaled >> 4) & 0xFF
        tmp[12] = (spd_scaled & 0x0F) << 4  # Upper nibble

        # Byte 13: reserved
        tmp[13] = 0

        return bytes(tmp)

    @classmethod
    def from_bytes(cls, data: bytes) -> MetaPosition:
        """
        Decode 14-byte META field to position data.

        Args:
            data: 14-byte META field.

        Returns:
            MetaPosition with decoded values.
        """
        if len(data) != 14:
            raise ValueError(f"META field must be 14 bytes, got {len(data)}")

        radius_lut = [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0]

        data_source = DataSource((data[0] >> 4) & 0x0F)
        station_type = StationType(data[0] & 0x0F)
        validity = ValidityField((data[1] >> 4) & 0x0F)
        log_r = (data[1] >> 1) & 0x07
        radius = radius_lut[log_r]
        bearing = ((data[1] & 0x01) << 8) | data[2]

        # Latitude (24-bit signed)
        lat_bytes = bytes([data[3], data[4], data[5]])
        lat_scaled = int.from_bytes(lat_bytes, "big", signed=True)
        latitude = lat_scaled / 8388607.0 * 90.0

        # Longitude (24-bit signed)
        lon_bytes = bytes([data[6], data[7], data[8]])
        lon_scaled = int.from_bytes(lon_bytes, "big", signed=True)
        longitude = lon_scaled / 8388607.0 * 180.0

        # Altitude
        alt_scaled = (data[9] << 8) | data[10]
        altitude = alt_scaled / 2.0 - 500.0

        # Speed
        spd_scaled = (data[11] << 4) | ((data[12] >> 4) & 0x0F)
        speed = spd_scaled / 2.0

        return cls(
            data_source=data_source,
            station_type=station_type,
            validity=validity,
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            speed=speed,
            bearing=bearing,
            radius=radius,
        )


@dataclass
class MetaExtendedCallsign:
    """
    Extended Callsign Data (ECD) META field encoding.

    Contains two additional callsign fields for extended routing.
    """

    callsign_field_1: str = ""
    callsign_field_2: str = ""

    def to_bytes(self) -> bytes:
        """
        Encode extended callsign data to 14-byte META field.

        Returns:
            14-byte META field.
        """
        cf1_addr = Address(callsign=self.callsign_field_1 or " ")
        cf2_addr = Address(callsign=self.callsign_field_2 or " ")

        # Reserve space
        tmp = bytearray(14)

        # First callsign (6 bytes)
        tmp[0:6] = bytes(cf1_addr)

        # Second callsign (6 bytes)
        tmp[6:12] = bytes(cf2_addr)

        # Remaining 2 bytes are reserved/padding
        tmp[12] = 0
        tmp[13] = 0

        return bytes(tmp)

    @classmethod
    def from_bytes(cls, data: bytes) -> MetaExtendedCallsign:
        """
        Decode 14-byte META field to extended callsign data.

        Args:
            data: 14-byte META field.

        Returns:
            MetaExtendedCallsign with decoded values.
        """
        if len(data) != 14:
            raise ValueError(f"META field must be 14 bytes, got {len(data)}")

        cf1 = Address(addr=data[0:6]).callsign.strip()
        cf2 = Address(addr=data[6:12]).callsign.strip()

        return cls(callsign_field_1=cf1, callsign_field_2=cf2)


@dataclass
class MetaNonce:
    """
    Nonce META field for encryption.

    Contains 4-byte timestamp (Unix epoch - 2020 epoch) and 10-byte random data.
    """

    timestamp: int = 0  # Unix timestamp
    random_data: bytes = field(default_factory=lambda: bytes(10))

    # 2020 epoch offset (seconds from Unix epoch to Jan 1, 2020 00:00:00 UTC)
    _EPOCH_2020: int = 1577836800

    def to_bytes(self) -> bytes:
        """
        Encode nonce data to 14-byte META field.

        Returns:
            14-byte META field.
        """
        tmp = bytearray(14)

        # Convert Unix timestamp to 2020 epoch
        ts_2020 = self.timestamp - self._EPOCH_2020
        if ts_2020 < 0:
            ts_2020 = 0

        # Timestamp (4 bytes, big-endian)
        tmp[0:4] = ts_2020.to_bytes(4, "big")

        # Random data (10 bytes)
        random_bytes = self.random_data[:10] if len(self.random_data) >= 10 else self.random_data + bytes(10 - len(self.random_data))
        tmp[4:14] = random_bytes

        return bytes(tmp)

    @classmethod
    def from_bytes(cls, data: bytes) -> MetaNonce:
        """
        Decode 14-byte META field to nonce data.

        Args:
            data: 14-byte META field.

        Returns:
            MetaNonce with decoded values.
        """
        if len(data) != 14:
            raise ValueError(f"META field must be 14 bytes, got {len(data)}")

        ts_2020 = int.from_bytes(data[0:4], "big")
        timestamp = ts_2020 + cls._EPOCH_2020
        random_data = bytes(data[4:14])

        return cls(timestamp=timestamp, random_data=random_data)


@dataclass
class LinkSetupFrame:
    """
    M17 Link Setup Frame.

    Contains addressing and stream configuration information.

    Attributes:
        dst: Destination address.
        src: Source address.
        type_field: 16-bit TYPE field value.
        meta: 14-byte META field.
    """

    dst: Address
    src: Address
    type_field: int = 0x0005  # Default: voice stream, no encryption
    meta: bytes = field(default_factory=lambda: bytes(14))

    def __post_init__(self) -> None:
        """Validate and normalize fields after initialization."""
        # Convert string callsigns to Address objects if needed
        if isinstance(self.dst, str):
            object.__setattr__(self, "dst", Address(callsign=self.dst))
        if isinstance(self.src, str):
            object.__setattr__(self, "src", Address(callsign=self.src))

        # Ensure meta is exactly 14 bytes
        if len(self.meta) != 14:
            if len(self.meta) < 14:
                object.__setattr__(self, "meta", self.meta + bytes(14 - len(self.meta)))
            else:
                object.__setattr__(self, "meta", self.meta[:14])

    @property
    def crc(self) -> int:
        """Calculate CRC-16 for this LSF."""
        data = self.to_bytes_without_crc()
        return crc_m17(data)

    @property
    def stream_type(self) -> M17Type:
        """Get stream/packet type."""
        return M17Type(self.type_field & 0x01)

    @property
    def data_type(self) -> M17DataType:
        """Get data type."""
        return M17DataType((self.type_field >> 1) & 0x03)

    @property
    def encryption_type(self) -> M17EncryptionType:
        """Get encryption type."""
        return M17EncryptionType((self.type_field >> 3) & 0x03)

    @property
    def encryption_subtype(self) -> M17EncryptionSubtype:
        """Get encryption subtype / META interpretation."""
        return M17EncryptionSubtype((self.type_field >> 5) & 0x03)

    @property
    def can(self) -> int:
        """Get Channel Access Number."""
        return (self.type_field >> 7) & 0x0F

    def get_parsed_type(self):
        """Get fully parsed TYPE field."""
        return parse_type_field(self.type_field)

    def set_type(
        self,
        stream_type: M17Type = M17Type.STREAM,
        data_type: M17DataType = M17DataType.VOICE,
        encryption_type: M17EncryptionType = M17EncryptionType.NONE,
        encryption_subtype: M17EncryptionSubtype = M17EncryptionSubtype.TEXT,
        can: int = 0,
    ) -> None:
        """Set TYPE field from components."""
        self.type_field = build_type_field(
            stream_type, data_type, encryption_type, encryption_subtype, can
        )

    def set_position_meta(
        self,
        latitude: float,
        longitude: float,
        altitude: float = 0.0,
        speed: float = 0.0,
        bearing: int = 0,
        data_source: DataSource = DataSource.GNSS_FIX,
        station_type: StationType = StationType.MOBILE,
        validity: ValidityField = ValidityField.ALL_VALID,
        radius: float = 1.0,
    ) -> None:
        """
        Set META field with GNSS position data.

        Args:
            latitude: Latitude in degrees (-90 to +90).
            longitude: Longitude in degrees (-180 to +180).
            altitude: Altitude in meters (-500 to 32267.5).
            speed: Speed in km/h (0 to 2047.5).
            bearing: Bearing in degrees (0 to 511).
            data_source: GNSS data source type.
            station_type: Transmitting station type.
            validity: Data validity flags.
            radius: Position uncertainty in meters.
        """
        pos = MetaPosition(
            data_source=data_source,
            station_type=station_type,
            validity=validity,
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            speed=speed,
            bearing=bearing,
            radius=radius,
        )
        self.meta = pos.to_bytes()

    def get_position_meta(self) -> MetaPosition:
        """
        Get position data from META field.

        Returns:
            MetaPosition with decoded values.
        """
        return MetaPosition.from_bytes(self.meta)

    def set_extended_callsign_meta(self, cf1: str, cf2: str) -> None:
        """
        Set META field with Extended Callsign Data.

        Args:
            cf1: Callsign Field 1.
            cf2: Callsign Field 2.
        """
        ecd = MetaExtendedCallsign(callsign_field_1=cf1, callsign_field_2=cf2)
        self.meta = ecd.to_bytes()

    def get_extended_callsign_meta(self) -> MetaExtendedCallsign:
        """
        Get extended callsign data from META field.

        Returns:
            MetaExtendedCallsign with decoded values.
        """
        return MetaExtendedCallsign.from_bytes(self.meta)

    def set_nonce_meta(self, timestamp: int, random_data: bytes) -> None:
        """
        Set META field with nonce for encryption.

        Args:
            timestamp: Unix timestamp.
            random_data: 10-byte random data.
        """
        nonce = MetaNonce(timestamp=timestamp, random_data=random_data)
        self.meta = nonce.to_bytes()

    def get_nonce_meta(self) -> MetaNonce:
        """
        Get nonce data from META field.

        Returns:
            MetaNonce with decoded values.
        """
        return MetaNonce.from_bytes(self.meta)

    def to_bytes_without_crc(self) -> bytes:
        """
        Serialize LSF without CRC (28 bytes).

        Returns:
            28-byte LSF data.
        """
        return bytes(self.dst) + bytes(self.src) + self.type_field.to_bytes(2, "big") + self.meta

    def to_bytes(self) -> bytes:
        """
        Serialize LSF with CRC (30 bytes).

        Returns:
            30-byte LSF data with CRC.
        """
        data = self.to_bytes_without_crc()
        crc_value = crc_m17(data)
        return data + crc_value.to_bytes(2, "big")

    def __bytes__(self) -> bytes:
        """Return serialized LSF without CRC (for IP frames)."""
        return self.to_bytes_without_crc()

    @classmethod
    def from_bytes(cls, data: bytes, has_crc: bool = False) -> LinkSetupFrame:
        """
        Parse LSF from bytes.

        Args:
            data: 28 or 30 bytes of LSF data.
            has_crc: True if data includes 2-byte CRC.

        Returns:
            Parsed LinkSetupFrame.

        Raises:
            ValueError: If data length is wrong or CRC is invalid.
        """
        expected_len = 30 if has_crc else 28
        if len(data) != expected_len:
            raise ValueError(f"LSF must be {expected_len} bytes, got {len(data)}")

        if has_crc:
            # Verify CRC
            if crc_m17(data) != 0:
                raise ValueError("Invalid LSF CRC")
            data = data[:28]

        dst = Address(addr=data[0:6])
        src = Address(addr=data[6:12])
        type_field = int.from_bytes(data[12:14], "big")
        meta = bytes(data[14:28])

        return cls(dst=dst, src=src, type_field=type_field, meta=meta)

    def chunks(self, chunk_size: int = 6) -> list[bytes]:
        """
        Split LSF into chunks for LICH transmission.

        Args:
            chunk_size: Size of each chunk (default 6 bytes).

        Returns:
            List of byte chunks.
        """
        data = bytes(self)
        return [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]

    def __str__(self) -> str:
        """Return string representation."""
        return f"LSF: {self.src.callsign} -> {self.dst.callsign} [type=0x{self.type_field:04x}]"
