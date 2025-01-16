import random
try:
    from .address import Address
    from .frames import *
except:
    from address import Address
    from frames import *


class M17_RFFramer:
    def __init__(self, *args, **kwargs):
        self.packet_count = 0
        self.LICH = initialLICH(*args,**kwargs)

    def makeLICH(self):
        return bytes(self.LICH)

    @classmethod
    def fromLICH(cls,data:bytes):
        d = initialLICH.dict_from_bytes( data )
        return cls( **d )

    def payload_stream( self, payload:bytes):
        LICH = self.LICH
        payloads = chunk( payload, regularFrame.payload_sz )
        pkts = []
        for p in payloads:
            if len(p) < regularFrame.payload_sz:
                p = p + b"\x00"*(regularFrame.payload_sz - len(p))
            pkt = regularFrame(LICH=LICH, frame_number=self.packet_count, payload=p)
            self.packet_count+=1
            if self.packet_count >= 2**16:
                self.packet_count = 0
            pkts.append(pkt)
        return pkts

class M17_IPFramer(M17_RFFramer):
    def __init__(self, *args, **kwargs):
        self.streamid = kwargs.pop("streamid", random.randint(0,2**16-1))
        super().__init__(*args,**kwargs)

    def payload_stream( self, payload:bytes):
        #only difference is which frame we use, ipFrame instead of regularFrame
        LICH = self.LICH
        payloads = chunk( payload, regularFrame.payload_sz )
        pkts = []
        for p in payloads:
            if len(p) < regularFrame.payload_sz:
                p = p + b"\x00"*(regularFrame.payload_sz - len(p))
            pkt = ipFrame(streamid=self.streamid, LICH=LICH, frame_number=self.packet_count, payload=p)
            self.packet_count+=1
            if self.packet_count >= 2**16:
                self.packet_count = 0
            pkts.append(pkt)
        return pkts

