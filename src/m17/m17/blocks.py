"""blocks.py
"""
from __future__ import annotations

import logging
import multiprocessing
import queue
import random
import socket
import sys
import time
from collections.abc import Callable
from typing import Any, NoReturn, Optional

import numpy
import numpy.typing as npt

from m17 import Address, IPFrame, M17IPFramer, network
from m17.misc import chunk, print_hex

logger = logging.getLogger(__name__)


# Type aliases for block functions
BlockFunction = Callable[[Any, "multiprocessing.Queue[Any]", "multiprocessing.Queue[Any]"], None]
NDArrayInt16 = npt.NDArray[numpy.int16]


def codeblock(callback: Callable[[Any], Any]) -> BlockFunction:
    """Wrap a callback in a block that can be used in the processing chain"""

    def fn(
        config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
    ) -> NoReturn:
        """The block itself"""
        while 1:
            x = inq.get()
            y = callback(x)
            outq.put(y)

    return fn


def udp_server(
    port: int,
    packet_handler: Callable[
        [socket.socket, dict[tuple[str, int], float], bytes, tuple[str, int]], None
    ],
    occasional: Optional[Callable[[socket.socket], None]] = None,
) -> Callable[[], NoReturn]:
    """Not meant to be used in a chain"""

    def fn() -> NoReturn:  # but still has a closure to allow running it as a process
        """The actual function that gets run"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", port))
        sock.setblocking(False)
        active_connections: dict[tuple[str, int], float] = {}
        timeout = 30
        while 1:
            active_connections = {
                k: v for k, v in active_connections.items() if v + timeout < time.time()
            }
            try:
                bs, conn = sock.recvfrom(1500)
                active_connections[conn] = time.time()
                packet_handler(sock, active_connections, bs, conn)
            except BlockingIOError:
                pass
            if occasional:
                occasional(sock)
            time.sleep(0.001)

    return fn


def zeros(size: int, dtype: str, rate: float) -> BlockFunction:
    """Generate a stream of numpy arrays of zeros at a specified rate"""

    def fn(
        config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
    ) -> NoReturn:
        """The block itself"""
        while 1:
            outq.put(numpy.zeros(size, dtype))
            time.sleep(1 / rate)

    return fn


class M17ReflectorClientBlocks:
    """A set of blocks that can be used to create a reflector client"""

    def __init__(self, mycall: str, theirmodule: str, host: str, port: int) -> None:
        self.mycall = mycall
        self.theirmodule = theirmodule
        self.host = host
        self.port = port
        self.qs: dict[str, multiprocessing.Queue[Any]] = {}

    def start(self) -> None:
        """Start the reflector client"""
        process = multiprocessing.Process(
            name="m17ref_client_blocks",
            target=self.proc,
            args=(self.qs, self.mycall, self.theirmodule, self.host, self.port),
        )
        process.start()

    def proc(
        self,
        qs: dict[str, multiprocessing.Queue[Any]],
        mycall: str,
        theirmodule: str,
        host: str,
        port: int,
    ) -> NoReturn:
        """The shared process that handles the socket"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", random.randint(17010, 17100)))
        sock.setblocking(False)
        timeout = 0.1
        sendq = qs["send"]
        recvq = qs["recv"]
        conn: tuple[str, int] = (host, port)
        refcon = network.n7tae_reflector_conn(sock, conn, mycall, theirmodule)
        refcon.connect()
        while 1:
            try:
                bs, conn = sock.recvfrom(1500)
                logger.debug("RECV %s", bs)
                if bs.startswith(b"M17 "):
                    recvq.put(bs)  # could also hand conn along later
                else:
                    refcon.handle(bs, conn)
            except BlockingIOError:
                pass
            if not sendq.empty():
                data = sendq.get_nowait()
                logger.debug("SEND %s", data)
                sock.sendto(data, conn)
            time.sleep(0.000001)

    def probe(self, name: str, direction: str) -> BlockFunction:
        """Processes that can sample inputs and outputs
        direction describes the path of elements from fn -
        e.g. if it's being used only to generate packets, the direction is "out"
        if it's being used to terminate a processing stream, the direction is "in"
        """
        self.qs[name] = multiprocessing.Queue()

        def fn(
            config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
        ) -> NoReturn:
            while 1:
                if direction == "in":
                    self.qs[name].put(inq.get())
                elif direction == "out":
                    outq.put(self.qs[name].get())
                time.sleep(0.000001)

        return fn

    def receiver(self) -> BlockFunction:
        return self.probe("recv", "out")

    def sender(self) -> BlockFunction:
        return self.probe("send", "in")


def null(
    config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
) -> NoReturn:
    """Don't do nuffin.

    (Useful for stopping a q from filling up and preventing further processing)

    (Probably used after tee() or teefile() if you just want to collect
    data with those and not do further processing on the data stream)
    """
    while 1:
        x = inq.get()


def tee(header: str) -> BlockFunction:
    """Log incoming items before putting them on the next q.
    bytes get logged as hex strings.
    "header" parameter gets logged with each queue element to differentiate multiple tee()s.
    named like standard UNIX tee(1)
    """

    def fn(
        config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
    ) -> NoReturn:
        while 1:
            x = inq.get()
            if type(x) == bytes:
                logger.debug("%s %s", header, print_hex(x))
            else:
                logger.debug("%s %s", header, x)
            outq.put(x)

    return fn


def ffmpeg(ffmpeg_url: str) -> BlockFunction:
    # Example URL format (uses DEFAULT_TEST_HOST from m17.core.constants):
    # ffmpeg_url_example = f"icecast://source:m17@{DEFAULT_TEST_HOST}:876/live.ogg"
    _ = ffmpeg_url  # Used via closure

    def fn(
        config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
    ) -> NoReturn:
        from subprocess import PIPE, Popen

        p = Popen(
            [
                "ffmpeg",
                "-re",
                # ffmpeg, and limit reading rate to native speed so we don't spin a whole core with writing zeros to icecast
                "-f",
                "s16le",
                "-ar",
                "8000",
                "-ac",
                "1",
                "-i",
                "/dev/stdin",  # the input options
                "-ar",
                "48000",
                "-ac",
                "2",
                "-content_type",
                "'application/mpeg'",  # only support ogg for now
                ffmpeg_url,
            ],
            stdout=PIPE,
            stdin=PIPE,
            stderr=PIPE,
        )
        while 1:
            try:
                # audio = inq.get_nowait()
                audio = inq.get()
                p.stdin.write(audio.tobytes())  # type: ignore[union-attr]
            except queue.Empty:
                sys.stdout.write("aU")
                audio = numpy.zeros(config.codec2.conrate, dtype="<h")
            sys.stdout.flush()
            # time.sleep(1/50)

    return fn


def teefile(filename: str) -> BlockFunction:
    """Same as tee, except assumes elements coming in are bytes, and writes
    them to a provided filename
    """

    def fn(
        config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
    ) -> NoReturn:
        with open(filename, "wb") as fd:
            try:
                while True:
                    x = inq.get()
                    fd.write(x)
                    fd.flush()
                    outq.put(x)
            except Exception:
                fd.close()
        # This is unreachable but satisfies type checker
        raise RuntimeError("Unexpected exit")  # pragma: no cover

    return fn


def throttle(n_per_second: float) -> BlockFunction:
    """Read from the inq and only put elements on the outq at (no more than)
    a specified rate in q elements per second. As "no more than" might
    suggest, this is setting a maximum, not a minimum. Minimum is based
    on your hardware and a number of other factors.

    Args:
    ----
        n_per_second: Maximum elements per second to pass through.

    Returns:
    -------
        A block function that rate-limits queue elements.
    """
    interval = 1.0 / n_per_second

    def fn(
        config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
    ) -> NoReturn:
        last_send = 0.0
        while 1:
            x = inq.get()
            now = time.time()
            elapsed = now - last_send
            if elapsed < interval:
                time.sleep(interval - elapsed)
            outq.put(x)
            last_send = time.time()

    return fn


def delay(size: int) -> BlockFunction:
    """Keep a rolling fifo of size "size", creating a predictable delay
    (assuming they are coming in at a limited rate)

    See "throttle()" for enforcing a rate limit of elements per unit time.
    """

    def fn(
        config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
    ) -> NoReturn:
        fifo: list[Any] = []
        while 1:
            x = inq.get()
            fifo.insert(0, x)
            if len(fifo) > size:
                outq.put(fifo.pop())

    return fn


def ptt(config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]) -> NoReturn:
    """Take elements off the inq (like audio frames) and only put them on the outq
    if the "push to talk" evaluates truthy.

    Redo this to take a check function as a parameter and close around
    that instead of using config
    """
    while 1:
        x = inq.get()
        if config.ptt.poll():  # this will check for every single packet
            outq.put(x)


def vox(config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]) -> NoReturn:
    """Watch for duplicate incoming q elements, and if there's more than
    a configurable threshold in a row, don't copy further duplicates

    This lets you use a microphone mute as a reverse PTT, among other things
    """
    last: Any = None
    repeat_count = 0
    while 1:
        x = inq.get()
        if x == last:
            repeat_count += 1
        else:
            repeat_count = 0
        last = x
        if repeat_count > config.vox.silence_threshold:
            continue
        outq.put(x)


def mic_audio(
    config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
) -> NoReturn:
    """Pull audio off the default microphone in 8k, 1 channel, scale it
    into 16bit shorts since soundcard uses floats, and put them in the outq.

    inq is unconnected here.
    """
    import soundcard as sc

    default_mic = sc.default_microphone()
    # print(default_mic)
    conrate = config.codec2.conrate
    with default_mic.recorder(samplerate=8000, channels=1, blocksize=conrate) as mic:
        while 1:
            audio = mic.record(numframes=conrate)
            # we get "interleaved" floats out of here, in a numpy column ([[][][]])(hence the flatten even though it's a single audio channel)
            audio = audio.flatten() * 32767  # scales from -1,1 to signed 16bit int values
            # rest of the system works in little endian shorts, so we scale it up and convert the type
            audio = audio.astype("<h")
            outq.put(audio)


def spkr_audio(
    config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
) -> NoReturn:
    """Play mono (c=1) 8k audio into the speaker
    Accepts 16bit shorts, converts to soundcard expected format

    outq is unconnected here.

    buflen allows for slow computers that cant keep the buffers filled
    within the realtime constraints to still play smooth audio - just
    in stutters of specified length in frames
    """
    import soundcard as sc

    default_speaker = sc.default_speaker()

    # print(default_speaker)
    def silence() -> None:
        sp.play(numpy.zeros(config.codec2.conrate))

    with default_speaker.player(samplerate=8000, channels=1) as sp:
        buf: list[Any] = []  # allow for playing chunks of audio even when computer is slow
        buflen = 0  # 0 is dont use
        while 1:
            # if we stop receiving audio because someone stops transmitting,
            # we wont get anything off the queue, so we can't block (hence nowait)
            try:
                audio = inq.get_nowait()
                # rest of system works in LE signed shorts but soundcard expects floats in and out
                # so convert it back to a float, and scale it back down to an appropriate range (-1,1)
                audio = audio.astype("float")
                audio = audio / 32767
                if buflen:
                    if len(buf) < buflen:
                        buf.append(audio)
                        silence()
                    else:
                        for b in buf:
                            sp.play(b)
                        buf = []
                sp.play(audio)
            except queue.Empty:
                # and if we have no data, just play zeros
                silence()


def tobytes(
    config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
) -> NoReturn:
    """Convert everything passing through to bytes, just what it says on the tin"""
    while 1:
        outq.put(bytes(inq.get()))


def m17frame(
    config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
) -> NoReturn:
    """Frame incoming codec2 compressed audio frames into M17 packets"""
    dst = Address(callsign=config.m17.dst)
    src = Address(callsign=config.m17.src)
    logger.debug("M17 frame: dst=%s, src=%s", dst, src)
    framer = M17IPFramer(
        stream_id=random.randint(1, 2**16 - 1),
        dst=dst,
        src=src,
        streamtype=5,  # TODO need to set this based on codec2 settings too to support c2.1600
        nonce=b"\xbe\xef\xf0\x0d" + b"a" * 10,
    )
    while 1:
        plen = 16  # TODO grab from the framer itself
        # need 16 bytes for M17 payload, each element on q should be 8 bytes if c2.3200
        # this will fail in funny ways if our c2 payloads dont fit exactly on byte boundaries
        d = inq.get()
        while len(d) < plen:
            d += inq.get()
        # TODO generalize to support other Codec2 sizes, and grab data until enough is here to send
        # TODO payload_stream needs to return packets and any unused data from the buffer to support that functionality
        pkts = framer.payload_stream(d)
        for pkt in pkts:
            outq.put(pkt)


def m17parse(
    config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
) -> NoReturn:
    """Parse incoming bytes into M17 ipFrames"""
    while 1:
        f = IPFrame.from_bytes(inq.get())
        if "verbose" in config and config.verbose:
            logger.debug("Parsed M17 frame: %s", f)
        outq.put(f)


def payload2codec2(
    config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
) -> NoReturn:
    """Pull out an M17 payload and return just the raw Codec2 bytes"""
    byteframe = int(
        config.codec2.bitframe / 8
    )  # TODO another place where we assume codec2 frames are byte-sized
    while 1:
        x = inq.get()
        for c in chunk(x.payload, byteframe):
            assert len(c) == byteframe
            outq.put(c)


def codec2setup(mode: int) -> list[Any]:
    import pycodec2

    c2 = pycodec2.Codec2(mode)
    conrate: int = c2.samples_per_frame()
    bitframe: int = c2.bits_per_frame()
    return [c2, conrate, bitframe]


def codec2enc(
    config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
) -> NoReturn:
    """Exact opposite of codec2dec

    8khz sample rate, 1 channel (mono audio)
    In: 16bit signed shorts, size varies but expects 160 samples for Codec2 3200
    Out: depends on Codec2 mode, but 3200 bps gives 8 bytes per 160 sample raw frame.
    """
    while 1:
        audio = inq.get()
        c2bits = config.codec2.c2.encode(audio)
        assert len(c2bits) == config.codec2.bitframe / 8
        outq.put(c2bits)


def codec2dec(
    config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
) -> NoReturn:
    """Exact opposite of codec2enc
    In: Depends on Codec2 mode, but expects 8 bytes for Codec2 mode 3200
    Out: 16 bit signed shorts, size varies but 160 samples for Codec2 mode 3200
    8khz sample rate, 1 channel (mono audio)
    """
    while 1:
        c2bits = inq.get()
        audio = config.codec2.c2.decode(c2bits)
        outq.put(audio)


def udp_send(sendto: tuple[str, int]) -> BlockFunction:
    """Send incoming bytes to udp (host,port)

    sendto is the standard host,port) tuple like ("localhost",17000)
    """

    def fn(
        config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
    ) -> NoReturn:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        while 1:
            bs = inq.get()
            sock.sendto(bs, sendto)

    return fn


def udp_recv(port: int) -> BlockFunction:
    """Receive UDP datagram payloads as bytes and output them to outq
    Maintains UDP datagram separation on the q
    Does not allow for responding to incoming packets. See udp_server for that.
    """

    def fn(
        config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
    ) -> NoReturn:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", port))
        # sock.setblocking(False)
        while 1:
            x, conn = sock.recvfrom(1500)
            # 1500 is the maximum packet payload size

            # but what do I do with conn data, anything?
            # print(_x(x))
            outq.put(x)

    return fn


def integer_decimate(i: int) -> BlockFunction:
    """For each incoming list of things, skip some of them, decimating the incoming signal
    e.g. integer_decimate(2) will cut a 16khz sampled audio signal to 8khz
    see integer_interpolate for the reverse
    """

    def fn(
        config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
    ) -> NoReturn:
        while 1:
            x = inq.get()
            de = x[::i]
            outq.put(x[::i])

    return fn


def integer_interpolate(i: int) -> BlockFunction:
    """For each incoming list of things, interpolate
    useful for going from 8khz audio to 16khz audio to match expected formats

    starting to look uncomfortably like gnuradio, innit?
    """

    def fn(
        config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
    ) -> NoReturn:
        import samplerate

        resampler = samplerate.Resampler("sinc_best", channels=1)
        while 1:
            x = inq.get()
            y = resampler.process(x, i)
            z = numpy.array(y, dtype="<h")
            outq.put(z)

    return fn


def chunker_b(size: int) -> BlockFunction:
    """Incoming bytes will get chunked into a particular size for downstream
    nodes that don't do their own buffering
    """

    def fn(
        config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
    ) -> NoReturn:
        buf = b""
        while 1:
            x = inq.get()
            buf += x
            while len(buf) > size:
                outq.put(buf[:size])
                buf = buf[size:]

    return fn


def np_convert(outtype: str) -> BlockFunction:
    """Use numpy to convert incoming elements to a numpy type"""

    def fn(
        config: Any, inq: multiprocessing.Queue[Any], outq: multiprocessing.Queue[Any]
    ) -> NoReturn:
        while 1:
            x = inq.get()
            y = numpy.frombuffer(x, outtype)
            outq.put(y)

    return fn


def check_ptt() -> bool:
    """Is there a good way to do cross platform ptt, or
    should i abandon that idea and try to improve vox, or
    just assume linux?
    """
    if int(time.time() / 2) % 2 == 0:
        return True
    else:
        return False
