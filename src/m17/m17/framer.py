"""M17 Framer Classes (Legacy Module)

This module contains the M17 framer classes. These classes are responsible for
taking a payload and turning it into a series of frames.

.. deprecated:: 0.1.1
    This module is deprecated and will be removed in v1.0.
    Consider using the frame classes directly from :mod:`m17.frames`.
"""
from __future__ import annotations

import random
import warnings
from typing import Any, Optional

from m17.frames import IPFrame, LICHFrame, M17Payload, StreamFrame
from m17.misc import chunk

# Emit deprecation warning on module import
warnings.warn(
    "m17.framer is deprecated and will be removed in v1.0. "
    "Consider using frame classes directly from m17.frames.",
    DeprecationWarning,
    stacklevel=2,
)


class M17RFFramer:
    """M17 RF Framer"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.packet_count = 0
        self.lich_frame = LICHFrame(*args, **kwargs)

    def payload_stream(self, payload: bytes) -> list[StreamFrame]:
        """Take a payload and turn it into a series of frames"""
        payloads = chunk(payload, StreamFrame.payload_sz)
        pkts: list[StreamFrame] = []
        lich_chunks = self.lich_frame.chunks(6)
        for p in payloads:
            if len(p) < StreamFrame.payload_sz:
                p = p + b"\x00" * (StreamFrame.payload_sz - len(p))
            m17_payload = M17Payload(frame_number=self.packet_count, payload=p)
            # Get LICH chunk for this frame (5 chunks rotate)
            lich_chunk_idx = self.packet_count % 5
            lich_chunk = (
                lich_chunks[lich_chunk_idx] if lich_chunk_idx < len(lich_chunks) else bytes(6)
            )
            pkt = StreamFrame(lich_chunk=lich_chunk, payload=m17_payload)
            self.packet_count += 1
            if self.packet_count >= 2**16:
                self.packet_count = 0
            pkts.append(pkt)
        return pkts


class M17IPFramer(M17RFFramer):
    """M17 IP Frame Framer"""

    def __init__(self, stream_id: Optional[int] = None, *args: Any, **kwargs: Any) -> None:
        self.stream_id = stream_id or random.randint(0, 2**16 - 1)
        super().__init__(*args, **kwargs)

    def payload_stream(self, payload: bytes) -> list[IPFrame]:  # type: ignore[override]
        """Take a payload and turn it into a series of frames"""
        # only difference is which frame we use, ipFrame instead of regularFrame
        lich_frame = self.lich_frame
        payloads = chunk(payload, StreamFrame.payload_sz)
        pkts: list[IPFrame] = []
        for p in payloads:
            if len(p) < StreamFrame.payload_sz:
                p = p + b"\x00" * (StreamFrame.payload_sz - len(p))
            m17_payload = M17Payload(frame_number=self.packet_count, payload=p)
            pkt = IPFrame.create(
                stream_id=self.stream_id,
                dst=lich_frame.dst,
                src=lich_frame.src,
                stream_type=lich_frame.stream_type,
                nonce=lich_frame.nonce,
                frame_number=m17_payload.frame_number,
                payload=m17_payload.payload,
            )
            self.packet_count += 1
            if self.packet_count >= 2**16:
                self.packet_count = 0
            pkts.append(pkt)
        return pkts
