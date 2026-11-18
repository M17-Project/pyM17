"""Receiver: finds frames in a stream of synchronized symbols and decodes them."""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timezone

from .callsign import callsign_from_bytes
from .frames import LSFFrame, PacketFrame, StreamFrame, decode_lsf, decode_packet, decode_stream
from .lsf import ENCR_AES, ENCR_NONE, ENCR_SCRAMBLER, LSF, META_ECD, SIGNED, crc_ok
from .packet import Packet, PacketAssembler
from .phy import EOT_MARKER, SYM_PER_FRA, SYM_PER_SWD, SYNC_LSF, SYNC_PKT, SYNC_STR, distance, syncword_symbols
from .transmission import AUTH_FN, SIGNATURE_FN


@dataclass
class EndOfTransmission:
    pass


@dataclass
class Signature:
    """Result of a signed stream (specification 2.1).

    ``valid`` is None if it could not be checked: no public keys, frames missed, or
    reception started after FN 0. The other fields come from the Authentication Frame
    and are empty / None when it was not received.
    """

    valid: bool | None
    public_key: bytes | None  # the key it verified with
    signer: str = ""  # callsign of the station whose key signed the stream
    destination: str = ""  # DST as sent by the signer
    signed_at: datetime | None = None  # time of signing, UTC
    signer_is_originator: bool | None = None  # False: signed by another station than the one the LSF names

    def fresh(self, window: float = 300, now: datetime | None = None) -> bool | None:
        """Time of signing within ``window`` seconds of ``now`` (default: the system clock).

        The specification's default window is 300 s; only meaningful with a trusted clock.
        """
        if self.signed_at is None:
            return None
        now = now or datetime.now(timezone.utc)
        return abs((now - self.signed_at).total_seconds()) <= window


Event = LSFFrame | StreamFrame | PacketFrame | Packet | Signature | EndOfTransmission

_SYNCS = (
    (syncword_symbols(SYNC_LSF), decode_lsf),
    (syncword_symbols(SYNC_STR), decode_stream),
    (syncword_symbols(SYNC_PKT), decode_packet),
    (syncword_symbols(EOT_MARKER), None),
)


class Receiver:
    """Feed symbols (one per symbol, levels around -3, -1, +1, +3), get decoded events.

    >>> rx = Receiver()
    >>> for event in rx.feed(symbols):
    ...     print(event)

    Packet frames yield a :class:`~m17.frames.PacketFrame` each and a
    :class:`~m17.packet.Packet` when the packet is complete. With ``key`` (AES
    key or scrambler seed), encrypted stream payloads are decrypted. Signed
    streams yield a :class:`Signature`, checked against ``public_keys``.
    ``lsf`` holds the current LSF, also when it was rebuilt from the LICH.
    """

    def __init__(self, threshold: float = 2.0, key: bytes | None = None, public_keys: Iterable[bytes] = ()) -> None:
        self.threshold = threshold  # maximum syncword distance when searching
        self.key = key
        self.public_keys = list(public_keys)
        self.lsf: LSF | None = None
        self._buf: list[float] = []
        self._packet = PacketAssembler()
        self._in_eot = False
        self._expect = -1  # buffer index where the next frame should start, -1 if unknown
        self._new_stream()

    def _new_stream(self) -> None:
        self._lich: dict[int, bytes] = {}
        self._digest = None  # StreamHash from FN 0; None before FN 0 and after a missed frame
        self._next_fn = -1
        self._auth: bytes | None = None
        self._signature = bytearray(64)
        self._sig_parts = 0
        self._scrambler = None

    def feed(self, symbols) -> list[Event]:
        self._buf.extend(float(s) for s in symbols)
        events: list[Event] = []
        i = 0
        while i + SYM_PER_FRA <= len(self._buf):
            window = self._buf[i : i + SYM_PER_SWD]
            dist, decode = min(((distance(window, sync), dec) for sync, dec in _SYNCS), key=lambda d: d[0])
            # right after a frame, the next one is expected here: accept a weaker match
            limit = 2 * self.threshold if i == self._expect else self.threshold
            if dist >= limit:
                i += 1
                continue
            if decode is None:  # EOT marker: report once, skip the rest of it
                if not self._in_eot:
                    events.append(EndOfTransmission())
                    self._packet.reset()
                    self._new_stream()
                self._in_eot = True
                self._expect = -1
                i += SYM_PER_SWD
                continue
            self._in_eot = False
            frame = decode(self._buf[i + SYM_PER_SWD : i + SYM_PER_FRA])
            events.extend(self._handle(frame))
            i += SYM_PER_FRA
            self._expect = i
        del self._buf[:i]
        self._expect = self._expect - i if self._expect >= 0 else -1
        return events

    def _handle(self, frame) -> list[Event]:
        if isinstance(frame, LSFFrame):
            if frame.crc_ok:
                self.lsf = frame.lsf
                self._new_stream()
            return [frame]
        if isinstance(frame, PacketFrame):
            packet = self._packet.add(frame)
            return [frame, packet] if packet else [frame]
        return self._stream_frame(frame)

    def _stream_frame(self, frame: StreamFrame) -> list[Event]:
        from . import crypto

        if frame.lich_counter is not None:  # rebuild the LSF from the LICH if it was missed
            self._lich[frame.lich_counter] = frame.lich
            if len(self._lich) == 6:
                data = b"".join(self._lich[n] for n in range(6))
                if crc_ok(data):
                    self.lsf = LSF.from_bytes(data)
                self._lich.clear()
        lsf = self.lsf
        if lsf is None:
            return [frame]
        events: list[Event] = []
        if lsf.type & SIGNED and frame.fn >= SIGNATURE_FN:
            k = frame.fn - SIGNATURE_FN
            self._signature[16 * k : 16 * k + 16] = frame.payload
            self._sig_parts |= 1 << k
            events.append(frame)
            if k == 3:
                events.append(self._check_signature())
            return events
        if lsf.type & SIGNED:
            # the hash covers every frame from FN 0 with its payload as transmitted, then the
            # Authentication Frame, which is sent in the clear
            if frame.fn == AUTH_FN:
                if self._digest:
                    self._digest.update(frame.fn, frame.payload)
                self._auth = frame.payload
                return [frame]
            if frame.fn == 0:
                self._digest = crypto.StreamHash()
            elif frame.fn != self._next_fn:
                self._digest = None  # a frame is missing: the hash cannot be rebuilt
            if self._digest:
                self._digest.update(frame.fn, frame.payload)
            self._next_fn = frame.fn + 1
        encr = lsf.type & (3 << 3)
        if self.key is not None and encr == ENCR_AES:
            payload = crypto.aes_crypt(self.key, lsf.meta, frame.fn, frame.payload)
            frame = replace(frame, payload=payload, decrypted=True)
        elif self.key is not None and encr == ENCR_SCRAMBLER:
            if self._scrambler is None:
                self._scrambler = crypto.Scrambler(self.key)
            frame = replace(frame, payload=self._scrambler.crypt(frame.fn, frame.payload), decrypted=True)
        events.append(frame)
        return events

    def _check_signature(self) -> Signature:
        from . import crypto

        info = {}
        if self._auth is not None:
            signer, destination, t = crypto.parse_auth(self._auth)
            lsf = self.lsf
            ecd = (lsf.type & (3 << 3)) == ENCR_NONE and (lsf.type & (3 << 5)) == META_ECD
            originator = callsign_from_bytes(lsf.meta[0:6]) if ecd else lsf.src  # ECD Callsign Field 1, else SRC
            info = dict(
                signer=signer,
                destination=destination,
                signed_at=datetime.fromtimestamp(t, timezone.utc),
                signer_is_originator=signer == originator,
            )
        if self._sig_parts != 0xF or self._digest is None or self._auth is None or not self.public_keys:
            return Signature(None, None, **info)
        digest = self._digest.digest
        for key in self.public_keys:
            if crypto.verify(key, digest, bytes(self._signature)):
                return Signature(True, key, **info)
        return Signature(False, None, **info)
