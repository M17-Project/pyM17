"""This module contains constants used by the M17 protocol.
"""
import string

DEFAULT_PORT = 17000
SYNC = b"\x32\x43"


CALLSIGN_ALPHABET = " " + string.ascii_uppercase + string.digits + "-/."
# "." is TBD
# print("Alphabet: %s"%(callsign_alphabet))
# print("len(Alphabet): %d"%(len(callsign_alphabet)))


M17_ADDRESS_LAYOUT_STRUCT = "6B"
M17_MAGIC_NUMBER = b"M17 "
M17_PAYLOAD_LAYOUT_STRUCT = "H 8B H"  #  12 bytes -- 10 list items
LICH_FRAME_LAYOUT_STRUCT = "6B 6B H 14B"  #  28 bytes -- 27 list items
LICH_FRAME_CRC_LAYOUT_STRUCT = f"{LICH_FRAME_LAYOUT_STRUCT} H"  #  30 bytes -- 28 list items
REGULAR_FRAME_LAYOUT_STRUCT = f"6B {M17_PAYLOAD_LAYOUT_STRUCT}"  #  18 bytes -- 16 list items
IP_FRAME_LAYOUT_STRUCT = (
    f"4B H {LICH_FRAME_LAYOUT_STRUCT} {M17_PAYLOAD_LAYOUT_STRUCT}"  #  48 bytes -- 42 list items
)
