# pyM17

[![CI](https://github.com/M17-Project/pyM17/actions/workflows/ci.yml/badge.svg)](https://github.com/M17-Project/pyM17/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/M17-Project/pyM17/branch/main/graph/badge.svg)](https://codecov.io/gh/M17-Project/pyM17)

> **Note:** This library is under active development and the API may change. Not recommended for production use yet.

A Python library for the M17 digital radio protocol, compliant with M17 specification v2.0.3 and v3.0.0 (WIP).

## Features

- **Core Protocol Support**
  - Base-40 callsign encoding/decoding with hash-address and broadcast support
  - CRC-16 (polynomial 0x5935) per M17 specification
  - TYPE field handling with encryption and metadata support
  - v3.0.0 TYPE field with expanded payload types, encryption options, and META types
  - Automatic version detection (v2.0.3 vs v3.0.0)

- **Frame Handling**
  - Link Setup Frame (LSF) with META field variants (position, extended callsign, nonce)
  - Stream frames for real-time voice/data
  - Packet frames for bulk data transfer
  - IP frames for M17-over-IP networking
  - v3.0.0 multi-block text META (up to 195 bytes over 15 frames)
  - v3.0.0 TLE packet type for satellite orbital data
  - v3.0.0 packet protocol identifiers (RAW, AX.25, APRS, 6LoWPAN, IPv4, SMS, Winlink, TLE)

- **Forward Error Correction (FEC)**
  - Golay(24,12) codec for LICH protection
  - K=5 rate 1/2 convolutional encoder
  - Soft-decision Viterbi decoder
  - Puncture patterns (P1, P2, P3)
  - 368-element interleaver
  - 46-byte randomizer

- **Networking**
  - n7tae reflector protocol client
  - Kademlia DHT for distributed routing
  - P2P connections with NAT traversal

- **Cryptography** (optional)
  - Scrambler encryption (8/16/24-bit LFSR)
  - AES encryption (128/192/256-bit CTR mode)
  - ECDSA digital signatures (secp256r1) for v3.0.0
  - BERT (Bit Error Rate Test) frame support

- **Audio** (optional)
  - Codec2 integration for voice encoding
  - Audio I/O processing blocks

## Installation

```bash
# Basic installation
pip install m17

# With audio support
pip install m17[audio]

# With DHT networking
pip install m17[dht]

# With cryptography (AES, digital signatures)
pip install m17[crypto]

# All optional dependencies
pip install m17[all]
```

### From Source

```bash
git clone https://github.com/M17-Project/pyM17.git
cd pyM17/src/m17
poetry install        # or: pip install -e .
```

## Quick Start

### Address Encoding

```python
from m17.core.address import Address

# Create from callsign
addr = Address(callsign="W2FBI")
print(f"Numeric: {addr.numeric:#x}")  # 0x161ae1f
print(f"Bytes: {addr.addr.hex()}")

# Create from numeric
addr2 = Address(numeric=0x161AE1F)
print(f"Callsign: {addr2.callsign}")  # W2FBI

# Special addresses
broadcast = Address(callsign="@ALL")
print(f"Is broadcast: {broadcast.is_broadcast}")  # True
```

### Creating Frames

```python
from m17.core.address import Address
from m17.frames import LinkSetupFrame, IPFrame, M17Payload

# Create a Link Setup Frame
lsf = LinkSetupFrame(
    dst=Address(callsign="W2FBI"),
    src=Address(callsign="N0CALL"),
    type_field=0x0005,  # Voice stream, no encryption
)

# Add position metadata
lsf.set_position_meta(
    latitude=40.7128,
    longitude=-74.0060,
    altitude=100.0,
)

# Serialize
data = lsf.to_bytes()  # 30 bytes with CRC

# Create an IP frame for network transmission
ip_frame = IPFrame.create(
    dst="W2FBI",
    src="N0CALL",
    stream_id=0x1234,
    payload=b"voice_data_here!",
)
```

### CRC Calculation

```python
from m17.core.crc import crc_m17, verify_crc

# Calculate CRC
data = b"Hello M17!"
checksum = crc_m17(data)
print(f"CRC: {checksum:#06x}")

# Verify CRC
data_with_crc = data + checksum.to_bytes(2, "big")
print(f"Valid: {verify_crc(data_with_crc)}")  # True
```

### FEC Encoding (for RF transmission)

```python
from m17.codec.golay import golay24_encode, encode_lich
from m17.codec.convolutional import convolutional_encode
from m17.codec.interleave import interleave
from m17.codec.randomize import randomize

# Golay encoding for LICH
lich_chunk = bytes([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC])
encoded_lich = encode_lich(lich_chunk)  # 12 bytes (96 bits)

# Full FEC pipeline for payload
payload_bits = [...]  # 272 bits
encoded = convolutional_encode(payload_bits)  # Convolutional encoding
interleaved = interleave(encoded)  # Spread burst errors
randomized = randomize(interleaved)  # Decorrelate
```

### v3.0.0 Features

```python
from m17.core.types import (
    M17Payload, M17Encryption, M17Meta, M17Version,
    build_type_field_v3, parse_type_field_v3, detect_type_field_version,
)
from m17.frames.lsf import LinkSetupFrame, MetaText
from m17.frames.packet import TLEPacket, PacketProtocol

# Build v3.0.0 TYPE field
type_field = build_type_field_v3(
    payload=M17Payload.VOICE_3200,
    encryption=M17Encryption.AES_256,
    signed=True,
    meta=M17Meta.TEXT_DATA,
    can=5,
)

# Detect version from existing frame
version = detect_type_field_version(0x0005)  # v2.0.3
version = detect_type_field_version(0x0020)  # v3.0.0

# Create LSF with v3.0.0 TYPE field
lsf = LinkSetupFrame(dst="W2FBI", src="N0CALL")
lsf.set_type_v3(
    payload=M17Payload.VOICE_3200,
    meta=M17Meta.TEXT_DATA,
)

# Multi-block text META (up to 195 bytes)
lsf.set_text_meta("Hello M17! This is a longer message.")
text_blocks = MetaText.encode_multi_block("Very long message...")

# TLE packet for satellite data
tle = TLEPacket(
    satellite_name="ISS (ZARYA)",
    tle_line1="1 25544U 98067A   21275.52043534...",
    tle_line2="2 25544  51.6442 123.4567...",
)
packet_data = tle.to_bytes()

# Packet protocol identifiers
print(PacketProtocol.APRS)    # 0x02
print(PacketProtocol.TLE)     # 0x07
```

### Encryption (requires `cryptography`)

```python
from m17.crypto.scrambler import Scrambler, ScramblerMode
from m17.crypto.aes import AESEncryptor, AESMode

# Scrambler encryption (8/16/24-bit LFSR)
scrambler = Scrambler(mode=ScramblerMode.BIT_24)
seed = b"\x12\x34\x56"
ciphertext = scrambler.encrypt(b"Hello M17!", seed)
plaintext = scrambler.decrypt(ciphertext, seed)

# AES encryption (128/192/256-bit CTR mode)
encryptor = AESEncryptor(mode=AESMode.AES_256)
key = bytes(32)  # 256-bit key
meta_iv = bytes(14)  # From META field
frame_number = 0

ciphertext = encryptor.encrypt(b"Voice data", key, meta_iv, frame_number)
plaintext = encryptor.decrypt(ciphertext, key, meta_iv, frame_number)
```

### Digital Signatures (requires `cryptography`)

```python
from m17.crypto.signature import SigningKey, generate_keypair, sign_message, verify_signature

# Generate keypair
sk = SigningKey.generate()
vk = sk.verifying_key

# Sign and verify
message = b"Authenticated transmission"
signature = sk.sign(message)
is_valid = vk.verify(message, signature)  # True

# Convenience functions
private_key, public_key = generate_keypair()
signature = sign_message(message, private_key)
is_valid = verify_signature(message, signature, public_key)
```

### BERT (Bit Error Rate Test)

```python
from m17.frames.bert import BERTFrame, BERTGenerator, calculate_ber

# Generate BERT test frame
bert = BERTFrame.generate(seed=0x1FF)
rf_data = bert.encode_for_rf()  # 48 bytes with sync word

# At receiver - calculate BER
received = BERTFrame.from_rf(rf_data)
expected = BERTFrame.generate(seed=0x1FF)
ber = received.calculate_ber(expected)
print(f"BER: {ber:.2%}")  # 0.00%

# Direct BER calculation
ber = calculate_ber(received_bytes, expected_bytes)
```

## Module Structure

```
m17/
├── core/           # Core protocol primitives
│   ├── address.py  # Base-40 callsign encoding
│   ├── crc.py      # CRC-16 implementation
│   ├── types.py    # TYPE field enums
│   └── constants.py
├── frames/         # Frame definitions
│   ├── lsf.py      # Link Setup Frame + META
│   ├── stream.py   # Stream frames
│   ├── packet.py   # Packet frames
│   ├── ip.py       # IP frames
│   ├── lich.py     # LICH handling
│   └── bert.py     # BERT test frames
├── codec/          # FEC layer
│   ├── golay.py    # Golay(24,12)
│   ├── convolutional.py
│   ├── viterbi.py  # Soft Viterbi decoder
│   ├── puncture.py # P1, P2, P3 patterns
│   ├── interleave.py
│   └── randomize.py
├── crypto/         # Cryptography (optional)
│   ├── scrambler.py  # LFSR scrambler
│   ├── aes.py        # AES-CTR encryption
│   └── signature.py  # ECDSA signatures
├── net/            # Networking
│   ├── reflector.py
│   ├── dht.py
│   ├── p2p.py
│   └── client.py
└── audio/          # Audio processing
    ├── codec2.py
    └── blocks.py
```

## Requirements

- Python 3.12+
- numpy >= 2.2
- pydantic >= 2.9

### Optional Dependencies

- **Audio**: pycodec2, soundcard, samplerate
- **DHT**: kademlia, rpcudp
- **Crypto**: cryptography (for AES encryption and digital signatures)

### Audio Dependencies

The audio module requires [pycodec2](https://github.com/gregorias/pycodec2), which depends on the Codec2 C library. Install Codec2 first:

**Debian/Ubuntu:**
```bash
sudo apt install codec2 libcodec2-dev
```

**Fedora/RHEL:**
```bash
sudo dnf install codec2 codec2-devel
```

**macOS (Homebrew):**
```bash
brew install codec2
```

**From source:**
```bash
git clone https://github.com/drowe67/codec2.git
cd codec2 && mkdir build && cd build
cmake .. && make && sudo make install
```

Then install pyM17 with audio support:
```bash
pip install m17[audio]
```

## Testing

```bash
# Install with dev dependencies (using Poetry)
poetry install

# Run tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=m17 --cov-report=html

# Run specific test file
poetry run pytest tests/test_crypto.py -v
```

## Development

### Code Quality

Pre-commit hooks are configured for code quality checks:

```bash
# Install pre-commit hooks
pre-commit install

# Run all hooks manually
pre-commit run --all-files
```

Configured hooks:
- **ruff** - Linting and formatting
- **mypy** - Type checking (strict mode)
- **poetry-check** - Dependency validation

### CI/CD

GitHub Actions runs on every push/PR:
- pytest with coverage reporting to Codecov
- mypy type checking
- ruff linting and format checking

## Specification Compliance

This library implements the [M17 Protocol Specification](https://spec.m17project.org/):
- **v2.0.3** - Fully supported (legacy)
- **v3.0.0** - Work in progress (based on dev branch)

Key compliance points:
- CRC-16 polynomial 0x5935, init 0xFFFF
- Base-40 callsign alphabet: ` 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-/.`
- Golay(24,12) for LICH protection
- K=5 rate 1/2 convolutional code (G1=0x19, G2=0x17)
- 368-element QPP interleaver
- 46-byte randomizer sequence

v3.0.0 additions:
- Redesigned TYPE field: PAYLOAD(4), ENCRYPTION(3), SIGNED(1), META(4), CAN(4)
- Multi-block text META (15 blocks × 13 bytes = 195 bytes max)
- TLE packet protocol for satellite orbital data
- Automatic version detection via PAYLOAD field
- ECDSA digital signatures (secp256r1)
- Expanded encryption: 8/16/24-bit scrambler, AES-128/192/256

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- [M17 Project](https://m17project.org/)
- [M17 Specification](https://spec.m17project.org/)
- [libm17](https://github.com/M17-Project/libm17) - C reference implementation
