"""
M17 frames (Legacy Module)

.. deprecated:: 1.0.0
    This module is deprecated. Use the :mod:`m17.frames` package instead.

    Example migration::

        # Old imports (deprecated)
        from m17.frames import M17Payload, LICHFrame, IPFrame

        # New imports (preferred)
        from m17.frames import M17Payload, LICHFrame, IPFrame
        # (These are re-exported from m17.frames package for compatibility)
"""
import struct
import warnings
from typing import Union

from m17 import const as m17_const
from m17.address import Address
from m17.misc import print_hex, chunk

# Emit deprecation warning on module import
warnings.warn(
    "Direct import from m17.frames (the legacy module) is deprecated. "
    "The m17/frames/ package provides the same classes with modern implementations.",
    DeprecationWarning,
    stacklevel=2,
)

M17PayloadLayout = struct.Struct(m17_const.M17_PAYLOAD_LAYOUT_STRUCT)


class M17Payload:
    """
    16b  Frame number counter
    128b payload
    16b  CRC-16 chksum
    """
    sz = M17PayloadLayout.size

    def __init__(self, frame_number: int, payload: bytes, crc: int = 0):
        self.frame_number = frame_number
        self.payload = payload
        self.crc = crc

    def __eq__(self, other):
        return bytes(self) == bytes(other)

    def __str__(self):
        return f"M17[{self.frame_number}]: {print_hex(self.payload)}"

    def __bytes__(self):
        return self.pack()

    def get_pack_values(self):
        return [
            self.frame_number,
            *self.payload,
            self.crc
        ]

    def pack(self) -> bytes:
        """
        returns the M17Payload as a bytes object
        """
        return M17PayloadLayout.pack(*self.get_pack_values())

    @classmethod
    def unpack(cls, data: bytes) -> "M17Payload":
        """
        Convert bytes to M17Payload
        """
        frame_number, payload, crc = M17PayloadLayout.unpack(data)
        return cls(frame_number, payload, crc)

    @classmethod
    def from_bytes(cls, data: bytes) -> "M17Payload":
        """
        Convert bytes to M17Payload
        """
        return M17Payload.unpack(data)

    @staticmethod
    def dict_from_bytes(data: bytes) -> dict:
        """
        Convert bytes to dict
        """
        frame_number, payload, crc = M17PayloadLayout.unpack(data)
        return {
            "frame_number": frame_number,
            "payload": payload,
            "crc": crc
        }


LICHFrameLayout = struct.Struct(m17_const.LICH_FRAME_LAYOUT_STRUCT)
LICHFrameCRCLayout = struct.Struct(m17_const.LICH_FRAME_CRC_LAYOUT_STRUCT)


class LICHFrame:
    """
    parts that get replicated in regularFrames:
        48b  Address dst
        48b  Address src
        16b  int(M17_streamtype)
        112b nonce (for encryption)
        #if actually sent on RF, needs a 16bit CRC also
    """
    sz = LICHFrameLayout.size

    def __init__(
            self,
            dst: Address = None,
            src: Address = None,
            stream_type: int = None,
            nonce: bytes = None
    ):
        self.src = src
        self.dst = dst
        self.stream_type = stream_type
        self.nonce = nonce
        assert len(nonce) == 14

    def __eq__(self, other):
        return bytes(self) == bytes(other)
        # lh_bytes = bytes(self)
        # rh_bytes = bytes(other)
        # print(f"len(lh_bytes): {len(lh_bytes)}")
        # print(f"lh_bytes: {print_hex(lh_bytes)}")
        # print(f"len(rh_bytes): {len(rh_bytes)}")
        # print(f"rh_bytes: {print_hex(rh_bytes)}")
        #
        # return lh_bytes == rh_bytes
        # for name in ["src","dst","streamtype","nonce"]:
        # x = getattr(self,name)
        # y = getattr(other,name)
        # z = x == y
        # print(z,x,y)

    def __str__(self):
        return f"LICH: {self.src.callsign} =[{self.stream_type}]> {self.dst.callsign}"

    def __bytes__(self):
        return self.pack()

    def get_pack_values(self):
        return [
            *bytes(self.dst),
            *bytes(self.src),
            self.stream_type,
            *self.nonce
        ]

    def pack(self):
        """
        returns the InitialCH(dst.addr, src.add, stream_type) as a bytes object
        """
        return LICHFrameLayout.pack(*self.get_pack_values())

    @classmethod
    def unpack(cls, data: bytes):
        """
        Convert bytes to LICHInitializer
        """
        unpacked_list = LICHFrameLayout.unpack(data)
        return cls(
            Address(addr=bytes(unpacked_list[0:6])),
            Address(addr=bytes(unpacked_list[6:12])),
            unpacked_list[12],
            bytes(unpacked_list[13:])
        )

    def chunks(self):
        """
        returns the InitialCH(dst.addr, src.add, stream_type) in 6 byte chunks
        """
        me = bytes(self)
        return chunk(me, 6)

    @staticmethod
    def from_bytes(data: bytes):
        """
        Convert bytes to InitialliCH
        data: bytes
        returns: InitialliCH
        """
        return LICHFrame.unpack(data)

    @staticmethod
    def dict_from_bytes(data: bytes):
        """
        Convert bytes to dict
        data: bytes
        returns: dict
        """
        lich_object = LICHFrame.unpack(data)
        return {
            "src": lich_object.src,
            "dst": lich_object.dst,
            "stream_type": lich_object.stream_type,
            "nonce": lich_object.nonce
        }

    @staticmethod
    def recover_bytes_from_bytes_frames(bytes_frames: list):
        """
        Recover bytes from bytes frames
        bytes_frames: list
        returns: bytes
        """
        frames = [RegularFrame.dict_from_bytes(b) for b in bytes_frames]
        # frame number gives us the idea of which part of the LICH we have in it
        # assuming that the first regular frame has the first part of the lich
        # per the spec
        # so we really just need one each of the "numbers on the clock"
        # so we could do this better by taking in packets and returning a LICH once
        # each spot is filled, which might be more robust

        # code below assumes there's a solution in the frames, that there's only one frame
        # for each spot on the "clock", etc, so it will be fragile with real RF

        idx_frame_number = [(frames.index(x), x["frame_number"]) for x in frames]
        # idx_frame_number = [ (0,9),(1,10),(2,11),(3,12),(4,13) ]
        # reorder so fn%5 == 0 is first
        # print( list(map( lambda x: x, idx_frame_number) ) )
        zeroth_chunk = list(map(lambda x: x[1] % 5 == 0, idx_frame_number)).index(True)
        # print(zeroth_chunk)
        reordered = frames[zeroth_chunk:] + frames[0:zeroth_chunk]
        # print(reordered)
        b = b""
        for p in reordered:
            b += p["lich_chunk"]
        return b


RegularFrameLayout = struct.Struct(m17_const.REGULAR_FRAME_LAYOUT_STRUCT)


class RegularFrame:
    """
    48b  LICH chunk
    16b  Frame number counter
    128b payload
    16b  CRC-16 chksum
    """
    sz = RegularFrameLayout.size
    lich_chunk_sz = int(48 / 8)
    payload_sz = int(128 / 8)

    def __init__(self, lich: Union[bytes, LICHFrame], m17_payload: M17Payload):
        """
        Can instantiate with either a full LICH object or just a lich_chunk
        """
        self.m17_payload = m17_payload
        self.lich = lich
        if isinstance(lich, bytes):
            self.lich_chunk = lich
        elif isinstance(lich, LICHFrame):
            self.lich_chunk = lich.chunks()[self.m17_payload.frame_number % 5]
        else:
            raise TypeError("lich must be bytes or LICHFrame")

    def __eq__(self, other):
        return bytes(self) == bytes(other)

    def __str__(self):
        return f"M17[{self.m17_payload.frame_number}]: {print_hex(self.m17_payload.payload)}"

    def __bytes__(self):
        return self.pack()

    def get_pack_values(self):
        return [
            *self.lich_chunk,
            *self.m17_payload.get_pack_values()
        ]

    def pack(self) -> bytes:
        """
        returns the RegularFrame as a bytes object
        """
        return RegularFrameLayout.pack(*self.get_pack_values())

    @classmethod
    def unpack(cls, data: bytes) -> "RegularFrame":
        """
        Convert bytes to RegularFrame
        """
        unpacked_values = RegularFrameLayout.unpack(data)
        return cls(
            bytes(unpacked_values[0:6]),
            M17Payload(
                unpacked_values[6],
                bytes(unpacked_values[7:15]),
                unpacked_values[15]
            )
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> "RegularFrame":
        """
        Convert bytes to RegularFrame
        """
        return RegularFrame.unpack(data)

    @staticmethod
    def dict_from_bytes(data: bytes) -> dict:
        """
        Convert bytes to dict
        """
        lich_chunk, frame_number, payload, crc = RegularFrameLayout.unpack(data)
        return {
            "lich_chunk": lich_chunk,
            "frame_number": frame_number,
            "payload": payload,
            "crc": crc
        }


IPFrameLayout = struct.Struct(m17_const.IP_FRAME_LAYOUT_STRUCT)


class IPFrame(RegularFrame):
    """
    32b "M17 "
    16b  StreamID
    ?    Full LICH bytes (minus CRC)
    16b  Frame number counter
    128b payload
    16b  CRC-16 chksum
    """
    sz = IPFrameLayout.size

    def __init__(
            self,
            magic_number: bytes = b"M17 ",
            stream_id: int = 0x0,
            full_lich: LICHFrame = None,
            m17_payload: M17Payload = None,
            *args,
            **kwargs
    ):
        super().__init__(
            full_lich,
            m17_payload,
            *args,
            **kwargs
        )
        self.magic_number = magic_number
        self.stream_id = stream_id

    def __str__(self):
        return (f"SID: {self.stream_id:04x}\n"
                f"LICH: {self.lich.src.callsign} =[ {self.lich.stream_type} ]> {self.lich.dst.callsign}\n"
                f"M17[ {self.m17_payload.frame_number} ]: {print_hex(self.m17_payload.payload)}")

    def __bytes__(self):
        return self.pack()

    def get_pack_values(self):
        ret_val = [
            *self.magic_number,
            self.stream_id,
            *self.lich.get_pack_values(),
            *self.m17_payload.get_pack_values()
        ]
        return ret_val

    def pack(self):
        return IPFrameLayout.pack(*self.get_pack_values())

    @classmethod
    def unpack(cls, data: bytes):
        unpacked_values = IPFrameLayout.unpack(data)
        return cls(
            bytes(unpacked_values[0:4]),
            unpacked_values[4],
            LICHFrame(
                Address(addr=bytes(unpacked_values[5:11])),
                Address(addr=bytes(unpacked_values[11:17])),
                unpacked_values[17],
                bytes(unpacked_values[18:32])
            ),
            M17Payload(
                unpacked_values[32],
                bytes(unpacked_values[33:41]),
                unpacked_values[41]
            )
        )

    @classmethod
    def from_bytes(cls, data: bytes):
        return IPFrame.unpack(data)

    @staticmethod
    def is_m17(data: bytes):
        return data[0:4] == m17_const.M17_MAGIC_NUMBER

    @staticmethod
    def dict_from_bytes(data: bytes):
        assert IPFrame.is_m17(data)
        magic_number, stream_id, dst, src, stream_type, nonce, frame_number, payload, crc = IPFrameLayout.unpack(data)
        return {
            "magic_number": magic_number,
            "stream_id": stream_id,
            "dst": dst,
            "src": src,
            "stream_type": stream_type,
            "nonce": nonce,
            "frame_number": frame_number,
            "payload": payload,
            "crc": crc
        }


def is_lich(b: bytes):
    """
    No real way to tell other than size with the implementation in this file
    in RF, they would be the same size
    """
    return len(b) == LICHFrame.sz


class M17_Frametype(int):
    """
    low bits v high bits
    stream?
    data?
    voice?
    non-codec2?
    non-3200bps?
    2b: encryption-type
    2b: encryption-subtype
    remaining of 16: reserved
    codec2 3200bps voice stream 00101
    """
    fields = [
        (1, "is_stream"),
        (1, "has_data"),
        (1, "has_voice"),
        (1, "non_codec2"),
        (1, "non_3200bps"),
        (2, "enc_type"),
        (2, "enc_subtype"),
        (7, "reserved"),
    ]
