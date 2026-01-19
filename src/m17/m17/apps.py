#!/usr/bin/env python
"""
M17 Application Examples

This module contains example applications for M17 protocol.
"""
from __future__ import annotations

import logging
import multiprocessing
import sys
import time
from typing import Any, Dict, List, NoReturn, Optional, Tuple, Union

import m17.blocks
import m17.network
from m17.const import DEFAULT_PORT
from m17.misc import DictDotAttribute

logger = logging.getLogger(__name__)


def default_config(c2_mode: int) -> DictDotAttribute:
    c2, conrate, bitframe = m17.blocks.codec2setup(c2_mode)
    logger.debug("conrate, bitframe = [%d,%d]", conrate, bitframe)

    config = DictDotAttribute({
        "m17": {
            "dst": "",
            "src": "",
        },
        "vox": {
            "silence_threshold": 10,  # that's measured in queue packets
        },
        "codec2": {
            "c2": c2,
            "conrate": conrate,
            "bitframe": bitframe,
        },
    })
    return config


def m17_parrot(refcallsign: str, port: Union[int, str] = DEFAULT_PORT) -> None:
    """
    A parrot service for M17.

    Records incoming streams and plays them back after the incoming stream
    is complete (PTT released). Useful for testing audio quality.

    Args:
        refcallsign: The callsign for the parrot service.
        port: UDP port to listen on.

    Raises:
        NotImplementedError: This function is not yet implemented.
    """
    raise NotImplementedError(
        "m17_parrot is not yet implemented. "
        "Required: recording buffer, stream end detection, playback logic."
    )


def m17_mirror(refcallsign: str, port: Union[int, str] = DEFAULT_PORT) -> None:
    """
    Mirror service for M17.

    Reflects your M17 stream back to you after decoding and re-encoding.
    Useful for testing voice codec compatibility and audio transformations.

    Args:
        refcallsign: The callsign for the mirror service.
        port: UDP port to listen on.

    Raises:
        NotImplementedError: This function is not yet implemented.
    """
    raise NotImplementedError(
        "m17_mirror is not yet implemented. "
        "Required: decode -> transform -> encode pipeline."
    )


def udp_mirror(refcallsign: str, port: Union[int, str] = DEFAULT_PORT) -> None:
    # reflects your own UDP packets back to you after a delay
    port_int = int(port)

    pkts: Dict[Tuple[str, int], DictDotAttribute] = {}

    def packet_handler(
        sock: Any,
        active_connections: Dict[Any, float],
        bs: bytes,
        conn: Tuple[str, int]
    ) -> None:
        if conn not in pkts:
            pkts[conn] = DictDotAttribute({"packets": [], "lastseen": time.time()})
        else:
            this = pkts[conn]
            pkts[conn].packets.append((time.time() - this.lastseen, bs))
            pkts[conn].lastseen = time.time()

    def timer(sock: Any) -> None:
        def replay(conn: Tuple[str, int], packets: List[Tuple[float, bytes]]) -> None:
            for reltime, bs in packets:
                time.sleep(reltime)
                sock.sendto(bs, conn)

        delthese: List[Tuple[str, int]] = []
        for conn in pkts:
            if pkts[conn].lastseen + 10 < time.time():
                # as udp_server is written, this will stop us from recvfrom - and that's okay for now
                # if we have multiple users, we may well timeout on several in a row because of the delays we're seeing here
                # what i wish i had was a setTimeout like in JS, but I'm sure I can do something with asyncio later to get what I want (and actually support multiple udp_mirror users)
                replay(conn, pkts[conn].packets)
                delthese.append(conn)
        for conn in delthese:
            del pkts[conn]

    srv = m17.blocks.udp_server(port_int, packet_handler, timer)
    srv()


def udp_reflector(refcallsign: str, port: Union[int, str] = DEFAULT_PORT) -> NoReturn:
    # "Reflects" an incoming stream to all connected users.
    # ✔ So first, we need a way to receive connections and keep track of them, right?
    # We also have our own callsign, but we'll deal with that later.

    port_int = int(port)

    def packet_handler(
        sock: Any,
        active_connections: Dict[Any, float],
        bs: bytes,
        conn: Tuple[str, int]
    ) -> None:
        others = [c for c in active_connections.keys() if c != conn]
        for c in others:
            sock.sendto(bs, c)

    srv = m17.blocks.udp_server(port_int, packet_handler)
    srv()


def m17ref_client(
    mycall: str,
    mymodule: str,
    refname: str,
    module: str,
    port: Union[int, str] = DEFAULT_PORT,
    mode: Union[int, str] = 3200
) -> None:
    mode_int = int(mode)  # so we can call modular_client straight from command line
    port_int = int(port)
    if (refname.startswith("M17-") and len(refname) <= 7):
        # should also be able to look up registered port in dns
        host = m17.network.m17ref_name2host(refname)
        logger.debug("Resolved reflector host: %s", host)
        # fallback to fetching json if its not in dns already
    else:
        raise NotImplementedError("Reflector name must start with 'M17-' and be <= 7 chars")
    myrefmod = "%s %s" % (mycall, mymodule)
    c = m17.blocks.M17ReflectorClientBlocks(myrefmod, module, host, port_int)
    tx_chain = [m17.blocks.mic_audio, m17.blocks.codec2enc, m17.blocks.vox, m17.blocks.m17frame, m17.blocks.tobytes,
                c.sender()]
    rx_chain = [c.receiver(), m17.blocks.m17parse, m17.blocks.payload2codec2, m17.blocks.codec2dec,
                m17.blocks.spkr_audio]
    config = default_config(mode_int)
    config.m17.dst = "%s %s" % (refname, module)
    config.m17.src = mycall
    logger.debug("Config: %s", config)
    c.start()
    modular(config, [tx_chain, rx_chain])


def voipsim(
    host: str = "localhost",
    src: str = "W2FBI",
    dst: str = "SP5WWP",
    mode: Union[int, str] = 3200,
    port: Union[int, str] = DEFAULT_PORT
) -> None:
    mode_int = int(mode)  # so we can call modular_client straight from command line
    port_int = int(port)
    config = default_config(mode_int)
    audio_sim = m17.blocks.zeros(size=config.codec2.conrate, dtype="<h", rate=50)
    tx_chain = [audio_sim, m17.blocks.codec2enc, m17.blocks.m17frame, m17.blocks.tobytes,
                m17.blocks.udp_send((host, port_int))]
    config.m17.dst = dst
    config.m17.src = src
    logger.debug("Config: %s", config)
    modular(config, [tx_chain])


def to_icecast(
    icecast_url: str,
    mode: Union[int, str] = 3200,
    port: Union[int, str] = DEFAULT_PORT
) -> None:
    mode_int = int(mode)  # so we can call modular_client straight from command line
    port_int = int(port)
    rx_chain = [m17.blocks.udp_recv(port_int), m17.blocks.m17parse, m17.blocks.payload2codec2, m17.blocks.codec2dec,
                m17.blocks.ffmpeg(icecast_url)]
    # rx_chain = [udp_recv(port), m17parse, tee('m17'), payload2codec2, codec2dec, ffmpeg(icecast_url)]
    config = default_config(mode_int)
    modular(config, [rx_chain])


def to_pcm(mode: Union[int, str] = 3200, port: Union[int, str] = DEFAULT_PORT) -> None:
    mode_int = int(mode)  # so we can call modular_client straight from command line
    port_int = int(port)
    rx_chain = [m17.blocks.udp_recv(port_int), m17.blocks.m17parse, m17.blocks.tee('m17'), m17.blocks.payload2codec2,
                m17.blocks.codec2dec, m17.blocks.teefile('m17.raw'), m17.blocks.null]
    config = default_config(mode_int)
    modular(config, [rx_chain])


def recv_dump(mode: Union[int, str] = 3200, port: Union[int, str] = DEFAULT_PORT) -> None:
    mode_int = int(mode)  # so we can call modular_client straight from command line
    port_int = int(port)
    rx_chain = [m17.blocks.udp_recv(port_int), m17.blocks.teefile("rx"), m17.blocks.m17parse, m17.blocks.tee('M17'),
                m17.blocks.payload2codec2, m17.blocks.teefile('out.c2_3200'), m17.blocks.codec2dec,
                m17.blocks.teefile('out.raw'), m17.blocks.spkr_audio]
    config = default_config(mode_int)
    modular(config, [rx_chain])


def voip(
    host: str = "localhost",
    port: Union[int, str] = DEFAULT_PORT,
    voipmode: str = "full",
    mode: Union[int, str] = 3200,
    src: str = "W2FBI",
    dst: str = "SP5WWP"
) -> None:
    mode_int = int(mode)  # so we can call modular_client straight from command line
    port_int = int(port)

    # this requires remote host to have port forwarded properly and everything - it doesn't
    # reuse the server socket connection (which would support NAT traversal)

    # this means the tx and rx paths are completely separate, which is,
    # if nothing else, simple to reason about

    tx_chain: List[Any] = [m17.blocks.mic_audio, m17.blocks.codec2enc, m17.blocks.vox, m17.blocks.m17frame, m17.blocks.tobytes,
                m17.blocks.udp_send((host, port_int))]
    rx_chain: List[Any] = [m17.blocks.udp_recv(port_int), m17.blocks.m17parse, m17.blocks.payload2codec2, m17.blocks.codec2dec,
                m17.blocks.spkr_audio]
    if voipmode == "tx":
        # disable the rx chain
        # useful for when something's already bound to listening port
        rx_chain = []
    if voipmode == "rx":
        # disable the tx chain
        # useful for monitoring incoming packets without sending anything
        tx_chain = []
    config = default_config(mode_int)

    config.m17.dst = dst
    config.m17.src = src
    logger.debug("Config: %s", config)

    modular(config, [tx_chain, rx_chain])


def echolink_bridge(
    mycall: str,
    mymodule: str,
    refname: str,
    refmodule: str,
    refport: Union[int, str] = DEFAULT_PORT,
    mode: Union[int, str] = 3200
) -> None:
    mode_int = int(mode)  # so we can call modular_client straight from command line
    refport_int = int(refport)
    if (refname.startswith("M17-") and len(refname) <= 7):
        # should also be able to look up registered port in dns
        host = m17.network.m17ref_name2host(refname)
        logger.debug("Resolved reflector host: %s", host)
        # fallback to fetching json if its not in dns already
    else:
        raise NotImplementedError("Reflector name must start with 'M17-' and be <= 7 chars")
    myrefmod = "%s %s" % (mycall, mymodule)
    c = m17.blocks.M17ReflectorClientBlocks(myrefmod, refmodule, host, refport_int)
    echolink_to_m17ref = [m17.blocks.udp_recv(55501), m17.blocks.chunker_b(640), m17.blocks.np_convert("<h"),
                          m17.blocks.integer_decimate(2), m17.blocks.codec2enc, m17.blocks.m17frame,
                          m17.blocks.tobytes, c.sender()]
    m17ref_to_echolink = [c.receiver(), m17.blocks.m17parse, m17.blocks.payload2codec2, m17.blocks.codec2dec,
                          m17.blocks.integer_interpolate(2),
                          m17.blocks.udp_send(("127.0.0.1", 55500))]
    config = default_config(mode_int)
    config.m17.dst = "%s %s" % (refname, refmodule)
    config.m17.src = mycall
    logger.debug("Config: %s", config)
    c.start()
    modular(config, [echolink_to_m17ref, m17ref_to_echolink])


def m17_to_echolink(
    port: Union[int, str] = DEFAULT_PORT,
    echolink_host: str = "localhost",
    mode: Union[int, str] = 3200,
    echolink_audio_in_port: Union[int, str] = 55500
) -> None:
    port_int = int(port)
    mode_int = int(mode)
    echolink_audio_in_port_int = int(echolink_audio_in_port)
    """
    decode and bridge m17 packets to echolink
    (useful for interopability testing)
    """
    chain = [
        m17.blocks.udp_recv(port_int),
        m17.blocks.m17parse, m17.blocks.payload2codec2, m17.blocks.codec2dec,
        m17.blocks.integer_interpolate(2),  # echolink wants 16k audio
        m17.blocks.udp_send((echolink_host, echolink_audio_in_port_int))
    ]
    config = default_config(mode_int)
    config.verbose = 0
    modular(config, [chain])


def _test_chains_example(mode: int = 3200) -> None:
    """
    example playground for testing
    """
    test_chain = [
        m17.blocks.mic_audio,
        m17.blocks.codec2enc,  # .02ms of audio per q element at c2.3200 in this part of chain
        # delay(5/.02), #to delay for 5s, divide 5s by the time-length of a q element in this part of chain (which does change)
        # tee("delayed c2bytes: "),
        # teefile("out.m17"),
        # vox,
        # ptt,
        # m17frame, #.04ms of audio per q element at c2.3200
        # tobytes,
        # udp_send,
        # udp_recv,
        # m17parse,
        # payload2codec2, #back to .02ms per q el
        m17.blocks.codec2dec,
        # null,
        m17.blocks.spkr_audio
    ]
    config = default_config(mode)
    config.verbose = 1
    modular(config, [test_chain])


def modular(config: DictDotAttribute, chains: List[List[Any]]) -> None:
    """
    Take in a global configuration, and a list of lists of queue
    processing functions, and hook them up in a chain, each function in
    its own process
    Fantastic for designing, developing, and debugging new features.
    """
    # a chain is a series of small functions that share a queue between each pair
    # each small function is its own process - which is absurd, except this
    # is a testing and development environment, so ease of implementation/modification
    # and modularity is the goal
    # this also means we can meet our latency constraint for writing out
    # to the speakers without any effort, even though our total latency
    # from mic->udp is greater than our deadline.
    # As long as each function stays under the deadline individually, all we do is add latency from sampled->delivered
    #   (well, as long as we have enough processor cores, but it's current_year, these functions still arent that heavy, and its working excellently given what I needed it to do
    # if a function does get slower than realtime, can I make two in its place writing to the same queues?
    #   as long as i have enough cores still, that seems reasonable - but I'll have to think about it
    """
    queues:
    n -> n2 -> n3 -> n4
    n has no inq
    n4 has no outq
    outq for n is inq for n2, etc
    for each chain:
        0 -> 1 -> 2 -> 3
          0    1     2
        if there's an old outq, inq=
        unless at end of chain, create an outq for each fn, outq=

    """
    modules: Dict[str, Any] = {
        "chains": chains,
        "queues": [],
        "processes": [],
    }

    for chainidx, chain in enumerate(modules["chains"]):
        inq: Optional["multiprocessing.Queue[Any]"] = None
        for fnidx, fn in enumerate(chain):
            name = fn.__name__
            outq: Optional["multiprocessing.Queue[Any]"]
            if fnidx != len(chain):
                outq = multiprocessing.Queue()
                modules["queues"].append(outq)
            else:
                outq = None
            process = multiprocessing.Process(name="chain_%d/fn_%d/%s" % (chainidx, fnidx, name), target=fn,
                                              args=(config, inq, outq))
            modules["processes"].append({
                "name": name,
                "inq": inq,
                "outq": outq,
                "process": process
            })
            process.start()
            inq = outq
    try:
        procs = modules['processes']
        while 1:
            if any(not p['process'].is_alive() for p in procs):
                logger.warning("Lost a client process")
                break
            time.sleep(.05)
        # I can see where this is going to need to change
        # it's fine for now, but a real server will need something different
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        logger.info("Closing down")
        for proc in procs:
            # messy
            # TODO make a rwlock for indicating shutdown
            proc["process"].terminate()


if __name__ == "__main__":
    _CLI_COMMANDS: Dict[str, Any] = {
        "m17_parrot": m17_parrot,
        "m17_mirror": m17_mirror,
        "udp_mirror": udp_mirror,
        "udp_reflector": udp_reflector,
        "m17ref_client": m17ref_client,
        "voipsim": voipsim,
        "to_icecast": to_icecast,
        "to_pcm": to_pcm,
        "recv_dump": recv_dump,
        "voip": voip,
        "echolink_bridge": echolink_bridge,
        "m17_to_echolink": m17_to_echolink,
        "modular": modular,
    }
    if len(sys.argv) < 2 or sys.argv[1] not in _CLI_COMMANDS:
        print(f"Usage: python -m m17.apps <command> [args]")
        print(f"Commands: {', '.join(_CLI_COMMANDS.keys())}")
        sys.exit(1)
    _CLI_COMMANDS[sys.argv[1]](*sys.argv[2:])

"""
Good links I found:
https://www.cloudcity.io/blog/2019/02/27/things-i-wish-they-told-me-about-multiprocessing-in-python/

"""
