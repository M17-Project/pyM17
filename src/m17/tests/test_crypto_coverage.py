"""Additional tests for M17 cryptographic modules to improve coverage.

These tests target specific uncovered code paths in:
- crypto/aes.py (IV handling, edge cases)
- crypto/scrambler.py (_get_taps_mask method)
- crypto/signature.py (equality methods, edge cases)
"""

import pytest


class TestScramblerInternals:
    """Tests for Scrambler internal methods."""

    def test_get_taps_mask_8bit(self):
        """Test _get_taps_mask for 8-bit mode."""
        from m17.crypto.scrambler import LFSR_TAPS, Scrambler, ScramblerMode

        scrambler = Scrambler(mode=ScramblerMode.BIT_8)
        mask = scrambler._get_taps_mask()

        # Taps are at positions 8, 6, 5, 4
        # Mask should have bits set at positions 7, 5, 4, 3 (0-indexed)
        expected = 0
        for tap in LFSR_TAPS[ScramblerMode.BIT_8]:
            expected |= 1 << (tap - 1)

        assert mask == expected
        # Verify specific bits: 0b11111000 would be wrong
        # Correct: bits 7, 5, 4, 3 = 0b10111000 = 0xB8
        assert mask == 0xB8

    def test_get_taps_mask_16bit(self):
        """Test _get_taps_mask for 16-bit mode."""
        from m17.crypto.scrambler import LFSR_TAPS, Scrambler, ScramblerMode

        scrambler = Scrambler(mode=ScramblerMode.BIT_16)
        mask = scrambler._get_taps_mask()

        # Taps are at positions 16, 14, 13, 11
        expected = 0
        for tap in LFSR_TAPS[ScramblerMode.BIT_16]:
            expected |= 1 << (tap - 1)

        assert mask == expected

    def test_get_taps_mask_24bit(self):
        """Test _get_taps_mask for 24-bit mode."""
        from m17.crypto.scrambler import LFSR_TAPS, Scrambler, ScramblerMode

        scrambler = Scrambler(mode=ScramblerMode.BIT_24)
        mask = scrambler._get_taps_mask()

        # Taps are at positions 24, 23, 22, 17
        expected = 0
        for tap in LFSR_TAPS[ScramblerMode.BIT_24]:
            expected |= 1 << (tap - 1)

        assert mask == expected


# AES tests - only run if cryptography is available
try:
    from m17.crypto.aes import HAS_CRYPTOGRAPHY

    @pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography not installed")
    class TestAESIVHandling:
        """Tests for AES IV handling edge cases."""

        def test_build_iv_short_meta_iv(self):
            """Test _build_iv with short meta_iv (< 14 bytes)."""
            from m17.crypto.aes import AESEncryptor

            encryptor = AESEncryptor()

            # Short meta_iv should be padded
            short_iv = bytes([0x01, 0x02, 0x03])  # 3 bytes
            iv = encryptor._build_iv(short_iv, frame_number=0x1234)

            assert len(iv) == 16
            # First 3 bytes should be the short_iv
            assert iv[:3] == short_iv
            # Bytes 3-13 should be zero padding
            assert iv[3:14] == bytes(11)
            # Last 2 bytes should be frame number
            assert iv[14:16] == b"\x12\x34"

        def test_build_iv_long_meta_iv(self):
            """Test _build_iv with long meta_iv (> 14 bytes)."""
            from m17.crypto.aes import AESEncryptor

            encryptor = AESEncryptor()

            # Long meta_iv should be truncated
            long_iv = bytes(range(20))  # 20 bytes
            iv = encryptor._build_iv(long_iv, frame_number=0xABCD)

            assert len(iv) == 16
            # First 14 bytes should be truncated meta_iv
            assert iv[:14] == bytes(range(14))
            # Last 2 bytes should be frame number
            assert iv[14:16] == b"\xAB\xCD"

        def test_build_iv_exact_meta_iv(self):
            """Test _build_iv with exact 14-byte meta_iv."""
            from m17.crypto.aes import AESEncryptor

            encryptor = AESEncryptor()

            # Exact length should work directly
            exact_iv = bytes(range(14))
            iv = encryptor._build_iv(exact_iv, frame_number=0x0000)

            assert len(iv) == 16
            assert iv[:14] == exact_iv
            assert iv[14:16] == b"\x00\x00"

        def test_encrypt_packet_short_iv(self):
            """Test encrypt_packet with short IV (< 16 bytes)."""
            from m17.crypto.aes import AESEncryptor

            encryptor = AESEncryptor()
            plaintext = b"Test data"
            key = bytes(32)
            short_iv = bytes([0x01, 0x02, 0x03])  # 3 bytes

            # Should pad the IV
            ciphertext = encryptor.encrypt_packet(plaintext, key, short_iv)
            assert ciphertext != plaintext

            # Decrypt with same short IV
            decrypted = encryptor.decrypt_packet(ciphertext, key, short_iv)
            assert decrypted == plaintext

        def test_encrypt_packet_long_iv(self):
            """Test encrypt_packet with long IV (> 16 bytes)."""
            from m17.crypto.aes import AESEncryptor

            encryptor = AESEncryptor()
            plaintext = b"Test data"
            key = bytes(32)
            long_iv = bytes(range(20))  # 20 bytes

            # Should truncate the IV
            ciphertext = encryptor.encrypt_packet(plaintext, key, long_iv)
            assert ciphertext != plaintext

            # Decrypt with same long IV (will also be truncated)
            decrypted = encryptor.decrypt_packet(ciphertext, key, long_iv)
            assert decrypted == plaintext

        def test_encrypt_packet_exact_iv(self):
            """Test encrypt_packet with exact 16-byte IV."""
            from m17.crypto.aes import AESEncryptor

            encryptor = AESEncryptor()
            plaintext = b"Test data"
            key = bytes(32)
            exact_iv = bytes(16)

            ciphertext = encryptor.encrypt_packet(plaintext, key, exact_iv)
            decrypted = encryptor.decrypt_packet(ciphertext, key, exact_iv)
            assert decrypted == plaintext

        def test_frame_number_wrapping(self):
            """Test frame number boundary values."""
            from m17.crypto.aes import AESEncryptor

            encryptor = AESEncryptor()
            plaintext = b"Test"
            key = bytes(32)
            meta_iv = bytes(14)

            # Test max frame number
            cipher_max = encryptor.encrypt(plaintext, key, meta_iv, frame_number=0xFFFF)
            decrypted = encryptor.decrypt(cipher_max, key, meta_iv, frame_number=0xFFFF)
            assert decrypted == plaintext

            # Test frame number masking (values > 16 bits)
            cipher_overflow = encryptor.encrypt(
                plaintext, key, meta_iv, frame_number=0x10000
            )
            cipher_zero = encryptor.encrypt(plaintext, key, meta_iv, frame_number=0)
            assert cipher_overflow == cipher_zero  # Should wrap to 0

except ImportError:
    pass


# Signature tests - only run if cryptography is available
try:
    from m17.crypto.signature import HAS_CRYPTOGRAPHY as HAS_SIG_CRYPTOGRAPHY

    @pytest.mark.skipif(not HAS_SIG_CRYPTOGRAPHY, reason="cryptography not installed")
    class TestSignatureEquality:
        """Tests for signature key equality methods."""

        def test_signing_key_equality_not_implemented(self):
            """Test SigningKey.__eq__ returns NotImplemented for incompatible types."""
            from m17.crypto.signature import SigningKey

            sk = SigningKey.generate()

            # Compare with incompatible types
            assert sk.__eq__(42) is NotImplemented
            assert sk.__eq__("string") is NotImplemented
            assert sk.__eq__([1, 2, 3]) is NotImplemented
            assert sk.__eq__(None) is NotImplemented

        def test_verifying_key_equality_not_implemented(self):
            """Test VerifyingKey.__eq__ returns NotImplemented for incompatible types."""
            from m17.crypto.signature import SigningKey

            sk = SigningKey.generate()
            vk = sk.verifying_key

            # Compare with incompatible types
            assert vk.__eq__(42) is NotImplemented
            assert vk.__eq__("string") is NotImplemented
            assert vk.__eq__([1, 2, 3]) is NotImplemented
            assert vk.__eq__(None) is NotImplemented

        def test_signing_key_inequality_with_different_types(self):
            """Test SigningKey inequality with different types."""
            from m17.crypto.signature import SigningKey

            sk = SigningKey.generate()

            # Python's != uses __eq__ and then negates
            assert sk != 42
            assert sk != "string"
            assert sk != None  # noqa: E711

        def test_verifying_key_inequality_with_different_types(self):
            """Test VerifyingKey inequality with different types."""
            from m17.crypto.signature import SigningKey

            sk = SigningKey.generate()
            vk = sk.verifying_key

            # Python's != uses __eq__ and then negates
            assert vk != 42
            assert vk != "string"
            assert vk != None  # noqa: E711

        def test_signing_key_equality_same_key(self):
            """Test SigningKey equality with same key."""
            from m17.crypto.signature import SigningKey

            sk1 = SigningKey.generate()
            sk2 = SigningKey.from_bytes(sk1.to_bytes())

            assert sk1 == sk2
            assert not (sk1 != sk2)

        def test_signing_key_equality_different_keys(self):
            """Test SigningKey inequality with different keys."""
            from m17.crypto.signature import SigningKey

            sk1 = SigningKey.generate()
            sk2 = SigningKey.generate()

            assert sk1 != sk2
            assert not (sk1 == sk2)

        def test_verifying_key_equality_same_key(self):
            """Test VerifyingKey equality with same key."""
            from m17.crypto.signature import SigningKey, VerifyingKey

            sk = SigningKey.generate()
            vk1 = sk.verifying_key
            vk2 = VerifyingKey.from_bytes(vk1.to_bytes())

            assert vk1 == vk2
            assert not (vk1 != vk2)

        def test_verifying_key_equality_different_keys(self):
            """Test VerifyingKey inequality with different keys."""
            from m17.crypto.signature import SigningKey

            sk1 = SigningKey.generate()
            sk2 = SigningKey.generate()

            assert sk1.verifying_key != sk2.verifying_key

    @pytest.mark.skipif(not HAS_SIG_CRYPTOGRAPHY, reason="cryptography not installed")
    class TestSignatureEdgeCases:
        """Tests for signature edge cases."""

        def test_verifying_key_from_bytes_with_prefix(self):
            """Test VerifyingKey.from_bytes with 0x04 prefix included."""
            from m17.crypto.signature import SigningKey, VerifyingKey

            sk = SigningKey.generate()
            vk1 = sk.verifying_key

            # Get raw bytes without prefix
            raw_bytes = vk1.to_bytes()
            assert len(raw_bytes) == 64

            # Add 0x04 prefix manually
            with_prefix = b"\x04" + raw_bytes
            assert len(with_prefix) == 65

            # Should handle the prefix correctly
            vk2 = VerifyingKey.from_bytes(with_prefix)
            assert vk1 == vk2

        def test_verifying_key_from_bytes_invalid_length(self):
            """Test VerifyingKey.from_bytes with invalid length."""
            from m17.crypto.signature import VerifyingKey

            # Invalid lengths
            with pytest.raises(ValueError, match="Invalid public key length"):
                VerifyingKey.from_bytes(bytes(10))

            with pytest.raises(ValueError, match="Invalid public key length"):
                VerifyingKey.from_bytes(bytes(50))

            with pytest.raises(ValueError, match="Invalid public key length"):
                VerifyingKey.from_bytes(bytes(100))

        def test_signing_key_from_bytes_invalid_key(self):
            """Test SigningKey.from_bytes with invalid key value."""
            from m17.crypto.signature import SigningKey

            # All zeros is likely an invalid private key
            with pytest.raises(ValueError, match="Invalid private key"):
                SigningKey.from_bytes(bytes(32))

        def test_verify_signature_with_invalid_public_key(self):
            """Test verify_signature returns False for invalid public key."""
            from m17.crypto.signature import verify_signature

            # Invalid public key (wrong length)
            result = verify_signature(b"message", bytes(64), bytes(10))
            assert result is False

            # Invalid public key (all zeros, invalid point)
            result = verify_signature(b"message", bytes(64), bytes(64))
            assert result is False

except ImportError:
    pass
