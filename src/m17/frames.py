"""Frame encoding (to 192 symbols) and decoding (from 184 payload symbols)."""

from dataclasses import dataclass

from . import fec
from .lsf import LSF, crc_ok
from .phy import SYNC_BERT, SYNC_LSF, SYNC_PKT, SYNC_STR, bits_to_symbols, symbols_to_soft, syncword_symbols

# ---- encoding


def lsf_frame(lsf: LSF) -> list[int]:
    """Link Setup Frame: 192 symbols."""
    bits = fec.conv_encode(lsf.to_bytes(), 240, fec.P1, 368)
    return syncword_symbols(SYNC_LSF) + bits_to_symbols(bits)


def stream_frame(
    lsf: LSF, fn: int, payload: bytes, last: bool = False, lich_counter: int | None = None
) -> list[int]:
    """Stream frame number ``fn`` with a 16-byte payload: 192 symbols.

    The frame carries LICH chunk ``lich_counter`` of the LSF (default ``fn % 6``).
    ``last`` marks the final frame of the transmission.
    """
    if len(payload) != 16:
        raise ValueError("stream payload must be 16 bytes")
    fn &= 0x7FFF
    lich = fec.encode_lich(lsf.lich(fn % 6 if lich_counter is None else lich_counter))
    fn |= 0x8000 if last else 0
    bits = lich + fec.conv_encode(fn.to_bytes(2, "big") + payload, 144, fec.P2, 272)
    return syncword_symbols(SYNC_STR) + bits_to_symbols(bits)


def packet_frame(chunk: bytes, counter: int, last: bool = False) -> list[int]:
    """Packet frame with up to 25 data bytes: 192 symbols.

    ``counter`` is the frame number (0 to 31), or for the ``last`` frame the
    number of valid bytes in it (1 to 25). See :mod:`m17.packet` for whole packets.
    """
    if len(chunk) > 25:
        raise ValueError("packet chunk must be at most 25 bytes")
    meta = (0x80 if last else 0) | ((counter & 0x1F) << 2)
    data = bytes(chunk).ljust(25, b"\0") + bytes([meta])
    bits = fec.conv_encode(data, 206, fec.P3, 368)
    return syncword_symbols(SYNC_PKT) + bits_to_symbols(bits)


def bert_frame(data: bytes) -> list[int]:
    """BERT frame from 197 bits (25 bytes, the last 3 bits unused): 192 symbols."""
    bits = fec.conv_encode(data, 197, fec.P2, 368)
    return syncword_symbols(SYNC_BERT) + bits_to_symbols(bits)


# ---- decoding


@dataclass
class LSFFrame:
    data: bytes  # the 30 decoded bytes
    metric: int  # Viterbi path metric: about 0xFFFF per corrected bit error, below that if error-free

    @property
    def crc_ok(self) -> bool:
        return crc_ok(self.data)

    @property
    def lsf(self) -> LSF:
        return LSF.from_bytes(self.data)


@dataclass
class StreamFrame:
    fn: int  # frame number, 0 to 0x7FFF
    last: bool
    payload: bytes  # 16 bytes
    lich: bytes  # 5 bytes of the LSF, zeros if the LICH could not be decoded
    lich_counter: int | None  # 0 to 5, None if the LICH could not be decoded
    metric: int
    decrypted: bool = False  # set by the Receiver when it decrypted the payload


@dataclass
class PacketFrame:
    data: bytes  # 25 bytes, for the last frame only ``counter`` of them are valid
    last: bool
    counter: int  # frame number, or the number of valid bytes in the last frame
    metric: int


def decode_lsf(symbols) -> LSFFrame:
    """Decode the 184 payload symbols of a Link Setup Frame."""
    out, metric = fec.viterbi_decode(symbols_to_soft(symbols), fec.P1)
    return LSFFrame(out[1:31], metric)


def decode_stream(symbols) -> StreamFrame:
    """Decode the 184 payload symbols of a stream frame."""
    soft = symbols_to_soft(symbols)
    lich = fec.decode_lich(soft[:96])
    out, metric = fec.viterbi_decode(soft[96:], fec.P2)
    fn = (out[1] << 8) | out[2]
    return StreamFrame(
        fn=fn & 0x7FFF,
        last=bool(fn & 0x8000),
        payload=out[3:19],
        lich=lich[:5] if lich else bytes(5),
        lich_counter=lich[5] >> 5 if lich else None,
        metric=metric,
    )


def decode_packet(symbols) -> PacketFrame:
    """Decode the 184 payload symbols of a packet frame."""
    out, metric = fec.viterbi_decode(symbols_to_soft(symbols), fec.P3)
    return PacketFrame(data=out[1:26], last=bool(out[26] & 0x80), counter=(out[26] >> 2) & 0x1F, metric=metric)
