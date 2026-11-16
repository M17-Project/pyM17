"""M17 CRC-16: polynomial 0x5935, initial value 0xFFFF, no reflection."""

POLY = 0x5935


def _table() -> list[int]:
    table = []
    for byte in range(256):
        crc = byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ POLY) if crc & 0x8000 else (crc << 1)
        table.append(crc & 0xFFFF)
    return table


_TABLE = _table()


def crc16(data: bytes) -> int:
    """CRC of ``data``. Appending it big-endian gives a CRC of 0 over the whole."""
    crc = 0xFFFF
    for byte in data:
        crc = ((crc << 8) & 0xFFFF) ^ _TABLE[(crc >> 8) ^ byte]
    return crc
