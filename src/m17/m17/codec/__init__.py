"""
M17 FEC Codec Layer

This module provides Forward Error Correction (FEC) components for M17:
- Golay(24,12) encoder/decoder
- Convolutional encoder (K=5, rate 1/2)
- Viterbi soft-decision decoder
- Puncture patterns (P1, P2, P3)
- Interleaver (368-bit QPP)
- Randomizer (46-byte sequence)

These are optional components primarily used for RF gateway support.
IP networking typically doesn't require FEC as the transport layer
provides reliability.
"""

from m17.codec.golay import (
    golay24_encode,
    golay24_decode,
    golay24_sdecode,
    encode_lich,
    decode_lich,
    ENCODE_MATRIX,
    DECODE_MATRIX,
)
from m17.codec.convolutional import (
    conv_encode,
    conv_encode_lsf,
    conv_encode_stream,
    conv_encode_packet,
    conv_encode_bert,
    POLY_G1,
    POLY_G2,
)
from m17.codec.puncture import (
    puncture,
    depuncture,
    PUNCTURE_P1,
    PUNCTURE_P2,
    PUNCTURE_P3,
)
from m17.codec.viterbi import (
    viterbi_decode,
    viterbi_decode_punctured,
    ViterbiDecoder,
)
from m17.codec.interleave import (
    interleave,
    deinterleave,
    INTERLEAVE_SEQ,
)
from m17.codec.randomize import (
    randomize,
    derandomize,
    RAND_SEQ,
)

__all__ = [
    # Golay
    "golay24_encode",
    "golay24_decode",
    "golay24_sdecode",
    "encode_lich",
    "decode_lich",
    "ENCODE_MATRIX",
    "DECODE_MATRIX",
    # Convolutional
    "conv_encode",
    "conv_encode_lsf",
    "conv_encode_stream",
    "conv_encode_packet",
    "conv_encode_bert",
    "POLY_G1",
    "POLY_G2",
    # Puncture
    "puncture",
    "depuncture",
    "PUNCTURE_P1",
    "PUNCTURE_P2",
    "PUNCTURE_P3",
    # Viterbi
    "viterbi_decode",
    "viterbi_decode_punctured",
    "ViterbiDecoder",
    # Interleave
    "interleave",
    "deinterleave",
    "INTERLEAVE_SEQ",
    # Randomize
    "randomize",
    "derandomize",
    "RAND_SEQ",
]
