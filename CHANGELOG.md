# Changelog

All notable changes to pyM17 will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-18

### Added

#### Core Module (`m17/core/`)
- **CRC-16 Implementation** (`crc.py`)
  - M17-compliant CRC-16 with polynomial 0x5935, init 0xFFFF
  - Test vectors: empty=0xFFFF, "A"=0x206E, "123456789"=0x772B
  - Functions: `crc_m17()`, `crc_m17_bytes()`, `verify_crc()`

- **TYPE Field Enums** (`types.py`)
  - `M17Type` - Stream/Packet type
  - `M17DataType` - Reserved/Data/Voice/Voice+Data
  - `M17EncryptionType` - None/Scrambler/AES256
  - `M17EncryptionSubType` - Scrambler/AES subtypes
  - `M17MetaType` - Text/GNSS/ExtCallsign/Reserved

- **Enhanced Address Module** (`address.py`)
  - Dataclass-based `Address` with full type hints
  - Hash-address support (`#` prefix, range 40^9 to 40^9+40^8)
  - Broadcast address support (`@ALL` = 0xFFFFFFFFFFFF)
  - Properties: `is_broadcast`, `is_hash_address`, `is_regular`
  - Equality comparison with str, int, bytes
  - Immutable and hashable (usable in sets/dicts)

- **Constants** (`constants.py`)
  - Sync words: LSF (0x55F7), Stream (0xFF5D), Packet (0x75FF), BERT (0xDF55)
  - EOT marker (0x555D)
  - Frame sizes and magic number

#### Frames Module (`m17/frames/`)
- **Link Setup Frame** (`lsf.py`)
  - Full LSF implementation with CRC
  - META field variants:
    - `MetaPosition` - GNSS position (v2.0.0 metric format)
    - `MetaExtendedCallsign` - Extended callsign data
    - `MetaNonce` - Encryption nonce with timestamp
  - Helper methods: `set_position_meta()`, `get_position_meta()`, etc.
  - LICH chunking for stream transmission

- **Stream Frames** (`stream.py`)
  - `M17Payload` - Frame number + 16-byte payload + CRC
  - `StreamFrame` - LICH chunk + payload for RF transmission
  - EOT flag handling

- **Packet Frames** (`packet.py`)
  - `PacketFrame` - For bulk data transfer
  - `PacketChunk` - Individual packet segments

- **IP Frames** (`ip.py`)
  - `IPFrame` - M17-over-IP format (54 bytes)
  - Magic number validation
  - Factory method `IPFrame.create()`

- **LICH Handling** (`lich.py`)
  - `LICHFrame` - Legacy-compatible LICH representation
  - `LICHChunk` - Single 6-byte chunk
  - `LICHCollector` - Reconstructs LSF from stream chunks

#### Codec Module (`m17/codec/`)
- **Golay(24,12)** (`golay.py`)
  - `golay24_encode()` - 12-bit to 24-bit encoding
  - `golay24_decode()` - Hard-decision decoding (corrects up to 3 errors)
  - `golay24_sdecode()` - Soft-decision decoding
  - `encode_lich()` / `decode_lich()` - 48-bit to 96-bit LICH encoding

- **Convolutional Encoder** (`convolutional.py`)
  - K=5 constraint length, rate 1/2
  - Polynomials: G1=0x19, G2=0x17
  - Functions: `convolutional_encode()`, `conv_encode_lsf()`, `conv_encode_stream()`

- **Puncture Patterns** (`puncture.py`)
  - P1 (61-bit) - LSF and BERT
  - P2 (12-bit) - Stream frames
  - P3 (8-bit) - Packet frames
  - Functions: `puncture()`, `depuncture()`

- **Viterbi Decoder** (`viterbi.py`)
  - 16-state trellis (K-1=4 bits)
  - Soft-decision decoding
  - Punctured decoding support
  - Functions: `viterbi_decode()`, `viterbi_decode_punctured()`

- **Interleaver** (`interleave.py`)
  - 368-element QPP interleaver sequence
  - Self-inverse (involution) property
  - Functions: `interleave()`, `deinterleave()`

- **Randomizer** (`randomize.py`)
  - 46-byte decorrelation sequence
  - Functions: `randomize()`, `derandomize()`

#### Networking Module (`m17/net/`)
- **Reflector Client** (`reflector.py`)
  - n7tae protocol implementation
  - `M17ReflectorClient` - Async reflector connection
  - Connection, ping, and stream handling

- **DHT Node** (`dht.py`)
  - Kademlia-based distributed routing
  - `M17DHTNode` - DHT node with callsign registration

- **P2P Connections** (`p2p.py`)
  - `P2PConnection` - Direct peer connections
  - `P2PManager` - NAT traversal with UDP hole punching

- **High-Level Client** (`client.py`)
  - `M17NetworkClient` - Unified async client
  - `M17ClientConfig` - Configuration dataclass
  - `StreamContext` - Context manager for streams

#### Audio Module (`m17/audio/`)
- **Codec2 Wrapper** (`codec2.py`)
  - `Codec2Wrapper` - pycodec2 integration
  - Mode support (3200, 1600, etc.)

- **Audio Blocks** (`blocks.py`)
  - Processing chain components

### Changed

- **Project Structure**
  - Reorganized into modular subpackages (core/, frames/, codec/, net/, audio/)
  - All modules use modern Python features (dataclasses, type hints)
  - Pydantic v2 for validation where appropriate

- **Address Module**
  - Converted from simple functions to dataclass-based `Address`
  - Added backward-compatible static methods `Address.encode()`, `Address.decode()`

- **Frame Classes**
  - `RegularFrame` renamed to `StreamFrame` (alias preserved for compatibility)
  - `IPFrame` now uses `lsf` parameter instead of `full_lich`
  - All frames use `to_bytes()` / `from_bytes()` pattern

- **Dependencies**
  - Updated to Python 3.12+
  - numpy >= 2.2
  - pydantic >= 2.9
  - Optional extras for audio and DHT features

### Deprecated

- Legacy `m17.address` module (use `m17.core.address`)
- Legacy `m17.frames` module (use `m17.frames.*` submodules)
- `RegularFrame` class name (use `StreamFrame`)
- `IPFrame(full_lich=...)` parameter (use `lsf=...`)

### Removed

- Debug `pdb.set_trace()` calls from network module
- Deprecated code marked for removal

### Fixed

- CRC calculation now matches M17 specification exactly
- Address encoding handles all edge cases (hash, broadcast, spaces)
- Frame serialization byte order corrected

### Security

- No known security issues

## [0.x.x] - Previous Versions

Previous versions were marked as DEPRECATED and are not documented here.
The codebase has been completely modernized for v1.0.0.

---

## Migration Guide

### From v0.x to v1.0.0

#### Import Changes

```python
# Old
from m17.address import Address
from m17.frames import RegularFrame, IPFrame

# New
from m17.core.address import Address
from m17.frames import StreamFrame, IPFrame
# Or use the compatibility imports:
from m17 import Address, StreamFrame, IPFrame
```

#### Frame Construction

```python
# Old
frame = IPFrame(full_lich=lich, m17_payload=payload)

# New
frame = IPFrame(lsf=lsf, payload=payload)
# Or use the factory method:
frame = IPFrame.create(dst="W2FBI", src="N0CALL", payload=data)
```

#### Address Creation

```python
# Old (still works)
addr = Address(callsign="W2FBI")

# New features
addr = Address(numeric=0x161AE1F)  # From numeric
addr = Address(addr=bytes_data)    # From bytes
print(addr.is_broadcast)           # New properties
```
