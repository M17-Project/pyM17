"""Stream encryption (AES-CTR, scramblers) and signatures (ECDSA P-256).

Compatible with gr-m17 and the M17 specification 2.0. AES and ECDSA need the
``cryptography`` package (``pip install m17[crypto]``).

- AES: the counter block is the 14-byte nonce (META) followed by the 15-bit
  frame number. One 16-byte payload per frame, so encryption and decryption
  are the same operation.
- Scrambler: an 8, 16 or 24-bit LFSR, selected by the seed length. Each frame
  uses the next 128 bits of its output.
- Signature: a 16-byte digest of the (encrypted) payloads, signed with ECDSA
  over secp256r1. Keys and signatures are raw bytes as in micro-ecc: private
  key 32 bytes, public key 64 bytes (x, y), signature 64 bytes (r, s).
"""

# ---- AES


def aes_crypt(key: bytes, nonce: bytes, fn: int, payload: bytes) -> bytes:
    """Encrypt or decrypt one 16-byte payload. ``key`` is 16, 24 or 32 bytes."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    if len(key) not in (16, 24, 32):
        raise ValueError("AES key must be 16, 24 or 32 bytes")
    if len(nonce) != 14 or len(payload) != 16:
        raise ValueError("nonce must be 14 bytes, payload 16 bytes")
    counter = bytes(nonce) + bytes([(fn >> 8) & 0x7F, fn & 0xFF])
    block = Cipher(algorithms.AES(bytes(key)), modes.ECB()).encryptor().update(counter)
    return bytes(a ^ b for a, b in zip(payload, block))


# ---- scrambler

_TAPS = {1: (7, 5, 4, 3), 2: (15, 14, 12, 3), 3: (23, 22, 21, 16)}


class Scrambler:
    """Scrambler keystream from a 1, 2 or 3-byte seed (8, 16 or 24-bit LFSR)."""

    def __init__(self, seed: bytes) -> None:
        if len(seed) not in _TAPS:
            raise ValueError("scrambler seed must be 1, 2 or 3 bytes")
        self._taps = _TAPS[len(seed)]
        self._mask = (1 << (8 * len(seed))) - 1
        self._seed = int.from_bytes(seed, "big")
        self._frame, self._lfsr = 0, self._seed

    def keystream(self, frame: int) -> bytes:
        """The 16 keystream bytes of frame number ``frame`` (counted from 0)."""
        if frame < self._frame:  # e.g. a new stream: start over from the seed
            self._frame, self._lfsr = 0, self._seed
        while self._frame <= frame:
            out = 0
            lfsr = self._lfsr
            for _ in range(128):
                bit = 0
                for t in self._taps:
                    bit ^= lfsr >> t
                bit &= 1
                lfsr = ((lfsr << 1) | bit) & 0xFFFFFF
                out = (out << 1) | bit
            self._frame, self._lfsr = self._frame + 1, lfsr & self._mask
        return out.to_bytes(16, "big")

    def crypt(self, frame: int, payload: bytes) -> bytes:
        """Encrypt or decrypt the payload of frame ``frame``."""
        return bytes(a ^ b for a, b in zip(payload, self.keystream(frame)))


# ---- signatures


class StreamDigest:
    """Digest of a signed stream: each payload is XORed in, then rotated left by a byte."""

    def __init__(self) -> None:
        self._d = bytearray(16)

    def update(self, payload: bytes) -> None:
        for i in range(16):
            self._d[i] ^= payload[i]
        self._d.append(self._d.pop(0))

    @property
    def digest(self) -> bytes:
        return bytes(self._d)


def _curve():
    from cryptography.hazmat.primitives.asymmetric import ec

    return ec.SECP256R1()


def _prehashed():
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, utils

    return ec.ECDSA(utils.Prehashed(hashes.SHA256()))


def generate_key() -> tuple[bytes, bytes]:
    """A new (private key, public key) pair."""
    from cryptography.hazmat.primitives.asymmetric import ec

    private = ec.generate_private_key(_curve()).private_numbers().private_value.to_bytes(32, "big")
    return private, public_key(private)


def public_key(private: bytes) -> bytes:
    """The 64-byte public key of a 32-byte private key."""
    from cryptography.hazmat.primitives.asymmetric import ec

    nums = ec.derive_private_key(int.from_bytes(private, "big"), _curve()).public_key().public_numbers()
    return nums.x.to_bytes(32, "big") + nums.y.to_bytes(32, "big")


def sign(private: bytes, digest: bytes) -> bytes:
    """64-byte signature of a 16-byte stream digest."""
    from cryptography.hazmat.primitives.asymmetric import ec, utils

    key = ec.derive_private_key(int.from_bytes(private, "big"), _curve())
    # micro-ecc signs the 16-byte digest as is, which equals a zero-padded 32-byte prehash
    r, s = utils.decode_dss_signature(key.sign(bytes(16) + digest, _prehashed()))
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def verify(public: bytes, digest: bytes, signature: bytes) -> bool:
    """True if ``signature`` over ``digest`` is valid for the 64-byte public key."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric import ec, utils

    try:
        key = ec.EllipticCurvePublicKey.from_encoded_point(_curve(), b"\x04" + bytes(public))
        der = utils.encode_dss_signature(int.from_bytes(signature[:32], "big"), int.from_bytes(signature[32:64], "big"))
        key.verify(der, bytes(16) + digest, _prehashed())
        return True
    except (InvalidSignature, ValueError):
        return False
