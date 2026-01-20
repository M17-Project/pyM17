# TODO

Remaining work items for pyM17 development.

## Critical

### Security

- [x] **Fix arbitrary code execution in `misc.py:131` and `apps.py:344`**
  ```python
  vars()[sys.argv[1]](*sys.argv[2:])  # Allows executing any function from CLI
  ```
  - Replaced with explicit whitelist of allowed CLI commands

## High Priority

### Bug Fixes

- [x] **Fix null pointer crash in `blocks.py:56`**
  - `occasional(sock)` called without checking if `occasional` is None
  - Added `if occasional:` guard before the call

- [x] **Fix bare except clause in `blocks.py:225`**
  - Catches `KeyboardInterrupt`/`SystemExit`, preventing graceful shutdown
  - Changed `except:` to `except Exception:`

- [x] **Fix `any()` misuse in `address.py:114`** (legacy module)
  - `any(self.is_brandmeister_tg())` - `any()` on a boolean, not iterable
  - Changed to `return self.is_brandmeister_tg()`

### Testing & Quality

- [ ] **Increase test coverage** - Current: 56%, Target: 80%+
  - [x] Add tests for `m17/codec/viterbi.py` (now 100% coverage)
  - [x] Add tests for `m17/codec/puncture.py` (now 100% coverage)
  - [x] Add tests for `m17/codec/randomize.py` (now 100% coverage)
  - [x] Add tests for `m17/codec/convolutional.py` (now 98% coverage)
  - [x] Add tests for `m17/net/` modules (2026-01-20)
    - `net/__init__.py` - 100% coverage
    - `net/reflector.py` - 87% coverage (86 tests)
    - `net/p2p.py` - 75% coverage
    - `net/client.py` - 89% coverage
    - `net/dht.py` - 46% coverage (kademlia tests skipped if not installed)
  - [x] Add tests for `m17/frames/packet.py` (78% coverage) - TLE tests added
  - [x] Add tests for `m17/frames/stream.py` (now 98% coverage)
  - [x] Add tests for `m17/frames/lich.py` (now 98% coverage)

- [x] **Run mypy strict mode** - Fix all type errors
  ```bash
  mypy m17/ --strict
  ```
  - Enabled `strict = true` in pyproject.toml
  - Added type annotations to ~70+ functions across blocks.py, misc.py, framer.py, address.py, network.py, apps.py
  - Configured per-module overrides for optional modules (net/*, audio/*) and complex typing patterns
  - Reduced errors from 304 to 0

- [x] **Integration tests**
  - [x] Full FEC encode/decode roundtrip test
  - [x] Frame serialization/deserialization with actual M17 data
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

- [x] **Remove legacy modules** (added deprecation warnings - 2026-01-19)
  - [x] `m17/frames.py` - Old frame definitions (replaced by `m17/frames/`) - added deprecation warning
  - [x] `m17/network.py` - Old network code (replaced by `m17/net/`) - added deprecation warning
  - [x] `m17/framer.py` - Unused framer module - added deprecation warning
  - [x] `m17/voipsim.py` - VoIP simulation - added deprecation warning
  - [x] `m17/sanity_check.py` - Sanity check script - added deprecation warning

- [x] **Consolidate address modules** (2026-01-19)
  - [x] Deprecate `m17/address.py` in favor of `m17/core/address.py` - added deprecation warning
  - [x] Add deprecation warnings to old imports
  - [x] Fix type hints in legacy `address.py:51` - verified already correct (Union[int, bytes])

- [x] **Remove debug code** (2026-01-19)
  - [x] Audit all modules for `print()` statements - replaced with logging in network.py, blocks.py, apps.py
  - [x] Replace with proper `logging` module usage
  - [x] Remove hardcoded `logging.basicConfig(level=DEBUG)` in `network.py:18` - replaced with logger

- [x] **Complete or remove stub functions** (2026-01-19)
  - [x] `blocks.py:238` - `throttle()` - implemented rate-limiting function
  - [x] `apps.py:37-45` - `m17_parrot()`, `m17_mirror()` - added proper NotImplementedError with docs
  - [x] `apps.py:108` - Reflector name parsing - added descriptive NotImplementedError message
  - [x] `network.py:65,68` - Packet frame and unknown message handling - improved error messages

- [x] **Fix silent failures** (2026-01-19)
  - [x] `frames/packet.py:276-280` - Invalid TLE data - now logs warnings for non-standard lengths
  - [x] `__init__.py:85-106` - ImportErrors - now logged at debug level

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

- [x] **GitHub Actions workflow** (2026-01-20)
  - [x] pytest on push/PR
  - [x] mypy type checking
  - [x] ruff linting and format checking
  - [x] Coverage reporting to Codecov
  - [x] Automated PyPI publishing on release (already existed)
  - Added `.github/workflows/ci.yml` with test, lint, and type-check jobs
  - Added `codecov.yml` for coverage configuration

- [x] **Pre-commit hooks** (2026-01-20)
  - [x] Add `.pre-commit-config.yaml`
  - [x] Configure ruff (lint + format), mypy, poetry-check
  - [x] Add pre-commit to dev dependencies
  - [x] Tune ruff configuration for codebase
    - Per-file ignores for legacy deprecated modules
    - Relaxed docstring rules for test files
    - Compatible docstring style settings (D211/D212)
  - Hooks: trailing-whitespace, end-of-file-fixer, check-yaml, check-toml, debug-statements

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

2. ~~**Network module debug code**~~ - **FIXED (2026-01-19)**: All debug prints
   replaced with proper logging. Hardcoded `logging.basicConfig` removed.

3. **Audio module dependencies** - pycodec2 installation can be problematic
   on some platforms. Need to document build requirements.

4. **Test flakiness** - Some tests use random data (`example_bytes()`). Consider
   using fixed seeds for reproducibility.

5. **M17 v3.0.0 spec is WIP** - The v3.0.0 specification is still being finalized.
   Implementation may need updates when the spec is released. Track changes at
   the M17_spec repository dev branch.

6. **Code style inconsistencies** - `while 1:` instead of `while True:` in
   `blocks.py`. `raise (NotImplementedError)` with unnecessary parentheses
   throughout several modules.

7. **LSF/LICH code duplication** - `frames/lsf.py` and `frames/lich.py` both
   represent the same 28-byte structure with conversion methods between them.
   Creates maintenance burden.

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

- [x] **mypy strict mode enabled** - Full type safety with 0 errors

### Code Cleanup (2026-01-19)

- [x] **Fixed silent failures** - TLE validation and import errors now logged
- [x] **Replaced debug prints with logging** - network.py, blocks.py, apps.py
- [x] **Implemented throttle() function** - Rate-limiting for queue processing
- [x] **Improved stub functions** - Added docstrings and descriptive errors
- [x] **Added deprecation warnings** - All legacy modules now warn on import
- [x] **Removed default hostname constants** - No hardcoded hostnames; users must provide explicit configuration
  - Removed `DEFAULT_PRIMARY_HOST`, `DEFAULT_DHT_BOOTSTRAP_HOSTS`, `DEFAULT_REFLECTOR_DOMAIN`, `DEFAULT_TEST_HOST`
  - `DHTConfig.bootstrap_nodes` and `P2PManager.primaries` now required parameters
  - `get_reflector_host()` and `m17ref_name2host()` now require explicit domain

---

Last updated: 2026-01-20
