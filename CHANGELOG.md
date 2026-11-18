# Changelog

## 0.3.0

Stream signatures follow the M17 Specification 2.1.0 (M17_spec issue #182). Signatures of
0.2.0 and older (XOR digest) do not verify any more, and the other way round.

- The stream hash is SHA-256 over the tag "M17-SIG-v2" and every frame's FN and payload as
  transmitted, from FN 0, ending with the new Authentication Frame (FN 0x7FFB: signer
  callsign, destination, time of signing). It needs no new dependency (hashlib).
- crypto: `StreamHash` replaces `StreamDigest`; `auth_payload()` and `parse_auth()`;
  `sign()` and `verify()` take the 32-byte hash and raise ValueError for other lengths.
- encode_stream() sends the Authentication Frame (the LSF's SRC as the signer) and takes an
  optional `timestamp`.
- Receiver: the `Signature` event carries `signer`, `destination`, `signed_at` and
  `signer_is_originator` (Extended Callsign Data field 1, else SRC), and has `fresh()` (the
  specification's 300 s window). A missed frame or a late join now gives `valid=None` (not
  checkable) where it gave an invalid signature.
- The crypto test vectors come from gr-m17 1.1.0's stream hash (lib/m17sig.c), and the
  specification's test vector is checked.

## 0.2.0

A rewrite of the package, ported from libm17 1.4.3 and gr-m17.

- Decoding of stream and packet frames works: the old Viterbi stage rejected the odd
  depunctured length of P2 and P3 frames, and decode_lsf() returned the flush byte first.
- Bit-exact with libm17, checked against generated reference values, down to the Viterbi
  metric of noisy frames. Packet transmissions are identical to m17-packet-encode.
- New API: frames, packets, whole transmissions, a receiver with LICH reassembly and
  decryption, AES/scrambler encryption, ECDSA stream signatures, a reflector client following
  the M17 Internet Interface specification (M17_inet) and a command line tool.
- No required dependencies. cryptography (AES, ECDSA) and numpy (RRC filtering) are optional.
- Removed: the DHT, P2P and audio modules, the legacy modules and the M17 specification
  3.0 draft features.

## 0.1.x

The original implementation by Michael McGinty W2FBI and Luke Stamm WE3DZ, see the git history.
