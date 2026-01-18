# TODO

Remaining work items for pyM17 development.

## High Priority

### Testing & Quality

- [ ] **Increase test coverage** - Current: 35%, Target: 80%+
  - [ ] Add tests for `m17/codec/viterbi.py` (21% coverage)
  - [ ] Add tests for `m17/codec/puncture.py` (28% coverage)
  - [ ] Add tests for `m17/codec/randomize.py` (34% coverage)
  - [ ] Add tests for `m17/codec/convolutional.py` (20% coverage)
  - [ ] Add tests for `m17/net/` modules (0% coverage)
  - [x] Add tests for `m17/frames/packet.py` (78% coverage) - TLE tests added

- [ ] **Run mypy strict mode** - Fix all type errors
  ```bash
  mypy m17/ --strict
  ```

- [ ] **Integration tests**
  - [ ] Full FEC encode/decode roundtrip test
  - [ ] Frame serialization/deserialization with actual M17 data
  - [ ] Network client connection tests (with mocked server)

### Interoperability

- [ ] **libm17 compatibility testing**
  - [ ] Generate test vectors in Python, verify with libm17
  - [ ] Generate test vectors in libm17, verify in Python
  - [ ] Document any differences

- [ ] **Real-world testing**
  - [ ] Connect to live M17 reflector
  - [ ] Send/receive actual voice streams
  - [ ] Test with M17 hardware (Module17, etc.)

## Medium Priority

### Code Cleanup

- [ ] **Remove legacy modules**
  - [ ] `m17/frames.py` - Old frame definitions (replaced by `m17/frames/`)
  - [ ] `m17/network.py` - Old network code (replaced by `m17/net/`)
  - [ ] `m17/framer.py` - Unused framer module
  - [ ] `m17/voipsim.py` - VoIP simulation (needs review)
  - [ ] `m17/sanity_check.py` - Sanity check script

- [ ] **Consolidate address modules**
  - [ ] Deprecate `m17/address.py` in favor of `m17/core/address.py`
  - [ ] Add deprecation warnings to old imports

- [ ] **Remove debug code**
  - [ ] Audit all modules for `print()` statements
  - [ ] Replace with proper `logging` module usage

### Documentation

- [ ] **API documentation**
  - [ ] Set up Sphinx documentation
  - [ ] Generate API reference from docstrings
  - [ ] Add usage examples for each module

- [ ] **Architecture documentation**
  - [ ] Document FEC pipeline (encode/decode flow)
  - [ ] Document frame structure diagrams
  - [ ] Document network protocol flow

### Features

- [ ] **Encryption support**
  - [ ] Implement scrambler encryption
  - [ ] Implement AES-256 encryption
  - [ ] Add key management utilities

- [ ] **BERT mode support**
  - [ ] Implement BERT frame generation
  - [ ] Implement BERT frame reception/analysis
  - [ ] Add BER calculation utilities

- [ ] **Digital signatures (v3.0.0)**
  - [ ] Implement ECDSA secp256r1 signing
  - [ ] Implement signature verification
  - [ ] Add key generation utilities

## Low Priority

### Performance

- [ ] **Optimize Viterbi decoder**
  - [ ] Profile current implementation
  - [ ] Consider Cython or numba for hot paths
  - [ ] Benchmark against libm17

- [ ] **Optimize interleaver**
  - [ ] Use numpy operations instead of list comprehensions
  - [ ] Pre-compute inverse lookup table

### CI/CD

- [ ] **GitHub Actions workflow**
  - [ ] pytest on push/PR
  - [ ] mypy type checking
  - [ ] ruff/flake8 linting
  - [ ] Coverage reporting to Codecov
  - [ ] Automated PyPI publishing on release

- [ ] **Pre-commit hooks**
  - [ ] Add `.pre-commit-config.yaml`
  - [ ] Configure ruff, mypy, pytest

### Future Versions

- [ ] **v0.2.0 - Enhanced networking**
  - [ ] WebSocket transport option
  - [ ] MQTT integration
  - [ ] REST API for remote control

- [ ] **v0.3.0 - RF support**
  - [ ] SDR integration (RTL-SDR, HackRF)
  - [ ] Demodulator implementation
  - [ ] Modulator implementation

- [ ] **v1.0.0 - Breaking changes**
  - [ ] Remove all deprecated code
  - [ ] Drop Python 3.11 support
  - [ ] Async-first API

## Known Issues

1. **Viterbi decoder performance** - Current pure Python implementation is slow
   for real-time decoding. Consider using numpy vectorization or Cython.

2. **Network module debug code** - Some debug prints may still exist in
   `m17/net/reflector.py`. Need full audit.

3. **Audio module dependencies** - pycodec2 installation can be problematic
   on some platforms. Need to document build requirements.

4. **Test flakiness** - Some tests use random data (`example_bytes()`). Consider
   using fixed seeds for reproducibility.

5. **M17 v3.0.0 spec is WIP** - The v3.0.0 specification is still being finalized.
   Implementation may need updates when the spec is released. Track changes at
   the M17_spec repository dev branch.

## Completed

- [x] Core protocol implementation (CRC, Address, Types)
- [x] Frame layer modernization (LSF, Stream, Packet, IP, LICH)
- [x] FEC codec implementation (Golay, Conv, Viterbi, Interleave, Randomize)
- [x] Network module structure (Reflector, DHT, P2P, Client)
- [x] Audio module structure (Codec2, Blocks)
- [x] Test suite foundation (120 tests passing)
- [x] Updated pyproject.toml with extras
- [x] README.md update
- [x] CHANGELOG.md creation

### v0.1.2 - M17 v3.0.0 Support

- [x] TYPE field v3.0.0 redesign (PAYLOAD, ENCRYPTION, SIGNED, META, CAN)
- [x] Automatic version detection (v2.0.3 vs v3.0.0)
- [x] Multi-block text META (up to 195 bytes over 15 frames)
- [x] AES IV META field support
- [x] TLE packet type for satellite orbital data
- [x] Packet protocol identifiers (RAW, AX.25, APRS, 6LoWPAN, IPv4, SMS, Winlink, TLE)
- [x] Expanded encryption options (8/16/24-bit scrambler, 128/192/256-bit AES)
- [x] v3.0.0 test suite (36 tests, total now 156 tests)
- [x] Backward compatibility with v2.0.3 frames

---

Last updated: 2026-01-18
