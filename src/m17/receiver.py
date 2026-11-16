"""Receiver: finds frames in a stream of synchronized symbols and decodes them."""

from dataclasses import dataclass

from .frames import LSFFrame, PacketFrame, StreamFrame, decode_lsf, decode_packet, decode_stream
from .packet import Packet, PacketAssembler
from .phy import EOT_MARKER, SYM_PER_FRA, SYM_PER_SWD, SYNC_LSF, SYNC_PKT, SYNC_STR, distance, syncword_symbols


@dataclass
class EndOfTransmission:
    pass


Event = LSFFrame | StreamFrame | PacketFrame | Packet | EndOfTransmission

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
    :class:`~m17.packet.Packet` when the packet is complete.
    """

    def __init__(self, threshold: float = 2.0) -> None:
        self.threshold = threshold  # maximum syncword distance when searching
        self._buf: list[float] = []
        self._packet = PacketAssembler()
        self._in_eot = False
        self._expect = -1  # buffer index where the next frame should start, -1 if unknown

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
                self._in_eot = True
                self._expect = -1
                i += SYM_PER_SWD
                continue
            self._in_eot = False
            frame = decode(self._buf[i + SYM_PER_SWD : i + SYM_PER_FRA])
            events.append(frame)
            if isinstance(frame, PacketFrame):
                packet = self._packet.add(frame)
                if packet:
                    events.append(packet)
            i += SYM_PER_FRA
            self._expect = i
        del self._buf[:i]
        self._expect = self._expect - i if self._expect >= 0 else -1
        return events
