"""M17 Digital Signatures

Implements ECDSA digital signatures for M17 v3.0.0 frame authentication.

M17 uses ECDSA with the secp256r1 (P-256/prime256v1) curve for:
- Authenticating transmissions (proving callsign ownership)
- Verifying message integrity

Signature Format:
- 64 bytes total: r (32 bytes) || s (32 bytes)
- Signatures are transmitted in the META field or as packet payload

Key Format:
- Private key: 32 bytes (256 bits)
- Public key: 64 bytes uncompressed (x, y each 32 bytes)
- Compressed public key: 33 bytes (prefix + x coordinate)

Requires the `cryptography` library:
    pip install cryptography

Example:
-------
    from m17.crypto.signature import SigningKey, VerifyingKey

    # Generate new keypair
    sk = SigningKey.generate()
    vk = sk.verifying_key

    # Sign message
    signature = sk.sign(b"Hello M17!")

    # Verify signature
    is_valid = vk.verify(b"Hello M17!", signature)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import (
        decode_dss_signature,
        encode_dss_signature,
    )

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

__all__ = [
    "SigningKey",
    "VerifyingKey",
    "sign_message",
    "verify_signature",
    "HAS_CRYPTOGRAPHY",
]

# Signature size: r (32 bytes) + s (32 bytes)
SIGNATURE_SIZE = 64

# Key sizes
PRIVATE_KEY_SIZE = 32
PUBLIC_KEY_SIZE = 64  # Uncompressed (x, y)
COMPRESSED_PUBLIC_KEY_SIZE = 33  # Prefix + x


def _check_cryptography() -> None:
    """Raise ImportError if cryptography is not available."""
    if not HAS_CRYPTOGRAPHY:
        raise ImportError(
            "cryptography library not installed. " "Install with: pip install cryptography"
        )


@dataclass
class VerifyingKey:
    """ECDSA public key for signature verification.

    Wraps a secp256r1 public key for M17 signature verification.

    Example:
    -------
        # From raw bytes (64 bytes uncompressed)
        vk = VerifyingKey.from_bytes(public_key_bytes)

        # Verify a signature
        if vk.verify(message, signature):
            print("Signature valid!")
    """

    _key: Any  # ec.EllipticCurvePublicKey when cryptography available

    @classmethod
    def from_bytes(cls, data: bytes) -> VerifyingKey:
        """Create verifying key from raw bytes.

        Args:
        ----
            data: Public key bytes (64 bytes uncompressed or 33 compressed).

        Returns:
        -------
            VerifyingKey instance.

        Raises:
        ------
            ValueError: If key format is invalid.
        """
        _check_cryptography()

        if len(data) == PUBLIC_KEY_SIZE:
            # Uncompressed format (64 bytes) - add 0x04 prefix
            key_bytes = b"\x04" + data
        elif len(data) == COMPRESSED_PUBLIC_KEY_SIZE:
            # Already compressed format (33 bytes)
            key_bytes = data
        elif len(data) == PUBLIC_KEY_SIZE + 1 and data[0] == 0x04:
            # Full uncompressed with prefix
            key_bytes = data
        else:
            raise ValueError(
                f"Invalid public key length: {len(data)} bytes. "
                f"Expected {PUBLIC_KEY_SIZE} (uncompressed) or "
                f"{COMPRESSED_PUBLIC_KEY_SIZE} (compressed)"
            )

        try:
            key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), key_bytes)
            return cls(_key=key)
        except Exception as e:
            raise ValueError(f"Invalid public key: {e}") from e

    def to_bytes(self, compressed: bool = False) -> bytes:
        """Export public key as raw bytes.

        Args:
        ----
            compressed: If True, return 33-byte compressed format.

        Returns:
        -------
            Public key bytes.
        """
        _check_cryptography()

        if compressed:
            data: bytes = self._key.public_bytes(
                encoding=serialization.Encoding.X962,
                format=serialization.PublicFormat.CompressedPoint,
            )
            return data
        else:
            data = self._key.public_bytes(
                encoding=serialization.Encoding.X962,
                format=serialization.PublicFormat.UncompressedPoint,
            )
            # Remove 0x04 prefix for raw format
            return data[1:]

    def verify(self, message: bytes, signature: bytes) -> bool:
        """Verify a signature.

        Args:
        ----
            message: Original message that was signed.
            signature: 64-byte signature (r || s).

        Returns:
        -------
            True if signature is valid, False otherwise.
        """
        _check_cryptography()

        if len(signature) != SIGNATURE_SIZE:
            return False

        try:
            # Extract r and s from signature
            r = int.from_bytes(signature[:32], "big")
            s = int.from_bytes(signature[32:], "big")

            # Convert to DER format for cryptography library
            der_sig = encode_dss_signature(r, s)

            # Verify
            self._key.verify(der_sig, message, ec.ECDSA(hashes.SHA256()))
            return True
        except Exception:
            return False

    def __eq__(self, other: object) -> bool:
        """Compare public keys."""
        if isinstance(other, VerifyingKey):
            return self.to_bytes() == other.to_bytes()
        return NotImplemented


@dataclass
class SigningKey:
    """ECDSA private key for signing messages.

    Wraps a secp256r1 private key for M17 signature generation.

    Example:
    -------
        # Generate new keypair
        sk = SigningKey.generate()

        # Sign a message
        signature = sk.sign(b"Hello M17!")

        # Get public key for verification
        vk = sk.verifying_key
    """

    _key: Any  # ec.EllipticCurvePrivateKey when cryptography available

    @classmethod
    def generate(cls) -> SigningKey:
        """Generate a new random signing key.

        Returns
        -------
            New SigningKey instance.
        """
        _check_cryptography()

        key = ec.generate_private_key(ec.SECP256R1())
        return cls(_key=key)

    @classmethod
    def from_bytes(cls, data: bytes) -> SigningKey:
        """Create signing key from raw bytes.

        Args:
        ----
            data: 32-byte private key scalar.

        Returns:
        -------
            SigningKey instance.

        Raises:
        ------
            ValueError: If key is invalid.
        """
        _check_cryptography()

        if len(data) != PRIVATE_KEY_SIZE:
            raise ValueError(
                f"Invalid private key length: {len(data)} bytes, expected {PRIVATE_KEY_SIZE}"
            )

        try:
            # Convert raw scalar to private key
            private_value = int.from_bytes(data, "big")
            key = ec.derive_private_key(private_value, ec.SECP256R1())
            return cls(_key=key)
        except Exception as e:
            raise ValueError(f"Invalid private key: {e}") from e

    def to_bytes(self) -> bytes:
        """Export private key as raw bytes.

        Returns
        -------
            32-byte private key scalar.
        """
        _check_cryptography()

        # Get raw private value
        private_numbers = self._key.private_numbers()
        result: bytes = private_numbers.private_value.to_bytes(PRIVATE_KEY_SIZE, "big")
        return result

    @property
    def verifying_key(self) -> VerifyingKey:
        """Get the corresponding public key.

        Returns
        -------
            VerifyingKey for this signing key.
        """
        _check_cryptography()
        return VerifyingKey(_key=self._key.public_key())

    def sign(self, message: bytes) -> bytes:
        """Sign a message.

        Args:
        ----
            message: Message to sign.

        Returns:
        -------
            64-byte signature (r || s, each 32 bytes big-endian).
        """
        _check_cryptography()

        # Sign with SHA-256
        der_sig = self._key.sign(message, ec.ECDSA(hashes.SHA256()))

        # Extract r and s from DER format
        r, s = decode_dss_signature(der_sig)

        # Convert to fixed-size format (32 bytes each)
        r_bytes: bytes = r.to_bytes(32, "big")
        s_bytes: bytes = s.to_bytes(32, "big")

        return r_bytes + s_bytes

    def __eq__(self, other: object) -> bool:
        """Compare private keys."""
        if isinstance(other, SigningKey):
            return self.to_bytes() == other.to_bytes()
        return NotImplemented


def sign_message(message: bytes, private_key: bytes) -> bytes:
    """Sign a message with a private key.

    Convenience function for one-shot signing.

    Args:
    ----
        message: Message to sign.
        private_key: 32-byte private key.

    Returns:
    -------
        64-byte signature.

    Example:
    -------
        signature = sign_message(b"Hello M17!", private_key_bytes)
    """
    sk = SigningKey.from_bytes(private_key)
    return sk.sign(message)


def verify_signature(message: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify a signature with a public key.

    Convenience function for one-shot verification.

    Args:
    ----
        message: Original message.
        signature: 64-byte signature.
        public_key: 64-byte public key (or 33-byte compressed).

    Returns:
    -------
        True if signature is valid, False otherwise.

    Example:
    -------
        is_valid = verify_signature(message, signature, public_key_bytes)
    """
    try:
        vk = VerifyingKey.from_bytes(public_key)
        return vk.verify(message, signature)
    except ValueError:
        return False


def generate_keypair() -> tuple[bytes, bytes]:
    """Generate a new ECDSA keypair.

    Returns:
    -------
        Tuple of (private_key, public_key) as raw bytes.
        Private key is 32 bytes, public key is 64 bytes.

    Example:
    -------
        private_key, public_key = generate_keypair()
    """
    sk = SigningKey.generate()
    return sk.to_bytes(), sk.verifying_key.to_bytes()
