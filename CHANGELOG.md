# Changelog

## 0.2.0

A rewrite of the package, ported from libm17 1.4.3 and gr-m17.

- Decoding of stream and packet frames works: the old Viterbi stage rejected the odd
  depunctured length of P2 and P3 frames, and decode_lsf() returned the flush byte first.
- Bit-exact with libm17, checked against generated reference values, down to the Viterbi
  metric of noisy frames. Packet transmissions are identical to m17-packet-encode.
- New API: frames, packets, whole transmissions, a receiver with LICH reassembly and
  decryption, AES/scrambler encryption, ECDSA stream signatures, an mrefd reflector client
  and a command line tool.
- No required dependencies. cryptography (AES, ECDSA) and numpy (RRC filtering) are optional.
- Removed: the DHT, P2P and audio modules, the legacy modules and the M17 specification
  3.0 draft features.

## 0.1.x

The original implementation by Michael McGinty W2FBI and Luke Stamm WE3DZ, see the git history.
