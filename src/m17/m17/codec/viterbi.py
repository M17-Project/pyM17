"""
M17 Viterbi Decoder

Soft-decision Viterbi decoder for K=5 rate 1/2 convolutional code.
16-state trellis with soft metric accumulation.

Port from libm17/decode/viterbi.c
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from m17.codec.puncture import PUNCTURE_P1, PUNCTURE_P2, PUNCTURE_P3, depuncture

__all__ = [
    "viterbi_decode",
    "viterbi_decode_punctured",
    "ViterbiDecoder",
]

# Number of states in the trellis (2^(K-1) = 2^4 = 16)
CONVOL_STATES: int = 16

# Maximum history length (in bit pairs)
VITERBI_HIST_LEN: int = 244

# Cost tables for soft decoding
# G1 outputs for each state transition
COST_TABLE_0: Tuple[int, ...] = (0, 0, 0, 0, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF)
# G2 outputs for each state transition
COST_TABLE_1: Tuple[int, ...] = (0, 0xFFFF, 0xFFFF, 0, 0, 0xFFFF, 0xFFFF, 0)


def _q_abs_diff(a: int, b: int) -> int:
    """Calculate absolute difference between two values."""
    return abs(a - b)


class ViterbiDecoder:
    """
    Stateful Viterbi decoder for streaming decoding.

    Maintains internal state for decoding bit pairs as they arrive.
    """

    def __init__(self) -> None:
        """Initialize decoder state."""
        self.reset()

    def reset(self) -> None:
        """Reset decoder to initial state."""
        self._history: List[int] = [0] * VITERBI_HIST_LEN
        self._prev_metrics: List[int] = [0x3FFFFFFF] * CONVOL_STATES
        self._curr_metrics: List[int] = [0] * CONVOL_STATES
        self._prev_metrics[0] = 0  # Only state 0 is valid at start
        self._pos: int = 0

    def decode_bit(self, s0: int, s1: int) -> None:
        """
        Decode one bit pair and update trellis.

        Args:
            s0: Soft value for G1 output (0 = strong 0, 0xFFFF = strong 1).
            s1: Soft value for G2 output.
        """
        if self._pos >= VITERBI_HIST_LEN:
            raise RuntimeError("Viterbi history overflow")

        for i in range(CONVOL_STATES // 2):
            e0 = COST_TABLE_0[i]
            e1 = COST_TABLE_1[i]

            bm0 = _q_abs_diff(e0, s0) + _q_abs_diff(e1, s1)
            bm1 = 0x1FFFE - bm0

            m0 = self._prev_metrics[i] + bm0
            m1 = self._prev_metrics[i + CONVOL_STATES // 2] + bm1

            m2 = self._prev_metrics[i] + bm1
            m3 = self._prev_metrics[i + CONVOL_STATES // 2] + bm0

            i0 = 2 * i
            i1 = i0 + 1

            if m0 >= m1:
                self._history[self._pos] |= 1 << i0
                self._curr_metrics[i0] = m1
            else:
                self._history[self._pos] &= ~(1 << i0)
                self._curr_metrics[i0] = m0

            if m2 >= m3:
                self._history[self._pos] |= 1 << i1
                self._curr_metrics[i1] = m3
            else:
                self._history[self._pos] &= ~(1 << i1)
                self._curr_metrics[i1] = m2

        # Swap metrics
        self._prev_metrics, self._curr_metrics = (
            self._curr_metrics,
            self._prev_metrics,
        )
        self._pos += 1

    def chainback(self, output_bits: int) -> Tuple[bytes, int]:
        """
        Perform chainback to get decoded bytes.

        Args:
            output_bits: Number of output bits expected.

        Returns:
            Tuple of (decoded bytes, minimum cost).
        """
        state = 0
        bit_pos = output_bits + 4  # Include flush bits
        out_bytes = bytearray((bit_pos + 7) // 8)
        pos = self._pos

        while pos > 0:
            bit_pos -= 1
            pos -= 1
            bit = self._history[pos] & (1 << (state >> 4))
            state >>= 1
            if bit:
                state |= 0x80
                out_bytes[bit_pos // 8] |= 1 << (7 - (bit_pos % 8))

        # Find minimum cost
        cost = self._prev_metrics[0]
        for i in range(CONVOL_STATES):
            if self._prev_metrics[i] < cost:
                cost = self._prev_metrics[i]

        return bytes(out_bytes), cost


def viterbi_decode(soft_bits: List[int]) -> Tuple[bytes, int]:
    """
    Decode unpunctured soft bits using Viterbi algorithm.

    Args:
        soft_bits: List of soft bit values (even length).
            Values: 0 = strong 0, 0xFFFF = strong 1, 0x7FFF = unknown.

    Returns:
        Tuple of (decoded bytes, bit errors corrected).

    Examples:
        >>> # Decode a simple sequence
        >>> soft = [0, 0, 0xFFFF, 0xFFFF] * 4  # Simplified example
        >>> data, cost = viterbi_decode(soft)
    """
    if len(soft_bits) % 2 != 0:
        raise ValueError(f"Soft bits must be even length, got {len(soft_bits)}")

    if len(soft_bits) // 2 > VITERBI_HIST_LEN:
        raise ValueError(f"Input too long: {len(soft_bits) // 2} > {VITERBI_HIST_LEN}")

    decoder = ViterbiDecoder()

    # Decode bit pairs
    for i in range(0, len(soft_bits), 2):
        decoder.decode_bit(soft_bits[i], soft_bits[i + 1])

    # Chainback
    output_bits = len(soft_bits) // 2
    return decoder.chainback(output_bits)


def viterbi_decode_punctured(
    soft_bits: List[int],
    pattern: Tuple[int, ...],
    fill_value: int = 0x7FFF,
) -> Tuple[bytes, int]:
    """
    Decode punctured soft bits using Viterbi algorithm.

    First depunctures (inserts erasures), then decodes.

    Args:
        soft_bits: List of punctured soft bit values.
        pattern: Puncture pattern used.
        fill_value: Value to use for erasure positions (default: 0x7FFF = unknown).

    Returns:
        Tuple of (decoded bytes, adjusted bit errors).

    Examples:
        >>> from m17.codec.puncture import PUNCTURE_P2
        >>> soft = [0, 0xFFFF] * 136  # 272 punctured bits
        >>> data, cost = viterbi_decode_punctured(soft, PUNCTURE_P2)
    """
    # Depuncture
    depunctured = depuncture(soft_bits, pattern, fill_value)

    # Decode
    data, cost = viterbi_decode(depunctured)

    # Adjust cost for inserted erasures
    # Each erasure contributes fill_value to the error metric
    inserted = len(depunctured) - len(soft_bits)
    adjusted_cost = cost - inserted * fill_value

    return data, adjusted_cost


def decode_lsf(soft_bits: List[int]) -> Tuple[bytes, int]:
    """
    Decode a punctured LSF (368 soft bits -> 30 bytes).

    Args:
        soft_bits: 368 punctured soft bits.

    Returns:
        Tuple of (30-byte LSF with CRC, error cost).
    """
    if len(soft_bits) != 368:
        raise ValueError(f"LSF must be 368 soft bits, got {len(soft_bits)}")

    return viterbi_decode_punctured(soft_bits, PUNCTURE_P1)


def decode_stream(soft_bits: List[int]) -> Tuple[bytes, int]:
    """
    Decode a punctured stream frame (272 soft bits -> 18 bytes).

    Args:
        soft_bits: 272 punctured soft bits.

    Returns:
        Tuple of (18-byte frame data, error cost).
    """
    if len(soft_bits) != 272:
        raise ValueError(f"Stream frame must be 272 soft bits, got {len(soft_bits)}")

    return viterbi_decode_punctured(soft_bits, PUNCTURE_P2)


def decode_packet(soft_bits: List[int]) -> Tuple[bytes, int]:
    """
    Decode a punctured packet frame (368 soft bits -> 26 bytes).

    Args:
        soft_bits: 368 punctured soft bits.

    Returns:
        Tuple of (26-byte packet chunk, error cost).
    """
    if len(soft_bits) != 368:
        raise ValueError(f"Packet frame must be 368 soft bits, got {len(soft_bits)}")

    return viterbi_decode_punctured(soft_bits, PUNCTURE_P3)
