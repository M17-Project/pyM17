"""M17 Scrambler Encryption

Implements the M17 scrambler cipher using Linear Feedback Shift Registers (LFSR).

The scrambler provides basic encryption by XORing the payload with a
pseudo-random sequence generated from a seed (provided in the META/nonce field).

Supported modes:
- 8-bit scrambler: Uses 1-byte seed
- 16-bit scrambler: Uses 2-byte seed
- 24-bit scrambler: Uses 3-byte seed

LFSR Polynomials (Fibonacci form):
- 8-bit:  x^8 + x^6 + x^5 + x^4 + 1 (taps at bits 8, 6, 5, 4)
- 16-bit: x^16 + x^14 + x^13 + x^11 + 1 (taps at bits 16, 14, 13, 11)
- 24-bit: x^24 + x^23 + x^22 + x^17 + 1 (taps at bits 24, 23, 22, 17)

Note: The scrambler is symmetric - encryption and decryption use the same operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Union

__all__ = [
    "Scrambler",
    "ScramblerMode",
    "scrambler_encrypt",
    "scrambler_decrypt",
]


class ScramblerMode(IntEnum):
    """Scrambler key size modes."""

    BIT_8 = 8
    BIT_16 = 16
    BIT_24 = 24


# LFSR tap positions for each mode (1-indexed from MSB)
# These create maximal-length sequences
LFSR_TAPS = {
    ScramblerMode.BIT_8: (8, 6, 5, 4),  # x^8 + x^6 + x^5 + x^4 + 1
    ScramblerMode.BIT_16: (16, 14, 13, 11),  # x^16 + x^14 + x^13 + x^11 + 1
    ScramblerMode.BIT_24: (24, 23, 22, 17),  # x^24 + x^23 + x^22 + x^17 + 1
}


@dataclass
class Scrambler:
    """M17 Scrambler cipher.

    Generates a pseudo-random byte stream from a seed using an LFSR,
    then XORs it with the payload.

    Example:
    -------
        # 24-bit scrambler with 3-byte seed
        scrambler = Scrambler(mode=ScramblerMode.BIT_24)
        seed = bytes([0x12, 0x34, 0x56])

        # Encrypt
        ciphertext = scrambler.encrypt(plaintext, seed)

        # Decrypt (same operation)
        plaintext = scrambler.decrypt(ciphertext, seed)
    """

    mode: ScramblerMode = ScramblerMode.BIT_24

    @property
    def seed_bytes(self) -> int:
        """Number of bytes required for the seed."""
        return self.mode // 8

    def _get_taps_mask(self) -> int:
        """Get the tap mask for the LFSR."""
        taps = LFSR_TAPS[self.mode]
        mask = 0
        for tap in taps:
            mask |= 1 << (tap - 1)
        return mask

    def _lfsr_step(self, state: int) -> tuple[int, int]:
        """Perform one LFSR step.

        Args:
        ----
            state: Current LFSR state.

        Returns:
        -------
            Tuple of (new_state, output_bit).
        """
        taps = LFSR_TAPS[self.mode]
        bits = self.mode

        # XOR all tap positions
        feedback = 0
        for tap in taps:
            feedback ^= (state >> (tap - 1)) & 1

        # Output is LSB
        output = state & 1

        # Shift right and insert feedback at MSB
        new_state = (state >> 1) | (feedback << (bits - 1))

        return new_state, output

    def _generate_byte(self, state: int) -> tuple[int, int]:
        """Generate one byte of keystream.

        Args:
        ----
            state: Current LFSR state.

        Returns:
        -------
            Tuple of (new_state, keystream_byte).
        """
        byte_val = 0
        for i in range(8):
            state, bit = self._lfsr_step(state)
            byte_val |= bit << i

        return state, byte_val

    def _seed_to_state(self, seed: bytes) -> int:
        """Convert seed bytes to LFSR initial state.

        Args:
        ----
            seed: Seed bytes (1, 2, or 3 bytes depending on mode).

        Returns:
        -------
            Initial LFSR state as integer.

        Raises:
        ------
            ValueError: If seed length doesn't match mode.
        """
        expected = self.seed_bytes
        if len(seed) < expected:
            # Pad with zeros
            seed = seed + bytes(expected - len(seed))
        elif len(seed) > expected:
            # Truncate
            seed = seed[:expected]

        # Convert to integer (big-endian)
        state = int.from_bytes(seed, "big")

        # Ensure non-zero state (LFSR locks up at 0)
        if state == 0:
            state = 1

        return state

    def encrypt(self, data: bytes, seed: bytes) -> bytes:
        """Encrypt data using the scrambler.

        Args:
        ----
            data: Plaintext data to encrypt.
            seed: Scrambler seed (1/2/3 bytes for 8/16/24-bit mode).

        Returns:
        -------
            Encrypted data (same length as input).
        """
        state = self._seed_to_state(seed)
        result = bytearray(len(data))

        for i, byte in enumerate(data):
            state, keystream_byte = self._generate_byte(state)
            result[i] = byte ^ keystream_byte

        return bytes(result)

    def decrypt(self, data: bytes, seed: bytes) -> bytes:
        """Decrypt data using the scrambler.

        This is the same operation as encrypt (XOR is symmetric).

        Args:
        ----
            data: Ciphertext data to decrypt.
            seed: Scrambler seed (same as used for encryption).

        Returns:
        -------
            Decrypted data.
        """
        return self.encrypt(data, seed)

    def generate_keystream(self, length: int, seed: bytes) -> bytes:
        """Generate raw keystream bytes.

        Useful for debugging or manual XOR operations.

        Args:
        ----
            length: Number of keystream bytes to generate.
            seed: Scrambler seed.

        Returns:
        -------
            Keystream bytes.
        """
        state = self._seed_to_state(seed)
        keystream = bytearray(length)

        for i in range(length):
            state, byte_val = self._generate_byte(state)
            keystream[i] = byte_val

        return bytes(keystream)


def scrambler_encrypt(
    data: bytes,
    seed: bytes,
    mode: Union[ScramblerMode, int] = ScramblerMode.BIT_24,
) -> bytes:
    r"""Encrypt data using M17 scrambler.

    Convenience function for one-shot encryption.

    Args:
    ----
        data: Plaintext data.
        seed: Scrambler seed.
        mode: Scrambler mode (8, 16, or 24 bits).

    Returns:
    -------
        Encrypted data.

    Example:
    -------
        ciphertext = scrambler_encrypt(b"Hello M17!", b"\x12\x34\x56")
    """
    if isinstance(mode, int):
        mode = ScramblerMode(mode)
    scrambler = Scrambler(mode=mode)
    return scrambler.encrypt(data, seed)


def scrambler_decrypt(
    data: bytes,
    seed: bytes,
    mode: Union[ScramblerMode, int] = ScramblerMode.BIT_24,
) -> bytes:
    r"""Decrypt data using M17 scrambler.

    Convenience function for one-shot decryption.

    Args:
    ----
        data: Ciphertext data.
        seed: Scrambler seed (same as used for encryption).
        mode: Scrambler mode (8, 16, or 24 bits).

    Returns:
    -------
        Decrypted data.

    Example:
    -------
        plaintext = scrambler_decrypt(ciphertext, b"\x12\x34\x56")
    """
    if isinstance(mode, int):
        mode = ScramblerMode(mode)
    scrambler = Scrambler(mode=mode)
    return scrambler.decrypt(data, seed)
