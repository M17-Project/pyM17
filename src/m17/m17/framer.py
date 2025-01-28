"""
This module contains the M17 framer classes. These classes are responsible for taking a payload and
 turning it into a series of frames.
"""
import random


from m17.frames import LICHFrame, RegularFrame, IPFrame, chunk, M17Payload


class M17_RFFramer:
    def __init__(self, *args, **kwargs):
        self.packet_count = 0
        self.lich_frame = LICHFrame(*args, **kwargs)

    def payload_stream(self, payload: bytes):
        payloads = chunk(payload, RegularFrame.payload_sz)
        pkts = []
        for p in payloads:
            if len(p) < RegularFrame.payload_sz:
                p = p + b"\x00" * (RegularFrame.payload_sz - len(p))
            m17_payload = M17Payload(frame_number=self.packet_count, payload=p)
            pkt = RegularFrame(self.lich_frame, m17_payload)
            self.packet_count += 1
            if self.packet_count >= 2 ** 16:
                self.packet_count = 0
            pkts.append(pkt)
        return pkts


class M17_IPFramer(M17_RFFramer):
    def __init__(self, stream_id: int=None, *args, **kwargs):
        self.stream_id = stream_id or random.randint(0, 2 ** 16 - 1)
        super().__init__(*args, **kwargs)

    def payload_stream(self, payload: bytes):
        # only difference is which frame we use, ipFrame instead of regularFrame
        lich_frame = self.lich_frame
        payloads = chunk(payload, RegularFrame.payload_sz)
        pkts = []
        for p in payloads:
            if len(p) < RegularFrame.payload_sz:
                p = p + b"\x00" * (RegularFrame.payload_sz - len(p))
            pkt = IPFrame(
                stream_id=self.stream_id,
                full_lich=lich_frame,
                m17_payload=M17Payload(frame_number=self.packet_count, payload=p),
            )
            self.packet_count += 1
            if self.packet_count >= 2 ** 16:
                self.packet_count = 0
            pkts.append(pkt)
        return pkts
