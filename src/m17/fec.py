"""Forward error correction: convolutional code, puncturing, Viterbi and Golay.

Soft bits are integers from 0 (certain 0) to 0xFFFF (certain 1), 0x7FFF is an
erasure. Ported from libm17, results are identical to it bit for bit.
"""

# Puncturing patterns: LSF (P1), stream frames and BERT (P2), packet frames (P3)
P1 = (1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1) + (1, 0, 1, 1, 1, 0, 1, 1) * 5 + (1, 0, 1, 1)
P2 = (1,) * 11 + (0,)
P3 = (1,) * 7 + (0,)

ERASURE = 0x7FFF
_HIST_LEN = 244  # trellis steps, enough for the longest frame (LSF)


def bytes_to_bits(data: bytes, nbits: int) -> list[int]:
    """The first ``nbits`` bits of ``data``, most significant bit first."""
    return [(data[i // 8] >> (7 - i % 8)) & 1 for i in range(nbits)]


def conv_encode(data: bytes, nbits: int, puncture: tuple[int, ...], out_len: int) -> list[int]:
    """Encode ``nbits`` bits with the K=5 rate 1/2 code (4 flush bits added) and puncture."""
    out: list[int] = []
    sr = 0  # bit k holds the input bit k+1 steps ago
    p = 0
    for b in bytes_to_bits(data, nbits) + [0, 0, 0, 0]:
        g1 = b ^ (sr >> 2 & 1) ^ (sr >> 3 & 1)  # 1 + D^3 + D^4
        g2 = b ^ (sr & 1) ^ (sr >> 1 & 1) ^ (sr >> 3 & 1)  # 1 + D + D^2 + D^4
        sr = ((sr << 1) | b) & 0xF
        for g in (g1, g2):
            if puncture[p] and len(out) < out_len:
                out.append(g)
            p = (p + 1) % len(puncture)
    return out


# ---- Viterbi decoder

_BM_IDX = (0, 1, 1, 0, 2, 3, 3, 2)  # expected (G1, G2) per butterfly


def viterbi_decode(soft: list[int], puncture: tuple[int, ...]) -> tuple[bytes, int]:
    """Depuncture and decode soft bits.

    Returns the decoded bytes and the path metric (about 0xFFFF per corrected
    hard bit error). As in libm17, the output starts with 4 zero bits and ends
    with the 4 flush bits: the data begins at bit 8 of the first full byte the
    caller expects, see :mod:`m17.frames`.
    """
    metrics = [0] + [0x3FFFFFFF] * 15
    history: list[int] = []
    p = 0
    i = 0
    u = 0  # depunctured bit count
    while i < len(soft):
        pair = []
        for _ in range(2):
            if u >= 2 * _HIST_LEN:
                raise ValueError("input too long")
            if i >= len(soft):
                pair.append(ERASURE)  # odd depunctured length: pad with an erasure
            else:
                pair.append(soft[i] if puncture[p] else ERASURE)
                if puncture[p]:
                    i += 1
                p = (p + 1) % len(puncture)
            u += 1
        s0, s1 = pair
        n0, n1 = 0xFFFF - s0, 0xFFFF - s1
        bm = (s0 + s1, s0 + n1, n0 + s1, n0 + n1)
        new = [0] * 16
        hist = 0
        for j in range(8):
            bm0 = bm[_BM_IDX[j]]
            bm1 = 0x1FFFE - bm0
            a, b = metrics[j], metrics[j + 8]
            m0, m1, m2, m3 = a + bm0, b + bm1, a + bm1, b + bm0
            d0, d1 = m0 >= m1, m2 >= m3
            new[2 * j] = m1 if d0 else m0
            new[2 * j + 1] = m3 if d1 else m2
            hist |= (d0 << (2 * j)) | (d1 << (2 * j + 1))
        metrics = new
        history.append(hist)

    # chainback
    pos = len(history)
    bit_pos = u // 2 + 4
    out = bytearray((bit_pos + 7) // 8)
    state = 0
    while pos:
        bit_pos -= 1
        pos -= 1
        bit = history[pos] & (1 << (state >> 4))
        state >>= 1
        if bit:
            state |= 0x80
            out[bit_pos // 8] |= 1 << (7 - bit_pos % 8)
    erasures = u - len(soft)
    return bytes(out), min(metrics) - erasures * ERASURE


# ---- Golay(24, 12)

ENCODE_MATRIX = (0x8EB, 0x93E, 0xA97, 0xDC6, 0x367, 0x6CD, 0xD99, 0x3DA, 0x7B4, 0xF68, 0x63B, 0xC75)
DECODE_MATRIX = (0xC75, 0x49F, 0x93E, 0x6E3, 0xDC6, 0xF13, 0xAB9, 0x1ED, 0x3DA, 0x7B4, 0xF68, 0xA4F)


def golay24_encode(data: int) -> int:
    """24-bit codeword for 12 data bits (data in the upper half)."""
    checksum = 0
    for i in range(12):
        if data >> i & 1:
            checksum ^= ENCODE_MATRIX[i]
    return (data << 12) | checksum


def _hard_errors(syndrome: int) -> int | None:
    """Error pattern of weight 3 or less for a syndrome, None if there is none."""
    if syndrome.bit_count() <= 3:
        return syndrome
    for i in range(12):
        if (syndrome ^ ENCODE_MATRIX[i]).bit_count() <= 2:
            return (1 << (12 + i)) | (syndrome ^ ENCODE_MATRIX[i])
    inv = 0
    for i in range(12):
        if syndrome >> i & 1:
            inv ^= DECODE_MATRIX[i]
    if inv.bit_count() <= 3:
        return inv << 12
    for i in range(12):
        if (inv ^ DECODE_MATRIX[i]).bit_count() <= 2:
            return ((inv ^ DECODE_MATRIX[i]) << 12) | (1 << i)
    return None


def _bit_syndrome(bit: int) -> int:
    return ENCODE_MATRIX[bit - 12] if bit >= 12 else 1 << bit


_CHASE_BITS = 4
_MIN_MARGIN = 32767  # half a bit error: closer runner-up candidates are ambiguous


def golay24_soft_decode(codeword: list[int]) -> int | None:
    """Chase-II soft decoder. Returns the 12 data bits, None if uncorrectable or ambiguous."""
    r = 0
    rel = [0] * 24  # reliability |2v - 0xFFFF| per bit number
    for i in range(24):
        v = codeword[23 - i]
        r |= (v > 0x7FFF) << i
        rel[i] = 2 * (v - 0x7FFF) - 1 if v > 0x7FFF else 0xFFFF - 2 * v

    # least reliable positions, ties go to the more significant bit
    positions: list[int] = []
    for _ in range(_CHASE_BITS):
        best, best_dist = -1, 0
        for i in range(23, -1, -1):
            v = codeword[23 - i]
            dist = v - 0x7FFF if v > 0x7FFF else 0x7FFF - v
            if i not in positions and (best < 0 or dist < best_dist):
                best, best_dist = i, dist
        positions.append(best)

    syndrome = (r ^ golay24_encode(r >> 12)) & 0xFFF
    best_d = second_d = None
    best_c = 0
    for t in range(1 << _CHASE_BITS):
        flip, syn = 0, syndrome
        for k, pos in enumerate(positions):
            if t >> k & 1:
                flip |= 1 << pos
                syn ^= _bit_syndrome(pos)
        e = _hard_errors(syn)
        if e is None:
            continue
        diff = flip ^ e
        c = r ^ diff
        if best_d is not None and c == best_c:
            continue
        d = sum(rel[b] for b in range(24) if diff >> b & 1)
        if best_d is None or d < best_d:
            second_d, best_d, best_c = best_d, d, c
        elif second_d is None or d < second_d:
            second_d = d
    if best_d is None:
        return None
    if second_d is not None and second_d - best_d <= _MIN_MARGIN:
        return None
    return best_c >> 12


def encode_lich(chunk: bytes) -> list[int]:
    """Encode a 6-byte LICH chunk to 96 bits (four Golay codewords)."""
    words = (
        (chunk[0] << 4) | (chunk[1] >> 4),
        ((chunk[1] & 0xF) << 8) | chunk[2],
        (chunk[3] << 4) | (chunk[4] >> 4),
        ((chunk[4] & 0xF) << 8) | chunk[5],
    )
    return [golay24_encode(w) >> (23 - k) & 1 for w in words for k in range(24)]


def decode_lich(soft: list[int]) -> bytes | None:
    """Decode 96 soft bits to the 6-byte LICH chunk, None if a codeword failed."""
    w = []
    for i in range(4):
        d = golay24_soft_decode(soft[24 * i : 24 * i + 24])
        if d is None:
            return None
        w.append(d)
    return bytes(
        [w[0] >> 4, ((w[0] & 0xF) << 4) | (w[1] >> 8), w[1] & 0xFF,
         w[2] >> 4, ((w[2] & 0xF) << 4) | (w[3] >> 8), w[3] & 0xFF]
    )
