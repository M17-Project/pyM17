"""Stream encryption (AES-CTR, scramblers) and signatures (ECDSA P-256).

Compatible with gr-m17 and the M17 specification 2.1. AES and ECDSA need the
``cryptography`` package (``pip install m17[crypto]``).

- AES: the counter block is the 14-byte nonce (META) followed by the 15-bit
  frame number. One 16-byte payload per frame, so encryption and decryption
  are the same operation.
- Scrambler: an 8, 16 or 24-bit LFSR, selected by the seed length. Each frame
  uses the next 128 bits of its output.
- Signature (specification 2.1): a SHA-256 hash of the tag "M17-SIG-v2" and
  every frame's 16-bit FN and 16-byte payload as transmitted (encrypted, if the
  stream is), ending with the Authentication Frame (FN 0x7FFB: signer callsign,
  destination, time of signing). The 32-byte hash is signed with ECDSA over
  secp256r1. Keys and signatures are raw bytes as in micro-ecc: private key 32
  bytes, public key 64 bytes (x, y), signature 64 bytes (r, s).
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
    return bytes(a ^ b for a, b in zip(payload, block, strict=True))


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
        """Encrypt or decrypt the 16-byte payload of frame ``frame``."""
        return bytes(a ^ b for a, b in zip(payload, self.keystream(frame), strict=True))


# ---- signatures


EPOCH_2020 = 1577836800  # 2020-01-01T00:00:00Z as a Unix time
AUTH_FN = 0x7FFB  # the Authentication Frame, sent before the signature frames


class StreamHash:
    """Hash of a signed stream (specification 2.1). Feed every frame from FN 0, then the
    Authentication Frame, each with its FN and its payload as transmitted."""

    def __init__(self) -> None:
        import hashlib

        self._h = hashlib.sha256(b"M17-SIG-v2")

    def update(self, fn: int, payload: bytes) -> None:
        if len(payload) != 16:
            raise ValueError("payload must be 16 bytes")
        self._h.update((fn & 0xFFFF).to_bytes(2, "big") + bytes(payload))

    @property
    def digest(self) -> bytes:
        """The 32-byte hash of the frames so far."""
        return self._h.digest()


def auth_payload(signer: str, destination: str, timestamp: int) -> bytes:
    """Authentication Frame payload: signer callsign, destination, ``timestamp`` (Unix time)."""
    from .callsign import callsign_to_bytes

    t = (timestamp - EPOCH_2020) & 0xFFFFFFFF
    return callsign_to_bytes(signer) + callsign_to_bytes(destination) + t.to_bytes(4, "big")


def parse_auth(payload: bytes) -> tuple[str, str, int]:
    """(signer, destination, Unix time of signing) from an Authentication Frame payload."""
    from .callsign import callsign_from_bytes

    if len(payload) != 16:
        raise ValueError("payload must be 16 bytes")
    return (
        callsign_from_bytes(payload[0:6]),
        callsign_from_bytes(payload[6:12]),
        int.from_bytes(payload[12:16], "big") + EPOCH_2020,
    )


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


def _check_hash(digest: bytes) -> bytes:
    if len(digest) != 32:
        raise ValueError("the stream hash is 32 bytes (M17 specification 2.1, see StreamHash)")
    return bytes(digest)


def sign(private: bytes, digest: bytes) -> bytes:
    """64-byte signature (r, s) of a 32-byte stream hash, used directly as the ECDSA message hash."""
    from cryptography.hazmat.primitives.asymmetric import ec, utils

    key = ec.derive_private_key(int.from_bytes(private, "big"), _curve())
    r, s = utils.decode_dss_signature(key.sign(_check_hash(digest), _prehashed()))
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def verify(public: bytes, digest: bytes, signature: bytes) -> bool:
    """True if ``signature`` over the 32-byte stream hash ``digest`` is valid for the 64-byte public key."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric import ec, utils

    digest = _check_hash(digest)  # a wrong length is a usage error, not an invalid signature
    try:
        key = ec.EllipticCurvePublicKey.from_encoded_point(_curve(), b"\x04" + bytes(public))
        der = utils.encode_dss_signature(int.from_bytes(signature[:32], "big"), int.from_bytes(signature[32:64], "big"))
        key.verify(der, digest, _prehashed())
        return True
    except (InvalidSignature, ValueError):
        return False
