"""Link Setup Frame (LSF): addresses, TYPE field, META field and CRC."""

import struct
from dataclasses import dataclass

from .callsign import callsign_from_bytes, callsign_to_bytes
from .crc import crc16

# TYPE field bits (M17 specification 2.0)
PACKET = 0
STREAM = 1
DATA = 1 << 1
VOICE = 2 << 1
VOICE_DATA = 3 << 1
ENCR_NONE = 0 << 3
ENCR_SCRAMBLER = 1 << 3
ENCR_AES = 2 << 3
SCRAMBLER_8 = 0 << 5  # encryption subtype, with ENCR_SCRAMBLER
SCRAMBLER_16 = 1 << 5
SCRAMBLER_24 = 2 << 5
AES_128 = 0 << 5  # encryption subtype, with ENCR_AES
AES_192 = 1 << 5
AES_256 = 2 << 5
META_TEXT = 0 << 5  # encryption subtype, with ENCR_NONE: META field content
META_POSITION = 1 << 5
META_ECD = 2 << 5
SIGNED = 1 << 11


def can(number: int) -> int:
    """TYPE bits for a Channel Access Number (0 to 15)."""
    return (number & 0xF) << 7


@dataclass
class LSF:
    """Link Setup Frame contents. ``meta`` is the 14-byte META field."""

    dst: str = "@ALL"
    src: str = ""
    type: int = STREAM | VOICE
    meta: bytes = bytes(14)

    def to_bytes(self) -> bytes:
        """The 30 transmitted bytes: DST, SRC, TYPE, META and CRC."""
        if len(self.meta) != 14:
            raise ValueError("META must be 14 bytes")
        body = callsign_to_bytes(self.dst) + callsign_to_bytes(self.src)
        body += self.type.to_bytes(2, "big") + bytes(self.meta)
        return body + crc16(body).to_bytes(2, "big")

    @classmethod
    def from_bytes(cls, data: bytes) -> "LSF":
        """Parse 30 bytes (the CRC is not checked, see :func:`crc_ok`)."""
        if len(data) < 28:
            raise ValueError("LSF needs at least 28 bytes")
        return cls(
            dst=callsign_from_bytes(data[0:6]),
            src=callsign_from_bytes(data[6:12]),
            type=int.from_bytes(data[12:14], "big"),
            meta=bytes(data[14:28]),
        )

    @property
    def can(self) -> int:
        return (self.type >> 7) & 0xF

    def lich(self, counter: int) -> bytes:
        """LICH chunk ``counter`` (0 to 5): 5 bytes of the LSF and the counter byte."""
        if not 0 <= counter <= 5:
            raise ValueError("LICH counter must be 0 to 5")
        return self.to_bytes()[counter * 5 : counter * 5 + 5] + bytes([counter << 5])


def crc_ok(data: bytes) -> bool:
    """True if a 30-byte LSF has a valid CRC."""
    return len(data) == 30 and crc16(data) == 0


# ---- META field helpers


def _f32(x: float) -> float:
    """Round to float32, so the arithmetic matches libm17's."""
    return struct.unpack("f", struct.pack("f", x))[0]


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if not x >= lo else min(x, hi)  # NaN -> lo


def _roundf(x: float) -> int:
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)


_RADIUS = (1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0)


@dataclass
class Position:
    """GNSS position META content. Units: degrees, metres, km/h, metres."""

    lat: float
    lon: float
    altitude: float = 0.0
    bearing: int = 0
    speed: float = 0.0
    radius: float = 1.0
    validity: int = 0xF  # lat/lon, altitude, speed and bearing, radius
    source: int = 0
    station: int = 0

    def to_meta(self) -> bytes:
        """Encode to 14 META bytes."""
        # float32 steps as in libm17: clamp, divide, scale, truncate
        lat = _f32(_f32(_clamp(_f32(self.lat), -90.0, 90.0) / 90.0) * 8388607.0)
        lon = _f32(_f32(_clamp(_f32(self.lon), -180.0, 180.0) / 180.0) * 8388607.0)
        alt = _roundf(_f32((500.0 + _clamp(_f32(self.altitude), -500.0, 32267.5)) * 2.0)) & 0xFFFF
        spd = _roundf(_f32(_clamp(_f32(self.speed), 0.0, 2047.5) * 2.0)) & 0xFFF
        radius = next((i for i, r in enumerate(_RADIUS) if _f32(self.radius) <= r), 7)
        bearing = self.bearing & 0x1FF
        return bytes(
            [((self.source & 0xF) << 4) | (self.station & 0xF),
             ((self.validity & 0xF) << 4) | (radius << 1) | (bearing >> 8),
             bearing & 0xFF]
        ) + (int(lat) & 0xFFFFFF).to_bytes(3, "big") + (int(lon) & 0xFFFFFF).to_bytes(3, "big") + bytes(
            [alt >> 8, alt & 0xFF, spd >> 4, (spd & 0xF) << 4, 0]
        )

    @classmethod
    def from_meta(cls, meta: bytes) -> "Position":
        """Decode 14 META bytes."""

        def s24(b: bytes) -> int:
            v = int.from_bytes(b, "big")
            return v - (1 << 24) if v & 0x800000 else v

        return cls(
            lat=s24(meta[3:6]) / 8388607.0 * 90.0,
            lon=s24(meta[6:9]) / 8388607.0 * 180.0,
            altitude=-500.0 + ((meta[9] << 8) | meta[10]) / 2.0,
            bearing=((meta[1] & 1) << 8) | meta[2],
            speed=((meta[11] << 4) | (meta[12] >> 4)) / 2.0,
            radius=_RADIUS[(meta[1] >> 1) & 7],
            validity=meta[1] >> 4,
            source=meta[0] >> 4,
            station=meta[0] & 0xF,
        )


def meta_ecd(callsign_1: str, callsign_2: str = "") -> bytes:
    """Extended Callsign Data META: two callsigns (e.g. the originator and a reflector)."""
    return callsign_to_bytes(callsign_1) + (callsign_to_bytes(callsign_2) if callsign_2 else bytes(6)) + bytes(2)


def meta_nonce(timestamp: int, random: bytes) -> bytes:
    """Nonce META for encryption: 32-bit time since 2020-01-01 UTC and 10 random bytes."""
    if len(random) != 10:
        raise ValueError("the random part must be 10 bytes")
    return ((timestamp - 1577836800) & 0xFFFFFFFF).to_bytes(4, "big") + bytes(random)
