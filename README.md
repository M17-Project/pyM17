# pyM17

> **Note:** This library is under active development and the API may change. Not recommended for production use yet.

A Python library for the M17 digital radio protocol, compliant with M17 specification v2.0.3.

## Features

- **Core Protocol Support**
  - Base-40 callsign encoding/decoding with hash-address and broadcast support
  - CRC-16 (polynomial 0x5935) per M17 specification
  - TYPE field handling with encryption and metadata support

- **Frame Handling**
  - Link Setup Frame (LSF) with META field variants (position, extended callsign, nonce)
  - Stream frames for real-time voice/data
  - Packet frames for bulk data transfer
  - IP frames for M17-over-IP networking

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

# All optional dependencies
pip install m17[all]
```

### From Source

```bash
git clone https://github.com/your-repo/pyM17.git
cd pyM17/src/m17
pip install -e .
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
│   └── lich.py     # LICH handling
├── codec/          # FEC layer
│   ├── golay.py    # Golay(24,12)
│   ├── convolutional.py
│   ├── viterbi.py  # Soft Viterbi decoder
│   ├── puncture.py # P1, P2, P3 patterns
│   ├── interleave.py
│   └── randomize.py
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

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=m17 --cov-report=html
```

## Specification Compliance

This library implements the [M17 Protocol Specification v2.0.3](https://spec.m17project.org/).

Key compliance points:
- CRC-16 polynomial 0x5935, init 0xFFFF
- Base-40 callsign alphabet: ` 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-/.`
- Golay(24,12) for LICH protection
- K=5 rate 1/2 convolutional code (G1=0x19, G2=0x17)
- 368-element QPP interleaver
- 46-byte randomizer sequence

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- [M17 Project](https://m17project.org/)
- [M17 Specification](https://spec.m17project.org/)
- [libm17](https://github.com/M17-Project/libm17) - C reference implementation
