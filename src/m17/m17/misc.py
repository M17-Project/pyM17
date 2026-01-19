"""
misc.py
"""
from __future__ import annotations

import binascii
import functools
import random
import sys
from typing import Any, Callable, Dict, List, TypeVar, Union

T = TypeVar("T", bound=Union[bytes, str])


def binary_print_factory(size: int) -> Callable[[int], str]:
    """
    Create a function that will print a number in binary, in chunks of a certain size.
    :param size: size of each chunk
    """
    def binary_print(num: int) -> str:
        binary_str = format(num, 'b').zfill(size)
        chunked_str = [binary_str[max(i - size, 0):i] for i in range(len(binary_str), 0, -size)]
        return " ".join(chunked_str[::-1])

    return binary_print


print_4bits = binary_print_factory(4)
print_8bits = binary_print_factory(8)
print_16bits = binary_print_factory(16)
print_bits = print_8bits
print_hex = functools.partial(binascii.hexlify, sep=" ", bytes_per_sep=-4)


def example_bytes(length: int) -> bytearray:
    """
    :param length: number of bytes to generate
    """
    return bytearray(random.getrandbits(8) for _ in range(length))


def demonstrate_chunk() -> None:
    """
    demonstrate the chunk function
    """
    ab = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    print(chunk(ab, 5))
    print(chunk(ab, -5))


def chunk(b: bytes, size: int) -> List[bytes]:
    """
    Chunk a byte array into chunks of a certain size

    :param b: bytes to chunk
    :param size: size of each chunk, chunk size is abs(size), chunk size of 0 is an error
        if size is positive, chunks starting left to right
        if size is negative, chunk from the right instead
    :return: a list of chunks of that size
    """
    fromright = size < 0
    size = abs(size)
    if fromright:
        return [b[::-1][i:i + size][::-1] for i in range(0, len(b), size)][::-1]
        # I'm not sorry
        # okay, maybe a little bit.
    else:
        return [b[i:i + size] for i in range(0, len(b), size)]


class DictDotAttribute(dict[str, Any]):
    """
    "DictDotAttribute", used for when you don't want to type [""] all the time
    (and i think it looks nicer for things like config settings)
    """

    def __getattr__(self, name: str) -> Any:
        """
        With a DictDotAttribute, you can do this:
        >>> x = DictDotAttribute({"abc":True})
        >>> x.abc
        True

        """
        if name in self and isinstance(self[name], dict) and not isinstance(self[name], DictDotAttribute):
            # make sure we wrap any nested dicts when we encounter them
            self[name] = DictDotAttribute(self[name])  # has to assign to save any changes to nested DictDotAttributes
            # e.g.  x.abc.fed = "in"

        # otherwise just make our key,value pairs accessible through . (e.g. x.name)
        return self[name]

    def __setattr__(self, name: str, value: Any) -> None:
        """
        With a DictDotAttribute, you can do this:

        >>> x = DictDotAttribute({"abc":True})
        >>> x.abc = False
        >>> x.abc
        False
        """
        self[name] = value


def c_array_init_file(filename: str) -> None:
    """
    Print a C array initializer for a file
    """
    with open(filename, "rb") as fd:
        c_array_init(fd.read())


def c_array_init(bs: bytes) -> None:
    """
    Print a C array initializer for a byte array
    """
    print("uint8_t sample_stream[]={")
    line = ""
    cnt = 0
    for b in bs:
        line += hex(b)
        line += ","
        cnt += 1
        if cnt == 4:
            line += "\t"
        if cnt >= 8:
            print(line)
            line = ""
            cnt = 0
            continue
    print("}")
    # cat filename |grep -o 'x' |wc -l to know how big it is


if __name__ == "__main__":
    _CLI_COMMANDS: Dict[str, Callable[..., Any]] = {
        "c_array_init_file": c_array_init_file,
        "demonstrate_chunk": demonstrate_chunk,
    }
    if len(sys.argv) < 2 or sys.argv[1] not in _CLI_COMMANDS:
        print(f"Usage: python -m m17.misc <command> [args]")
        print(f"Commands: {', '.join(_CLI_COMMANDS.keys())}")
        sys.exit(1)
    _CLI_COMMANDS[sys.argv[1]](*sys.argv[2:])
