"""M17 AES Encryption

Implements AES encryption for M17 frames using CTR mode.

M17 supports three AES key sizes:
- AES-128: 16-byte key
- AES-192: 24-byte key
- AES-256: 32-byte key

The 16-byte IV (Initialization Vector) is composed of:
- 14 bytes from the META field (MetaAesIV)
- 2 bytes from the frame number (in stream mode)

For packet mode, the full 16-byte IV comes from the META field.

Requires the `cryptography` library:
    pip install cryptography
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Union

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

__all__ = [
    "AESEncryptor",
    "AESMode",
    "aes_encrypt",
    "aes_decrypt",
    "HAS_CRYPTOGRAPHY",
]


class AESMode(IntEnum):
    """AES key size modes."""

    AES_128 = 128
    AES_192 = 192
    AES_256 = 256


# Key sizes in bytes for each mode
KEY_SIZES = {
    AESMode.AES_128: 16,
    AESMode.AES_192: 24,
    AESMode.AES_256: 32,
}


def _check_cryptography() -> None:
    """Raise ImportError if cryptography is not available."""
    if not HAS_CRYPTOGRAPHY:
        raise ImportError(
            "cryptography library not installed. " "Install with: pip install cryptography"
        )


@dataclass
class AESEncryptor:
    """M17 AES encryptor.

    Uses AES in CTR (Counter) mode for stream encryption.

    Example:
    -------
        encryptor = AESEncryptor(mode=AESMode.AES_256)

        # For stream mode: 14-byte IV from META + 2-byte frame number
        meta_iv = bytes(14)  # From MetaAesIV
        frame_number = 0x0000

        ciphertext = encryptor.encrypt(plaintext, key, meta_iv, frame_number)
        plaintext = encryptor.decrypt(ciphertext, key, meta_iv, frame_number)

        # For packet mode: full 16-byte IV
        full_iv = bytes(16)
        ciphertext = encryptor.encrypt_packet(plaintext, key, full_iv)
    """

    mode: AESMode = AESMode.AES_256

    def __post_init__(self) -> None:
        """Validate cryptography availability."""
        _check_cryptography()

    @property
    def key_bytes(self) -> int:
        """Number of bytes required for the key."""
        return KEY_SIZES[self.mode]

    def _validate_key(self, key: bytes) -> bytes:
        """Validate and normalize key length.

        Args:
        ----
            key: AES key.

        Returns:
        -------
            Key padded or truncated to correct length.

        Raises:
        ------
            ValueError: If key is too short.
        """
        expected = self.key_bytes
        if len(key) < expected:
            raise ValueError(f"Key too short: {len(key)} bytes, need {expected}")
        return key[:expected]

    def _build_iv(self, meta_iv: bytes, frame_number: int) -> bytes:
        """Build full 16-byte IV from META IV and frame number.

        Args:
        ----
            meta_iv: 14-byte IV from META field.
            frame_number: 16-bit frame number.

        Returns:
        -------
            16-byte IV for AES-CTR.
        """
        if len(meta_iv) < 14:
            meta_iv = meta_iv + bytes(14 - len(meta_iv))
        elif len(meta_iv) > 14:
            meta_iv = meta_iv[:14]

        # Frame number as big-endian 2 bytes
        frame_bytes = (frame_number & 0xFFFF).to_bytes(2, "big")

        return meta_iv + frame_bytes

    def encrypt(
        self,
        data: bytes,
        key: bytes,
        meta_iv: bytes,
        frame_number: int = 0,
    ) -> bytes:
        """Encrypt data for stream mode.

        Args:
        ----
            data: Plaintext data to encrypt.
            key: AES key (16/24/32 bytes).
            meta_iv: 14-byte IV from META field.
            frame_number: 16-bit frame number (0-65535).

        Returns:
        -------
            Encrypted data.
        """
        key = self._validate_key(key)
        iv = self._build_iv(meta_iv, frame_number)

        cipher = Cipher(algorithms.AES(key), modes.CTR(iv))
        encryptor = cipher.encryptor()
        result: bytes = encryptor.update(data) + encryptor.finalize()
        return result

    def decrypt(
        self,
        data: bytes,
        key: bytes,
        meta_iv: bytes,
        frame_number: int = 0,
    ) -> bytes:
        """Decrypt data for stream mode.

        Args:
        ----
            data: Ciphertext data.
            key: AES key (same as used for encryption).
            meta_iv: 14-byte IV from META field.
            frame_number: 16-bit frame number.

        Returns:
        -------
            Decrypted data.
        """
        key = self._validate_key(key)
        iv = self._build_iv(meta_iv, frame_number)

        cipher = Cipher(algorithms.AES(key), modes.CTR(iv))
        decryptor = cipher.decryptor()
        result: bytes = decryptor.update(data) + decryptor.finalize()
        return result

    def encrypt_packet(self, data: bytes, key: bytes, iv: bytes) -> bytes:
        """Encrypt data for packet mode.

        In packet mode, the full 16-byte IV is provided directly.

        Args:
        ----
            data: Plaintext data.
            key: AES key.
            iv: Full 16-byte IV.

        Returns:
        -------
            Encrypted data.
        """
        key = self._validate_key(key)

        if len(iv) < 16:
            iv = iv + bytes(16 - len(iv))
        elif len(iv) > 16:
            iv = iv[:16]

        cipher = Cipher(algorithms.AES(key), modes.CTR(iv))
        encryptor = cipher.encryptor()
        result: bytes = encryptor.update(data) + encryptor.finalize()
        return result

    def decrypt_packet(self, data: bytes, key: bytes, iv: bytes) -> bytes:
        """Decrypt data for packet mode.

        Args:
        ----
            data: Ciphertext data.
            key: AES key.
            iv: Full 16-byte IV.

        Returns:
        -------
            Decrypted data.
        """
        return self.encrypt_packet(data, key, iv)  # CTR is symmetric


def aes_encrypt(
    data: bytes,
    key: bytes,
    meta_iv: bytes,
    frame_number: int = 0,
    mode: Union[AESMode, int] = AESMode.AES_256,
) -> bytes:
    """Encrypt data using M17 AES.

    Convenience function for one-shot encryption.

    Args:
    ----
        data: Plaintext data.
        key: AES key.
        meta_iv: 14-byte IV from META field.
        frame_number: Frame number for stream mode.
        mode: AES mode (128, 192, or 256 bits).

    Returns:
    -------
        Encrypted data.

    Example:
    -------
        key = bytes(32)  # 256-bit key
        iv = bytes(14)   # From MetaAesIV
        ciphertext = aes_encrypt(b"Hello M17!", key, iv, frame_number=0)
    """
    _check_cryptography()
    if isinstance(mode, int):
        mode = AESMode(mode)
    encryptor = AESEncryptor(mode=mode)
    return encryptor.encrypt(data, key, meta_iv, frame_number)


def aes_decrypt(
    data: bytes,
    key: bytes,
    meta_iv: bytes,
    frame_number: int = 0,
    mode: Union[AESMode, int] = AESMode.AES_256,
) -> bytes:
    """Decrypt data using M17 AES.

    Convenience function for one-shot decryption.

    Args:
    ----
        data: Ciphertext data.
        key: AES key.
        meta_iv: 14-byte IV from META field.
        frame_number: Frame number for stream mode.
        mode: AES mode (128, 192, or 256 bits).

    Returns:
    -------
        Decrypted data.

    Example:
    -------
        plaintext = aes_decrypt(ciphertext, key, iv, frame_number=0)
    """
    _check_cryptography()
    if isinstance(mode, int):
        mode = AESMode(mode)
    encryptor = AESEncryptor(mode=mode)
    return encryptor.decrypt(data, key, meta_iv, frame_number)
