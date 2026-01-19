# Changelog

All notable changes to pyM17 will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security

- **Fixed arbitrary code execution vulnerability** in `misc.py` and `apps.py`
  - `vars()[sys.argv[1]](*sys.argv[2:])` allowed running any function from CLI
  - Replaced with explicit whitelist of allowed CLI commands

### Fixed

- **Fixed null pointer crash in `blocks.py:56`**
  - Added null check for `occasional` callback parameter

- **Fixed bare except clause in `blocks.py:225`**
  - Changed to `except Exception:` to allow graceful shutdown

- **Fixed `any()` misuse in `address.py:114`**
  - Removed incorrect `any()` wrapper around boolean return

### Added

- **Comprehensive test suite** - 348 tests, coverage improved from 35% to 43%
  - `test_viterbi.py` - Viterbi decoder tests (100% coverage)
  - `test_convolutional.py` - Convolutional encoder tests (98% coverage)
  - `test_puncture.py` - Puncture pattern tests (100% coverage)
  - `test_randomize.py` - Randomizer tests (100% coverage)
  - `test_stream.py` - Stream frame tests (98% coverage)
  - `test_lich.py` - LICH handling tests (98% coverage)
  - `test_blocks.py` - Audio processing blocks tests
  - `test_integration.py` - Full FEC pipeline and frame roundtrip tests

---

## [0.1.2] - 2026-01-18

### Added

#### M17 v3.0.0 Specification Support

- **TYPE Field v3.0.0** (`types.py`)
  - Complete rewrite of TYPE field for v3.0.0 specification
  - New enums: `M17Payload`, `M17Encryption`, `M17Meta`, `M17Version`
  - `TypeFieldV3` NamedTuple for parsed v3.0.0 fields
  - `build_type_field_v3()` / `parse_type_field_v3()` functions
  - `detect_type_field_version()` for automatic v2/v3 detection
  - v3.0.0 PAYLOAD types: DATA_ONLY, VOICE_3200, VOICE_1600_DATA, PACKET
  - v3.0.0 ENCRYPTION types: 8/16/24-bit scrambler, 128/192/256-bit AES
  - v3.0.0 META types: GNSS, Extended Callsign, Text, AES IV
  - Digital signature support (SIGNED flag)
  - Expanded CAN (Channel Access Number) to 4 bits

- **Multi-Block Text META** (`lsf.py`)
  - `MetaText` class for TEXT_DATA META type
  - Support for 1-15 blocks (up to 195 bytes of UTF-8 text)
  - `encode_multi_block()` / `decode_multi_block()` methods
  - Control byte format: [BLOCK_COUNT:4][BLOCK_INDEX:4]

- **AES IV META** (`lsf.py`)
  - `MetaAesIV` class for AES initialization vector
  - 14-byte IV field for AES encryption

- **TLE Packet Type** (`packet.py`, `constants.py`)
  - `TLEPacket` class for satellite orbital data
  - Standard 3-line TLE format (name + line1 + line2)
  - Protocol identifier 0x07
  - CRC verification on parse
  - `to_packet_frame()` / `from_packet_frame()` conversion

- **Packet Protocol Identifiers** (`constants.py`)
  - `PACKET_PROTOCOL_RAW` (0x00)
  - `PACKET_PROTOCOL_AX25` (0x01)
  - `PACKET_PROTOCOL_APRS` (0x02)
  - `PACKET_PROTOCOL_6LOWPAN` (0x03)
  - `PACKET_PROTOCOL_IPV4` (0x04)
  - `PACKET_PROTOCOL_SMS` (0x05)
  - `PACKET_PROTOCOL_WINLINK` (0x06)
  - `PACKET_PROTOCOL_TLE` (0x07)

- **LSF v3.0.0 Methods** (`lsf.py`)
  - `set_type_v3()` - Set TYPE field using v3.0.0 format
  - `set_text_meta()` / `get_text_meta()` - Text META convenience methods
  - `set_aes_iv_meta()` / `get_aes_iv_meta()` - AES IV META methods
  - `create_text_message_frames()` - Factory for multi-frame text messages
  - Properties: `version`, `payload_type`, `encryption_v3`, `is_signed`, `meta_type`, `can_v3`

- **Version Detection**
  - Automatic detection via PAYLOAD field (0x0 = v2.0.3, non-zero = v3.0.0)
  - Backward compatible: v2.0.3 frames continue to work unchanged

### Changed

- Legacy v2.0.3 TYPE field enums marked as DEPRECATED (still functional)
- Test suite expanded from 120 to 156 tests

---

## [0.1.1] - 2026-01-18

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
The codebase has been completely modernized for v0.1.1.

---

## Migration Guide

### From v0.x to v0.1.1

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
