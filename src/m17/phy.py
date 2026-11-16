"""Physical layer: symbols, syncwords, interleaver, randomizer and RRC filter.

Symbols are the 4FSK levels -3, -1, +1, +3 at 4800 symbols per second. A frame
is 192 symbols: an 8-symbol syncword and 184 payload symbols (368 bits).
"""

import math
import struct

SYM_PER_SWD = 8
SYM_PER_PLD = 184
SYM_PER_FRA = 192

SYMBOL_MAP = (+1, +3, -1, -3)  # dibit value (b1 * 2 + b0) to symbol

SYNC_LSF = 0x55F7
SYNC_STR = 0xFF5D
SYNC_PKT = 0x75FF
SYNC_BERT = 0xDF55
EOT_MARKER = 0x555D

# quadratic permutation polynomial interleaver: f(i) = 45 i + 92 i^2 mod 368
INTERLEAVER = tuple((45 * i + 92 * i * i) % 368 for i in range(368))

RANDOMIZER = bytes.fromhex(
    "d6b5e23082ff8462ba4e9690d898dd5d0cc85243911df86e682f35da14eacd76198dd580d1338713"
    "57182d2978c3"
)


def syncword_symbols(word: int) -> list[int]:
    """The 8 symbols of a 16-bit syncword."""
    return [SYMBOL_MAP[(word >> (14 - 2 * i)) & 3] for i in range(8)]


def preamble(bert: bool = False) -> list[int]:
    """40 ms preamble: alternating +3, -3 (before an LSF) or -3, +3 (before BERT)."""
    return [-3, +3] * 96 if bert else [+3, -3] * 96


def eot() -> list[int]:
    """40 ms End of Transmission marker."""
    return syncword_symbols(EOT_MARKER) * 24


def _random_bit(i: int) -> int:
    return (RANDOMIZER[i // 8] >> (7 - i % 8)) & 1


def bits_to_symbols(bits: list[int]) -> list[int]:
    """Interleave, randomize and map 368 type-3 bits to 184 payload symbols."""
    out = []
    for i in range(SYM_PER_PLD):
        b1 = bits[INTERLEAVER[2 * i]] ^ _random_bit(2 * i)
        b0 = bits[INTERLEAVER[2 * i + 1]] ^ _random_bit(2 * i + 1)
        out.append(SYMBOL_MAP[b1 * 2 + b0])
    return out


# ---- soft slicer, float32 arithmetic as in libm17


def _f32(x: float) -> float:
    return struct.unpack("f", struct.pack("f", x))[0]


_INV_D = _f32(65535.0 / 2.0)  # 0xFFFF per distance between neighbouring levels
_C3 = _f32(-_INV_D * 1.0)
_C1 = _f32(_INV_D * -1.0)


def _slice(x: float) -> tuple[int, int]:
    """Soft bits (b1, b0) for one symbol."""
    x = _f32(x)
    if not x == x:  # NaN
        return 0xFFFF, 0xFFFF
    if x >= 3:
        b0 = 0xFFFF
    elif x >= 1:
        b0 = int(_f32(_C3 + _f32(x * _INV_D)))
    elif x >= -1:
        b0 = 0
    elif x >= -3:
        b0 = int(_f32(_C1 - _f32(x * _INV_D)))
    else:
        b0 = 0xFFFF
    if x >= 1:
        b1 = 0
    elif x >= -1:
        b1 = int(_f32(0x7FFF - _f32(x * _INV_D)))
    else:
        b1 = 0xFFFF
    return b1, b0


def symbols_to_soft(symbols) -> list[int]:
    """Slice, derandomize and deinterleave 184 payload symbols to 368 soft bits.

    The symbols must be synchronized, one sample per symbol, scaled to the
    nominal levels -3, -1, +1, +3.
    """
    if len(symbols) < SYM_PER_PLD:
        raise ValueError(f"need {SYM_PER_PLD} symbols")
    out = [0] * (2 * SYM_PER_PLD)
    for i in range(SYM_PER_PLD):
        b1, b0 = _slice(float(symbols[i]))
        if _random_bit(2 * i):
            b1 = 0xFFFF - b1
        if _random_bit(2 * i + 1):
            b0 = 0xFFFF - b0
        out[INTERLEAVER[2 * i]] = b1
        out[INTERLEAVER[2 * i + 1]] = b0
    return out


def distance(symbols, reference) -> float:
    """Euclidean distance between received symbols and ideal ones (syncword detection)."""
    return math.sqrt(sum((float(a) - b) ** 2 for a, b in zip(symbols, reference)))


# ---- root raised cosine filter


def rrc_taps(sps: int = 10, span: int = 8, alpha: float = 0.5) -> list[float]:
    """RRC filter taps for ``sps`` samples per symbol, normalized to unit energy.

    sps=10 gives the 48 kHz filter, sps=5 the 24 kHz one (identical to libm17's).
    """
    taps = []
    for i in range(span * sps + 1):
        t = (i - span * sps / 2) / sps
        if t == 0:
            h = 1 - alpha + 4 * alpha / math.pi
        elif abs(abs(4 * alpha * t) - 1) < 1e-12:
            h = alpha / math.sqrt(2) * (
                (1 + 2 / math.pi) * math.sin(math.pi / (4 * alpha))
                + (1 - 2 / math.pi) * math.cos(math.pi / (4 * alpha))
            )
        else:
            h = (math.sin(math.pi * t * (1 - alpha)) + 4 * alpha * t * math.cos(math.pi * t * (1 + alpha))) / (
                math.pi * t * (1 - (4 * alpha * t) ** 2)
            )
        taps.append(h)
    norm = math.sqrt(sum(h * h for h in taps))
    return [h / norm for h in taps]


def modulate(symbols, sps: int = 10):
    """Upsample and RRC filter symbols to baseband for an FM modulator (needs numpy).

    The output has ``sps`` samples per symbol and is delayed by half the filter
    length (4 symbols).
    """
    import numpy as np

    x = np.zeros(len(symbols) * sps)
    x[::sps] = symbols
    return np.convolve(x, rrc_taps(sps)) * math.sqrt(sps)


def matched_filter(samples, sps: int = 10):
    """RRC filter received FM-demodulated samples (needs numpy). Symbol timing recovery is up to the caller."""
    import numpy as np

    return np.convolve(np.asarray(samples, dtype=float), rrc_taps(sps)) / math.sqrt(sps)
