#!/usr/bin/env python

import m17.network as network
from .blocks import *


def default_config(c2_mode):
    c2, conrate, bitframe = codec2setup(c2_mode)
    print("conrate, bitframe = [%d,%d]" % (conrate, bitframe))

    config = dattr({
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


def m17_parrot(refcallsign, port=default_port):
    # A parrot service for M17 - it's a full client that records and plays back after incoming stream is over PTT is released
    port = int(port)
    # udp_recv and udp_send are needed here, too.
    ...


def m17_mirror(refcallsign, port=default_port):
    # reflects your M17 stream back to you after decoding and encoding
    # can be useful for later transformations, like testing voice stream compatibilites
    port = int(port)
    # udp_recv and udp_send are needed here, too.
    ...


def udp_mirror(refcallsign, port=default_port):
    # reflects your own UDP packets back to you after a delay
    port = int(port)

    pkts = {}

    def packet_handler(sock, active_connections, bs, conn):
        if conn not in pkts:
            pkts[conn] = dattr({"packets": [], "lastseen": time.time()})
        else:
            this = pkts[conn]
            pkts[conn].packets.append((time.time() - this.lastseen, bs))
            pkts[conn].lastseen = time.time()

    def timer(sock):
        def replay(conn, packets):
            for reltime, bs in packets:
                time.sleep(reltime)
                sock.sendto(bs, conn)

        delthese = []
        for conn in pkts:
            if pkts[conn].lastseen + 10 < time.time():
                # as udp_server is written, this will stop us from recvfrom - and that's okay for now
                # if we have multiple users, we may well timeout on several in a row because of the delays we're seeing here
                # what i wish i had was a setTimeout like in JS, but I'm sure I can do something with asyncio later to get what I want (and actually support multiple udp_mirror users)
                replay(conn, pkts[conn].packets)
                delthese.append(conn)
        for conn in delthese:
            del pkts[conn]

    srv = udp_server(port, packet_handler, timer)
    srv()


def udp_reflector(refcallsign, port=default_port):
    # "Reflects" an incoming stream to all connected users.
    # ✔ So first, we need a way to receive connections and keep track of them, right?
    # We also have our own callsign, but we'll deal with that later.

    port = int(port)

    def packet_handler(sock, active_connections, bs, conn):
        others = [c for c in active_connections.keys() if c != conn]
        for c in others:
            sock.sendto(bs, c)

    srv = udp_server(port, packet_handler)
    srv()


def m17ref_client(mycall, mymodule, refname, module, port=default_port, mode=3200):
    mode = int(mode)  # so we can call modular_client straight from command line
    port = int(port)
    if (refname.startswith("M17-") and len(refname) <= 7):
        # should also be able to look up registered port in dns
        host = network.m17ref_name2host(refname)
        print(host)
        # fallback to fetching json if its not in dns already
    else:
        raise (NotImplementedError)
    myrefmod = "%s %s" % (mycall, mymodule)
    c = m17ref_client_blocks(myrefmod, module, host, port)
    tx_chain = [mic_audio, codec2enc, vox, m17frame, tobytes, c.sender()]
    rx_chain = [c.receiver(), m17parse, payload2codec2, codec2dec, spkr_audio]
    config = default_config(mode)
    config.m17.dst = "%s %s" % (refname, module)
    config.m17.src = mycall
    print(config)
    c.start()
    modular(config, [tx_chain, rx_chain])


def voipsim(host="localhost", src="W2FBI", dst="SP5WWP", mode=3200, port=default_port):
    mode = int(mode)  # so we can call modular_client straight from command line
    port = int(port)
    config = default_config(mode)
    audio_sim = zeros(size=config.codec2.conrate, dtype="<h", rate=50)
    tx_chain = [audio_sim, codec2enc, m17frame, tobytes, udp_send((host, port))]
    config.m17.dst = dst
    config.m17.src = src
    print(config)
    modular(config, [tx_chain])


def to_icecast(icecast_url, mode=3200, port=default_port):
    mode = int(mode)  # so we can call modular_client straight from command line
    port = int(port)
    rx_chain = [udp_recv(port), m17parse, payload2codec2, codec2dec, ffmpeg(icecast_url)]
    # rx_chain = [udp_recv(port), m17parse, tee('m17'), payload2codec2, codec2dec, ffmpeg(icecast_url)]
    config = default_config(mode)
    modular(config, [rx_chain])


def to_pcm(mode=3200, port=default_port):
    mode = int(mode)  # so we can call modular_client straight from command line
    port = int(port)
    rx_chain = [udp_recv(port), m17parse, tee('m17'), payload2codec2, codec2dec, teefile('m17.raw'), null]
    config = default_config(mode)
    modular(config, [rx_chain])


def recv_dump(mode=3200, port=default_port):
    mode = int(mode)  # so we can call modular_client straight from command line
    port = int(port)
    rx_chain = [udp_recv(port), teefile("rx"), m17parse, tee('M17'), payload2codec2, teefile('out.c2_3200'), codec2dec,
                teefile('out.raw'), spkr_audio]
    config = default_config(mode)
    modular(config, [rx_chain])


def voip(host="localhost", port=default_port, voipmode="full", mode=3200, src="W2FBI", dst="SP5WWP"):
    mode = int(mode)  # so we can call modular_client straight from command line
    port = int(port)

    # this requires remote host to have port forwarded properly and everything - it doesn't
    # reuse the server socket connection (which would support NAT traversal)

    # this means the tx and rx paths are completely separate, which is,
    # if nothing else, simple to reason about

    tx_chain = [mic_audio, codec2enc, vox, m17frame, tobytes, udp_send((host, port))]
    rx_chain = [udp_recv(port), m17parse, payload2codec2, codec2dec, spkr_audio]
    if voipmode == "tx":
        # disable the rx chain
        # useful for when something's already bound to listening port
        rx_chain = []
    if voipmode == "rx":
        # disable the tx chain
        # useful for monitoring incoming packets without sending anything
        tx_chain = []
    config = default_config(mode)

    config.m17.dst = dst
    config.m17.src = src
    print(config)

    modular(config, [tx_chain, rx_chain])


def echolink_bridge(mycall, mymodule, refname, refmodule, refport=default_port, mode=3200):
    mode = int(mode)  # so we can call modular_client straight from command line
    refport = int(refport)
    if (refname.startswith("M17-") and len(refname) <= 7):
        # should also be able to look up registered port in dns
        host = network.m17ref_name2host(refname)
        print(host)
        # fallback to fetching json if its not in dns already
    else:
        raise (NotImplementedError)
    myrefmod = "%s %s" % (mycall, mymodule)
    c = m17ref_client_blocks(myrefmod, refmodule, host, refport)
    echolink_to_m17ref = [udp_recv(55501), chunker_b(640), np_convert("<h"), integer_decimate(2), codec2enc, m17frame,
                          tobytes, c.sender()]
    m17ref_to_echolink = [c.receiver(), m17parse, payload2codec2, codec2dec, integer_interpolate(2),
                          udp_send(("127.0.0.1", 55500))]
    config = default_config(mode)
    config.m17.dst = "%s %s" % (refname, refmodule)
    config.m17.src = mycall
    print(config)
    c.start()
    modular(config, [echolink_to_m17ref, m17ref_to_echolink])


def m17_to_echolink(port=default_port, echolink_host="localhost", mode=3200, echolink_audio_in_port=55500):
    port = int(port)
    mode = int(mode)
    echolink_audio_in_port = int(echolink_audio_in_port)
    """
    decode and bridge m17 packets to echolink
    (useful for interopability testing)
    """
    chain = [
        udp_recv(port),
        m17parse, payload2codec2, codec2dec,
        integer_interpolate(2),  # echolink wants 16k audio
        udp_send((echolink_host, echolink_audio_in_port))
    ]
    config = default_config(mode)
    config.verbose = 0
    modular(config, [chain])


def _test_chains_example():
    """
    example playground for testing 
    """
    test_chain = [
        mic_audio,
        codec2enc,  # .02ms of audio per q element at c2.3200 in this part of chain
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
        codec2dec,
        # null,
        spkr_audio
    ]
    config = default_config(mode)
    config.verbose = 1
    modular(config, [test_chain])


def modular(config, chains):
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
    modules = {
        "chains": chains,
        "queues": [],
        "processes": [],
    }

    for chainidx, chain in enumerate(modules["chains"]):
        inq = None
        for fnidx, fn in enumerate(chain):
            name = fn.__name__
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
                print("lost a client process")
                break
            time.sleep(.05)
        # I can see where this is going to need to change
        # it's fine for now, but a real server will need something different
    except KeyboardInterrupt as e:
        print("Got ^C, ")
    finally:
        print("closing down")
        for proc in procs:
            # messy
            # TODO make a rwlock for indicating shutdown
            proc["process"].terminate()


if __name__ == "__main__":
    vars()[sys.argv[1]](*sys.argv[2:])

"""
Good links I found:
https://www.cloudcity.io/blog/2019/02/27/things-i-wish-they-told-me-about-multiprocessing-in-python/

"""
