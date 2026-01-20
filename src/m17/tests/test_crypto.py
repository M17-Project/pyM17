"""Tests for M17 cryptographic modules.

Tests scrambler and AES encryption/decryption.
"""

import pytest

from m17.crypto.scrambler import (
    Scrambler,
    ScramblerMode,
    scrambler_decrypt,
    scrambler_encrypt,
)


class TestScramblerMode:
    """Tests for ScramblerMode enum."""

    def test_modes_exist(self):
        """Test all scrambler modes exist."""
        assert ScramblerMode.BIT_8 == 8
        assert ScramblerMode.BIT_16 == 16
        assert ScramblerMode.BIT_24 == 24


class TestScrambler:
    """Tests for Scrambler class."""

    def test_seed_bytes(self):
        """Test seed_bytes property."""
        assert Scrambler(mode=ScramblerMode.BIT_8).seed_bytes == 1
        assert Scrambler(mode=ScramblerMode.BIT_16).seed_bytes == 2
        assert Scrambler(mode=ScramblerMode.BIT_24).seed_bytes == 3

    def test_encrypt_decrypt_roundtrip_8bit(self):
        """Test 8-bit scrambler encrypt/decrypt roundtrip."""
        scrambler = Scrambler(mode=ScramblerMode.BIT_8)
        plaintext = b"Hello M17!"
        seed = bytes([0x42])

        ciphertext = scrambler.encrypt(plaintext, seed)
        assert ciphertext != plaintext  # Should be different

        decrypted = scrambler.decrypt(ciphertext, seed)
        assert decrypted == plaintext

    def test_encrypt_decrypt_roundtrip_16bit(self):
        """Test 16-bit scrambler encrypt/decrypt roundtrip."""
        scrambler = Scrambler(mode=ScramblerMode.BIT_16)
        plaintext = b"Hello M17!"
        seed = bytes([0x12, 0x34])

        ciphertext = scrambler.encrypt(plaintext, seed)
        assert ciphertext != plaintext

        decrypted = scrambler.decrypt(ciphertext, seed)
        assert decrypted == plaintext

    def test_encrypt_decrypt_roundtrip_24bit(self):
        """Test 24-bit scrambler encrypt/decrypt roundtrip."""
        scrambler = Scrambler(mode=ScramblerMode.BIT_24)
        plaintext = b"Hello M17!"
        seed = bytes([0x12, 0x34, 0x56])

        ciphertext = scrambler.encrypt(plaintext, seed)
        assert ciphertext != plaintext

        decrypted = scrambler.decrypt(ciphertext, seed)
        assert decrypted == plaintext

    def test_different_seeds_different_output(self):
        """Test that different seeds produce different ciphertext."""
        scrambler = Scrambler(mode=ScramblerMode.BIT_24)
        plaintext = b"Test data"

        cipher1 = scrambler.encrypt(plaintext, b"\x01\x02\x03")
        cipher2 = scrambler.encrypt(plaintext, b"\x04\x05\x06")

        assert cipher1 != cipher2

    def test_same_seed_same_output(self):
        """Test that same seed produces same ciphertext."""
        scrambler = Scrambler(mode=ScramblerMode.BIT_24)
        plaintext = b"Test data"
        seed = b"\x12\x34\x56"

        cipher1 = scrambler.encrypt(plaintext, seed)
        cipher2 = scrambler.encrypt(plaintext, seed)

        assert cipher1 == cipher2

    def test_empty_data(self):
        """Test encryption of empty data."""
        scrambler = Scrambler(mode=ScramblerMode.BIT_24)
        ciphertext = scrambler.encrypt(b"", b"\x12\x34\x56")
        assert ciphertext == b""

    def test_seed_padding(self):
        """Test that short seeds are padded."""
        scrambler = Scrambler(mode=ScramblerMode.BIT_24)
        plaintext = b"Test"

        # Short seed should be padded with zeros
        cipher1 = scrambler.encrypt(plaintext, b"\x12")
        cipher2 = scrambler.encrypt(plaintext, b"\x12\x00\x00")

        assert cipher1 == cipher2

    def test_seed_truncation(self):
        """Test that long seeds are truncated."""
        scrambler = Scrambler(mode=ScramblerMode.BIT_8)
        plaintext = b"Test"

        # Long seed should be truncated
        cipher1 = scrambler.encrypt(plaintext, b"\x42")
        cipher2 = scrambler.encrypt(plaintext, b"\x42\xFF\xFF\xFF")

        assert cipher1 == cipher2

    def test_zero_seed_handled(self):
        """Test that zero seed is converted to non-zero."""
        scrambler = Scrambler(mode=ScramblerMode.BIT_8)
        plaintext = b"Test"

        # Zero seed should not lock up the LFSR
        ciphertext = scrambler.encrypt(plaintext, b"\x00")
        assert ciphertext != plaintext  # Should still encrypt

    def test_generate_keystream(self):
        """Test keystream generation."""
        scrambler = Scrambler(mode=ScramblerMode.BIT_24)
        seed = b"\x12\x34\x56"

        keystream = scrambler.generate_keystream(10, seed)
        assert len(keystream) == 10

        # Verify keystream is deterministic
        keystream2 = scrambler.generate_keystream(10, seed)
        assert keystream == keystream2

    def test_keystream_xor_equals_encrypt(self):
        """Test that manual XOR with keystream equals encrypt."""
        scrambler = Scrambler(mode=ScramblerMode.BIT_24)
        plaintext = b"Hello M17!"
        seed = b"\x12\x34\x56"

        keystream = scrambler.generate_keystream(len(plaintext), seed)
        manual_cipher = bytes(p ^ k for p, k in zip(plaintext, keystream, strict=False))

        auto_cipher = scrambler.encrypt(plaintext, seed)
        assert manual_cipher == auto_cipher

    def test_large_data(self):
        """Test encryption of larger data."""
        scrambler = Scrambler(mode=ScramblerMode.BIT_24)
        plaintext = bytes(range(256)) * 4  # 1024 bytes
        seed = b"\x12\x34\x56"

        ciphertext = scrambler.encrypt(plaintext, seed)
        decrypted = scrambler.decrypt(ciphertext, seed)

        assert decrypted == plaintext


class TestScramblerConvenienceFunctions:
    """Tests for scrambler_encrypt and scrambler_decrypt."""

    def test_encrypt_decrypt_default_mode(self):
        """Test convenience functions with default 24-bit mode."""
        plaintext = b"Hello M17!"
        seed = b"\x12\x34\x56"

        ciphertext = scrambler_encrypt(plaintext, seed)
        decrypted = scrambler_decrypt(ciphertext, seed)

        assert decrypted == plaintext

    def test_encrypt_decrypt_explicit_mode(self):
        """Test convenience functions with explicit mode."""
        plaintext = b"Hello M17!"
        seed = b"\x12\x34"

        ciphertext = scrambler_encrypt(plaintext, seed, mode=ScramblerMode.BIT_16)
        decrypted = scrambler_decrypt(ciphertext, seed, mode=ScramblerMode.BIT_16)

        assert decrypted == plaintext

    def test_encrypt_decrypt_int_mode(self):
        """Test convenience functions with integer mode."""
        plaintext = b"Hello M17!"
        seed = b"\x42"

        ciphertext = scrambler_encrypt(plaintext, seed, mode=8)
        decrypted = scrambler_decrypt(ciphertext, seed, mode=8)

        assert decrypted == plaintext


# AES tests - only run if cryptography is available
try:
    from m17.crypto.aes import (
        HAS_CRYPTOGRAPHY,
        AESEncryptor,
        AESMode,
        aes_decrypt,
        aes_encrypt,
    )

    @pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography not installed")
    class TestAESMode:
        """Tests for AESMode enum."""

        def test_modes_exist(self):
            """Test all AES modes exist."""
            assert AESMode.AES_128 == 128
            assert AESMode.AES_192 == 192
            assert AESMode.AES_256 == 256

    @pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography not installed")
    class TestAESEncryptor:
        """Tests for AESEncryptor class."""

        def test_key_bytes(self):
            """Test key_bytes property."""
            assert AESEncryptor(mode=AESMode.AES_128).key_bytes == 16
            assert AESEncryptor(mode=AESMode.AES_192).key_bytes == 24
            assert AESEncryptor(mode=AESMode.AES_256).key_bytes == 32

        def test_encrypt_decrypt_128(self):
            """Test AES-128 encrypt/decrypt roundtrip."""
            encryptor = AESEncryptor(mode=AESMode.AES_128)
            plaintext = b"Hello M17!"
            key = bytes(16)  # 128-bit key
            meta_iv = bytes(14)

            ciphertext = encryptor.encrypt(plaintext, key, meta_iv, frame_number=0)
            assert ciphertext != plaintext

            decrypted = encryptor.decrypt(ciphertext, key, meta_iv, frame_number=0)
            assert decrypted == plaintext

        def test_encrypt_decrypt_192(self):
            """Test AES-192 encrypt/decrypt roundtrip."""
            encryptor = AESEncryptor(mode=AESMode.AES_192)
            plaintext = b"Hello M17!"
            key = bytes(24)  # 192-bit key
            meta_iv = bytes(14)

            ciphertext = encryptor.encrypt(plaintext, key, meta_iv)
            decrypted = encryptor.decrypt(ciphertext, key, meta_iv)

            assert decrypted == plaintext

        def test_encrypt_decrypt_256(self):
            """Test AES-256 encrypt/decrypt roundtrip."""
            encryptor = AESEncryptor(mode=AESMode.AES_256)
            plaintext = b"Hello M17!"
            key = bytes(32)  # 256-bit key
            meta_iv = bytes(14)

            ciphertext = encryptor.encrypt(plaintext, key, meta_iv)
            decrypted = encryptor.decrypt(ciphertext, key, meta_iv)

            assert decrypted == plaintext

        def test_different_frame_numbers(self):
            """Test that different frame numbers produce different ciphertext."""
            encryptor = AESEncryptor(mode=AESMode.AES_256)
            plaintext = b"Test data"
            key = bytes(32)
            meta_iv = bytes(14)

            cipher0 = encryptor.encrypt(plaintext, key, meta_iv, frame_number=0)
            cipher1 = encryptor.encrypt(plaintext, key, meta_iv, frame_number=1)

            assert cipher0 != cipher1

        def test_same_params_same_output(self):
            """Test deterministic encryption."""
            encryptor = AESEncryptor(mode=AESMode.AES_256)
            plaintext = b"Test data"
            key = bytes(32)
            meta_iv = bytes(14)

            cipher1 = encryptor.encrypt(plaintext, key, meta_iv, frame_number=42)
            cipher2 = encryptor.encrypt(plaintext, key, meta_iv, frame_number=42)

            assert cipher1 == cipher2

        def test_packet_mode(self):
            """Test packet mode with full 16-byte IV."""
            encryptor = AESEncryptor(mode=AESMode.AES_256)
            plaintext = b"Packet data"
            key = bytes(32)
            full_iv = bytes(16)

            ciphertext = encryptor.encrypt_packet(plaintext, key, full_iv)
            decrypted = encryptor.decrypt_packet(ciphertext, key, full_iv)

            assert decrypted == plaintext

        def test_key_too_short(self):
            """Test that short key raises error."""
            encryptor = AESEncryptor(mode=AESMode.AES_256)

            with pytest.raises(ValueError, match="Key too short"):
                encryptor.encrypt(b"test", b"short", bytes(14))

        def test_key_truncation(self):
            """Test that long key is truncated."""
            encryptor = AESEncryptor(mode=AESMode.AES_128)
            plaintext = b"Test"
            meta_iv = bytes(14)

            # Both should work and produce same result
            key16 = bytes(range(16))
            key32 = bytes(range(32))  # Will be truncated to 16

            cipher1 = encryptor.encrypt(plaintext, key16, meta_iv)
            cipher2 = encryptor.encrypt(plaintext, key32, meta_iv)

            assert cipher1 == cipher2

    @pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography not installed")
    class TestAESConvenienceFunctions:
        """Tests for aes_encrypt and aes_decrypt."""

        def test_encrypt_decrypt_default_mode(self):
            """Test convenience functions with default AES-256."""
            plaintext = b"Hello M17!"
            key = bytes(32)
            meta_iv = bytes(14)

            ciphertext = aes_encrypt(plaintext, key, meta_iv)
            decrypted = aes_decrypt(ciphertext, key, meta_iv)

            assert decrypted == plaintext

        def test_encrypt_decrypt_explicit_mode(self):
            """Test convenience functions with explicit mode."""
            plaintext = b"Hello M17!"
            key = bytes(16)
            meta_iv = bytes(14)

            ciphertext = aes_encrypt(plaintext, key, meta_iv, mode=AESMode.AES_128)
            decrypted = aes_decrypt(ciphertext, key, meta_iv, mode=AESMode.AES_128)

            assert decrypted == plaintext

        def test_encrypt_decrypt_int_mode(self):
            """Test convenience functions with integer mode."""
            plaintext = b"Hello M17!"
            key = bytes(24)
            meta_iv = bytes(14)

            ciphertext = aes_encrypt(plaintext, key, meta_iv, mode=192)
            decrypted = aes_decrypt(ciphertext, key, meta_iv, mode=192)

            assert decrypted == plaintext

    from m17.crypto.signature import (
        HAS_CRYPTOGRAPHY as HAS_SIG_CRYPTOGRAPHY,
    )
    from m17.crypto.signature import (
        PRIVATE_KEY_SIZE,
        PUBLIC_KEY_SIZE,
        SIGNATURE_SIZE,
        SigningKey,
        VerifyingKey,
        generate_keypair,
        sign_message,
        verify_signature,
    )

    @pytest.mark.skipif(not HAS_SIG_CRYPTOGRAPHY, reason="cryptography not installed")
    class TestSigningKey:
        """Tests for SigningKey class."""

        def test_generate(self):
            """Test key generation."""
            sk = SigningKey.generate()
            assert sk is not None

        def test_to_bytes(self):
            """Test exporting private key."""
            sk = SigningKey.generate()
            key_bytes = sk.to_bytes()

            assert len(key_bytes) == PRIVATE_KEY_SIZE
            assert isinstance(key_bytes, bytes)

        def test_from_bytes_roundtrip(self):
            """Test import/export roundtrip."""
            sk1 = SigningKey.generate()
            key_bytes = sk1.to_bytes()

            sk2 = SigningKey.from_bytes(key_bytes)
            assert sk1 == sk2

        def test_from_bytes_invalid_length(self):
            """Test error on invalid key length."""
            with pytest.raises(ValueError, match="Invalid private key length"):
                SigningKey.from_bytes(b"short")

        def test_verifying_key(self):
            """Test getting public key."""
            sk = SigningKey.generate()
            vk = sk.verifying_key

            assert isinstance(vk, VerifyingKey)

        def test_sign(self):
            """Test signing a message."""
            sk = SigningKey.generate()
            message = b"Hello M17!"

            signature = sk.sign(message)

            assert len(signature) == SIGNATURE_SIZE
            assert isinstance(signature, bytes)

        def test_sign_deterministic_with_different_messages(self):
            """Test that different messages produce different signatures."""
            sk = SigningKey.generate()

            sig1 = sk.sign(b"Message 1")
            sig2 = sk.sign(b"Message 2")

            assert sig1 != sig2

        def test_sign_empty_message(self):
            """Test signing empty message."""
            sk = SigningKey.generate()
            signature = sk.sign(b"")

            assert len(signature) == SIGNATURE_SIZE

    @pytest.mark.skipif(not HAS_SIG_CRYPTOGRAPHY, reason="cryptography not installed")
    class TestVerifyingKey:
        """Tests for VerifyingKey class."""

        def test_to_bytes(self):
            """Test exporting public key."""
            sk = SigningKey.generate()
            vk = sk.verifying_key

            key_bytes = vk.to_bytes()
            assert len(key_bytes) == PUBLIC_KEY_SIZE

        def test_to_bytes_compressed(self):
            """Test exporting compressed public key."""
            sk = SigningKey.generate()
            vk = sk.verifying_key

            key_bytes = vk.to_bytes(compressed=True)
            assert len(key_bytes) == 33  # Compressed format

        def test_from_bytes_uncompressed(self):
            """Test importing uncompressed public key."""
            sk = SigningKey.generate()
            vk1 = sk.verifying_key

            key_bytes = vk1.to_bytes()
            vk2 = VerifyingKey.from_bytes(key_bytes)

            assert vk1 == vk2

        def test_from_bytes_compressed(self):
            """Test importing compressed public key."""
            sk = SigningKey.generate()
            vk1 = sk.verifying_key

            key_bytes = vk1.to_bytes(compressed=True)
            vk2 = VerifyingKey.from_bytes(key_bytes)

            assert vk1 == vk2

        def test_from_bytes_invalid(self):
            """Test error on invalid public key."""
            with pytest.raises(ValueError, match="Invalid public key"):
                VerifyingKey.from_bytes(bytes(64))  # All zeros is invalid point

        def test_verify_valid(self):
            """Test verifying valid signature."""
            sk = SigningKey.generate()
            vk = sk.verifying_key
            message = b"Hello M17!"

            signature = sk.sign(message)
            assert vk.verify(message, signature) is True

        def test_verify_invalid_signature(self):
            """Test rejecting invalid signature."""
            sk = SigningKey.generate()
            vk = sk.verifying_key
            message = b"Hello M17!"

            # Random signature
            signature = bytes(SIGNATURE_SIZE)
            assert vk.verify(message, signature) is False

        def test_verify_wrong_message(self):
            """Test rejecting signature for wrong message."""
            sk = SigningKey.generate()
            vk = sk.verifying_key

            signature = sk.sign(b"Original message")
            assert vk.verify(b"Different message", signature) is False

        def test_verify_wrong_key(self):
            """Test rejecting signature from different key."""
            sk1 = SigningKey.generate()
            sk2 = SigningKey.generate()
            message = b"Hello M17!"

            signature = sk1.sign(message)
            assert sk2.verifying_key.verify(message, signature) is False

        def test_verify_short_signature(self):
            """Test rejecting short signature."""
            sk = SigningKey.generate()
            vk = sk.verifying_key

            assert vk.verify(b"message", b"short") is False

    @pytest.mark.skipif(not HAS_SIG_CRYPTOGRAPHY, reason="cryptography not installed")
    class TestSignatureConvenienceFunctions:
        """Tests for convenience functions."""

        def test_sign_verify_roundtrip(self):
            """Test sign_message and verify_signature."""
            private_key, public_key = generate_keypair()
            message = b"Hello M17!"

            signature = sign_message(message, private_key)
            assert verify_signature(message, signature, public_key) is True

        def test_generate_keypair(self):
            """Test keypair generation."""
            private_key, public_key = generate_keypair()

            assert len(private_key) == PRIVATE_KEY_SIZE
            assert len(public_key) == PUBLIC_KEY_SIZE

        def test_verify_with_invalid_key(self):
            """Test verify returns False for invalid key."""
            result = verify_signature(b"message", bytes(64), b"invalid")
            assert result is False

        def test_sign_verify_empty_message(self):
            """Test signing/verifying empty message."""
            private_key, public_key = generate_keypair()

            signature = sign_message(b"", private_key)
            assert verify_signature(b"", signature, public_key) is True

        def test_sign_verify_large_message(self):
            """Test signing/verifying large message."""
            private_key, public_key = generate_keypair()
            message = bytes(range(256)) * 100  # 25.6 KB

            signature = sign_message(message, private_key)
            assert verify_signature(message, signature, public_key) is True

except ImportError:
    pass  # Skip AES/signature tests if cryptography not installed
