"""M17 Cryptographic Support

This module provides encryption and decryption for M17 frames:
- Scrambler encryption (8/16/24-bit LFSR)
- AES encryption (128/192/256-bit)
- Digital signatures (ECDSA P-256, v3.0.0)
"""

from m17.crypto.scrambler import (
    Scrambler,
    scrambler_decrypt,
    scrambler_encrypt,
)

__all__ = [
    "Scrambler",
    "scrambler_encrypt",
    "scrambler_decrypt",
]

# Conditionally export AES and signatures if cryptography is available
try:
    from m17.crypto.aes import (
        AESEncryptor,
        aes_decrypt,
        aes_encrypt,
    )
    from m17.crypto.signature import (
        SigningKey,
        VerifyingKey,
        generate_keypair,
        sign_message,
        verify_signature,
    )

    __all__.extend(
        [
            "AESEncryptor",
            "aes_encrypt",
            "aes_decrypt",
            "SigningKey",
            "VerifyingKey",
            "generate_keypair",
            "sign_message",
            "verify_signature",
        ]
    )
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False
