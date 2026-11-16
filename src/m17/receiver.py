"""Receiver: finds frames in a stream of synchronized symbols and decodes them."""

from collections.abc import Iterable
from dataclasses import dataclass, replace

from .frames import LSFFrame, PacketFrame, StreamFrame, decode_lsf, decode_packet, decode_stream
from .lsf import ENCR_AES, ENCR_SCRAMBLER, LSF, SIGNED, crc_ok
from .packet import Packet, PacketAssembler
from .phy import EOT_MARKER, SYM_PER_FRA, SYM_PER_SWD, SYNC_LSF, SYNC_PKT, SYNC_STR, distance, syncword_symbols
from .transmission import SIGNATURE_FN


@dataclass
class EndOfTransmission:
    pass


@dataclass
class Signature:
    """Result of a signed stream: ``valid`` is None if it could not be checked."""

    valid: bool | None
    public_key: bytes | None  # the key it verified with


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
        from .crypto import StreamDigest

        self._lich: dict[int, bytes] = {}
        self._digest = StreamDigest()
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
        self._digest.update(frame.payload)
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

        if self._sig_parts != 0xF or not self.public_keys:
            return Signature(None, None)
        for key in self.public_keys:
            if crypto.verify(key, self._digest.digest, bytes(self._signature)):
                return Signature(True, key)
        return Signature(False, None)
