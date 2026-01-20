"""M17 Networking (Legacy Module)

This module contains legacy networking code for M17.

.. deprecated:: 0.1.1
    This module is deprecated. Use the :mod:`m17.net` package instead.

    Example migration::

        # Old import (deprecated)
        from m17.network import n7tae_reflector_conn

        # New import (preferred)
        from m17.net.reflector import ReflectorClient
"""
from __future__ import annotations

import asyncio
import enum
import json
import logging
import queue
import socket
import sys
import threading
import time
import warnings
from collections.abc import Awaitable, Callable
from typing import Any, Optional, Union

from kademlia.network import Server

import m17
import m17.address
import m17.misc
from m17.core.constants import (
    get_reflector_host,
)
from m17.misc import DictDotAttribute

logger = logging.getLogger(__name__)

# Emit deprecation warning on module import
warnings.warn(
    "m17.network is deprecated and will be removed in v1.0. " "Use the m17.net package instead.",
    DeprecationWarning,
    stacklevel=2,
)

primaries: list[tuple[str, int]] = []  # Must be explicitly configured
dhtbootstraps: list[tuple[str, int]] = []  # Must be explicitly configured


def m17ref_name2host(refname: str, domain: str) -> str:
    """Convert a reflector name to a hostname.

    Args:
    ----
        refname: Reflector name (e.g., "M17-ABC").
        domain: Reflector domain suffix (required, e.g., "m17ref.example.com").

    Returns:
    -------
        Full hostname (e.g., "M17-ABC.m17ref.example.com").
    """
    return get_reflector_host(refname, domain)


class n7tae_reflector_conn:
    def __init__(
        self, sock: socket.socket, conn: tuple[str, int], mycallsign: str, theirmodule: str = "A"
    ) -> None:
        self.module = theirmodule
        self.sock = sock
        self.conn = conn
        self.mycallsign = mycallsign
        self.mycall_b = bytes(m17.address.Address(callsign=self.mycallsign))
        logger.debug("MYCALL=%s", self.mycallsign)

    def connect(self) -> None:
        data = b"CONN" + self.mycall_b + self.module.encode("ascii")
        self.send(data)

    def pong(self) -> None:
        data = b"PONG" + self.mycall_b
        self.send(data)

    def disco(self) -> None:
        data = b"DISC" + self.mycall_b
        self.send(data)

    def send(self, data: bytes) -> None:
        logger.debug("TAE SEND: %s", data)
        self.sock.sendto(data, self.conn)

    def handle(self, pkt: bytes, conn: tuple[str, int]) -> None:
        if pkt.startswith(b"PING"):
            self.pong()
        elif pkt.startswith(b"ACKN"):
            pass  # everything's fine
        elif pkt.startswith(b"NACK"):
            self.disco()
            raise Exception("Refused by reflector")
        elif pkt.startswith(b"CONN"):
            raise NotImplementedError("CONN packet handling not implemented")
        else:
            logger.warning("Unhandled packet type: %s", pkt)
            raise NotImplementedError(f"Unhandled packet type: {pkt[:4]!r}")


class msgtype(enum.Enum):
    where_am_i = 0  # remote host asks what their public IP is
    i_am_here = 1  # remote host asks to tie their host and callsign together
    where_is = 2  # getting a query for a stored callsign
    is_at = 3  # getting a reply to a query
    introduce_me = (
        4  # got a request: please introduce me to host, i'm trying to talk to them on port...
    )
    introducing = 5  # got an intro: I have an introduction for you, please contact ...
    hi = 6  # got an "oh hey" packet


# def getmyexternalip():
# # from requests import get
# # ip = get('https://api.ipify.org').text
# # ip = get('https://ident.me').text
# #or talk to bootstrap host
# # or https://stackoverflow.com/a/41385033
# # or https://checkip.amazonaws.com
# # or http://myip.dnsomatic.com
# return ip


class m17_networking_direct:
    def __init__(self, primaries: list[tuple[str, int]], callsign: str, port: int = 17000) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", port))
        self.sock.setblocking(False)
        # self.sock.bind( ("::1", 17000) )

        self.recvQ: queue.Queue[tuple[bytes, tuple[str, int]]] = queue.Queue()
        self.sendQ: queue.Queue[tuple[bytes, tuple[str, int]]] = queue.Queue()
        network_thread = threading.Thread(target=self.networker, args=(self.recvQ, self.sendQ))
        network_thread.start()

        self.conns: dict[
            Union[str, tuple[str, int]], DictDotAttribute
        ] = {}  # i was intending this for client side, not sure it makes sense

        self.whereis: dict[Union[str, tuple[str, int]], tuple[float, Any]] = {}

        self.primaries = primaries
        self.callsign = callsign
        self.m17_addr = m17.address.Address.encode(self.callsign)

        self.last: float = 0
        self.registration_keepalive_period = 25
        self.connection_timeout = 25
        self.looper: Optional[threading.Thread] = None

    def networker(
        self,
        recvq: queue.Queue[tuple[bytes, tuple[str, int]]],
        sendq: queue.Queue[tuple[bytes, tuple[str, int]]],
    ) -> None:
        """ """
        while True:
            try:
                data, conn = self.sock.recvfrom(1500)
                logger.debug("RECV %s %s", conn, data)
                recvq.put((data, conn))
            except BlockingIOError:
                pass
            if not sendq.empty():
                data, conn = sendq.get_nowait()
                logger.debug("SEND %s %s", conn, data)
                self.sock.sendto(data, conn)
            time.sleep(0.0001)

    def loop(self) -> None:
        def looper(self: m17_networking_direct) -> None:
            while True:
                self.loop_once()
                time.sleep(0.005)

        self.looper = threading.Thread(target=looper, args=(self,))
        self.looper.start()

    def clean_conns(self) -> None:
        ...
        # self.conns = {conn: data for conn, data in self.conns if time.time() - data.last > self.connection_timeout}

    def loop_once(self) -> None:
        self.registration_keepalive()
        if not self.recvQ.empty():
            data, conn = self.recvQ.get_nowait()
            logger.debug("Recv: %s %s", data, conn)
            if conn[0] not in self.conns:
                self.conns[conn] = DictDotAttribute(
                    {
                        "last": time.time(),
                        "conn": conn,
                    }
                )
                logger.debug("New connection: %s", self.conns)
            else:
                self.conns[conn[0]].last = time.time()
            self.process_packet(data, conn)
        # self.clean_conns()
        # self.clean_whereis()

    def M17J_send(self, payload: bytes, conn: tuple[str, int]) -> None:
        # print("Sending to %s M17J %s"%(conn,payload))
        self.sendQ.put((b"M17J" + payload, conn))

    def process_packet(self, payload: bytes, conn: tuple[str, int]) -> None:
        if payload.startswith(b"M17 "):
            ...
            # voice and data packets
        elif payload.startswith(
            b"M17J"
        ):  # M17 Json development and evaluation protocol - the standard is, there is no standard
            msg = DictDotAttribute(json.loads(payload[4:].decode("utf-8")))
            if msg.msgtype == msgtype.where_am_i:
                self.reg_store(msg.callsign, conn)  # so we store it
            elif msg.msgtype == msgtype.i_am_here:
                self.reg_store(msg.callsign, conn)  # so we store it
            elif msg.msgtype == msgtype.where_is:
                callsign = msg.callsign
                lastseen, theirconn = self.reg_fetch(callsign)
                self.answer_where_is(conn, callsign, theirconn)
            elif msg.msgtype == msgtype.is_at:
                logger.info("Found %s at %s", msg.callsign, msg.host)
                self.reg_store(msg.callsign, (msg.host, msg.port))

            elif msg.msgtype == msgtype.introduce_me:
                self.arrange_rendezvous(conn, msg)
            elif msg.msgtype == msgtype.introducing:
                self.attempt_rendezvous(conn, msg)
            elif msg.msgtype == msgtype.hi:
                logger.info("Got a holepunch packet from %s", conn)
                self.reg_store(msg.callsign, conn)
        else:
            logger.warning("Unrecognized payload: %s", payload)

    def reg_fetch(self, callsign: str) -> tuple[float, tuple[str, int]]:
        """Fetch registration by callsign."""
        result = self.whereis[callsign]
        return (result[0], result[1])

    def answer_where_is(self, conn: tuple[str, int], callsign: str, loc: tuple[str, int]) -> None:
        """Answer a where-is query."""
        addr = m17.address.Address.encode(callsign)
        payload = json.dumps({"msgtype": "is at", "m17_addr": addr.hex(), "host": loc[0]}).encode(
            "utf-8"
        )
        self.M17J_send(payload, conn)

    # user registration handling starts here
    def registration_keepalive(self) -> None:
        """Periodically re-register"""
        if not self.callsign:
            return
        sincelastrun = time.time() - self.last
        if sincelastrun > self.registration_keepalive_period:
            for primary in primaries:
                self.register_me_with(primary)
            self.last = time.time()

    def register_me_with(self, server: tuple[str, int]) -> None:
        payload = json.dumps({"msgtype": "i am here", "callsign": self.callsign}).encode("utf-8")
        self.M17J_send(payload, server)

    def reg_store(self, callsign: str, conn: tuple[str, int]) -> None:
        logger.debug("[M17 registration] %s -> %s", callsign, conn)
        self.whereis[callsign] = (time.time(), conn)
        self.whereis[conn] = (time.time(), callsign)

    def reg_fetch_by_callsign(self, callsign: str) -> tuple[float, tuple[str, int]]:
        result = self.whereis[callsign]
        return (result[0], result[1])

    def reg_fetch_by_conn(self, conn: tuple[str, int]) -> tuple[float, str]:
        result = self.whereis[conn]
        return (result[0], str(result[1]))

    # def callsign_lookup( self, callsign):
    # for primary in self.primaries:
    # self.ask_where_is( callsign, primary )
    # def ask_where_is( self, callsign, server ):
    # addr = m17.address.Address.encode(callsign)
    # payload = json.dumps({"msgtype":"where is?", "m17_addr": addr }).encode("utf-8")
    # self.M17J_send(payload, server)
    # def answer_where_is( self, conn, callsign, loc ):
    # addr = m17.address.Address.encode(callsign)
    # payload = json.dumps({"msgtype":"is at", "m17_addr": addr, "host":loc[0] }).encode("utf-8")
    # self.rendezvous_send(payload, conn)

    # the rendezvous stuff starts here
    def request_rendezvous(self, callsign: str) -> None:
        payload = json.dumps({"msgtype": "introduce me?", "callsign": callsign}).encode("utf-8")
        for introducer in self.primaries:
            self.M17J_send(payload, introducer)

    def arrange_rendezvous(self, conn: tuple[str, int], msg: DictDotAttribute) -> None:
        # requires peer1 and peer2 both be connected live to self (e.g. keepalives)
        # sent to opposing peer with other sides host and expected port
        try:
            _, requestor_callsign = self.reg_fetch_by_conn(conn)
            target_callsign = msg.callsign
            _, theirconn = self.reg_fetch_by_callsign(msg.callsign)
        except KeyError as e:
            logging.error("Missing a registration, didn't find %s" % (e))
            return
        payload = json.dumps(
            {
                "msgtype": "introducing",
                "callsign": requestor_callsign,
                "host": conn[0],
                "port": conn[1],
            }
        ).encode("utf-8")
        self.M17J_send(
            payload, theirconn
        )  # this port needs to be from our existing list of connections appropriate to the _callsign_
        # we need to arrange the port too, don't we?
        payload = json.dumps(
            {
                "msgtype": "introducing",
                "callsign": target_callsign,
                "host": theirconn[0],
                "port": theirconn[1],
            }
        ).encode("utf-8")
        self.M17J_send(payload, conn)  # this one we can reply to directly, of course

    def attempt_rendezvous(self, conn: tuple[str, int], msg: DictDotAttribute) -> None:
        payload = json.dumps({"msgtype": "hi!", "callsign": self.callsign}).encode("utf-8")
        self.M17J_send(payload, (msg.host, msg.port))

    def have_link(self, callsign: str) -> Union[float, bool]:
        try:
            last, conn = self.reg_fetch_by_callsign(callsign)
            return time.time() - last  # <30
        except KeyError:
            return False

    def callsign_connect(self, callsign: str) -> None:
        self.request_rendezvous(callsign)

    def callsign_wait_connect(self, callsign: str) -> bool:
        self.callsign_connect(callsign)
        start = time.time()
        while not self.have_link(callsign):
            time.sleep(0.003)
            if time.time() - start > 3:
                return False
        # TODO now start the auto-keepalives here
        return True


async def repeat(
    interval: float, func: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any
) -> None:
    """Run func every interval seconds.

    If func has not finished before *interval*, will run again
    immediately when the previous iteration finished.

    *args and **kwargs are passed as the arguments to func.
    https://stackoverflow.com/a/55505152
    """
    while True:
        await asyncio.gather(
            func(*args, **kwargs),
            asyncio.sleep(interval),
        )


class m17_networking_dht:
    """https://github.com/bmuller/kademlia

    real p2p for callsign lookup and introductions?
    visualization tool for reading logs and a config to see packets and streams
        going back and forth between nodes, slowed down?

    bayeux style multicast for heavily linked reflectors?
    DHT multicast for reflectors in general
    So unicast comes into reflector, who then broadcasts it back out...

    handhelds should not need to run a DHT.
    DHT and other p2p stuff should be for servers, reflectors, etc - infrastructure
    handhelds and clients are not infrastructure.
    They should be able to join through any node in the network.
    one way to handle that would be to have the bootstrap node(s) also
    be DNS servers, where when you ask for a record it returns the result
    over DNS (and assume well-known ports), enabling compatibility with non-DHT applications?


    http://www.cs.columbia.edu/~jae/papers/bootstrap-paper-v3.2-icc11-camera.pdf
    borg https://engineering.purdue.edu/~ychu/publications/borg.pdf
    bayeux https://apps.dtic.mil/sti/pdfs/ADA603200.pdf
    https://inst.eecs.berkeley.edu//~cs268/sp03/notes/Lecture22.pdf
    http://www0.cs.ucl.ac.uk/staff/B.Karp/opendht-sigcomm2005.pdf
    https://sites.cs.ucsb.edu/~ravenben/talks/apis-1-03.pdf
    https://www.cs.cornell.edu/home/rvr/papers/willow.pdf
    http://p2p.cs.ucsb.edu/chimera/html/overview.html
    https://sites.cs.ucsb.edu/~ravenben/publications/pdf/tapestry_jsac.pdf
    http://p2p.cs.ucsb.edu/chimera/html/papers.html
    http://rowstron.azurewebsites.net/
    https://www2.eecs.berkeley.edu/Pubs/TechRpts/2001/CSD-01-1141.pdf
    http://p2p.cs.ucsb.edu/chimera/html/home.html
    http://p2p.cs.ucsb.edu/cashmere/
    http://p2p.cs.ucsb.edu/chimera/html/overview.html
    https://github.com/topics/distributed-hash-table?o=asc&s=stars
    https://github.com/bmuller/kademlia
    https://github.com/DivyanshuSaxena/Distributed-Hash-Tables
    http://citeseerx.ist.psu.edu/viewdoc/download?rep=rep1&type=pdf&doi=10.1.1.218.6222
    https://pdos.csail.mit.edu/~jinyang/pub/nsdi04.pdf
    https://dsf.berkeley.edu/papers/sigcomm05-placelab.pdf
    https://cs.baylor.edu/~donahoo/papers/MCD15.pdf
    https://github.com/ipfs/specs/blob/master/ARCHITECTURE.md
    http://www.cs.umd.edu/class/fall2015/cmsc417-0201/public/assignments/5.pdf
    http://citeseerx.ist.psu.edu/viewdoc/download?rep=rep1&type=pdf&doi=10.1.1.218.6222
    https://pdos.csail.mit.edu/~jinyang/pub/nsdi04.pdf
    https://dsf.berkeley.edu/papers/sigcomm05-placelab.pdf
    https://cs.baylor.edu/~donahoo/papers/MCD15.pdf

    """

    def __init__(
        self,
        callsign: str,
        myhost: str,
        port: int,
        bootstrap_nodes: Optional[list[tuple[str, int]]] = None,
    ) -> None:
        self.callsign = callsign
        self.host = myhost
        self.port = port
        self.bootstrap_nodes = bootstrap_nodes or []
        self.node: Server = Server()

    async def run(self) -> None:
        await self.node.listen(self.port)
        if self.bootstrap_nodes:
            await self.node.bootstrap(self.bootstrap_nodes)
        t1 = asyncio.ensure_future(repeat(15, self.register_me))
        t2 = asyncio.ensure_future(repeat(15, self.check))

    async def check(self) -> None:
        for c in ["", "-M", "-T", "-F"]:
            call = "W2FBI" + c
            x = await self.node.get(call)
            logger.debug("DHT check: %s -> %s", call, x)

    async def register_me(self) -> None:
        me = [self.host, self.port]
        jme = json.dumps(me)
        await self.node.set(self.callsign, jme)
        await self.node.set(jme, self.callsign)


if __name__ == "__main__":

    def loop_once(loop: asyncio.AbstractEventLoop) -> None:
        loop.stop()
        loop.run_forever()

    if sys.argv[1] == "dhtclient":

        async def run() -> None:
            server = Server()
            await server.listen(8469)
            bootstrap_node = (sys.argv[2], int(sys.argv[3]))
            await server.bootstrap([bootstrap_node])
            await server.set(sys.argv[4], sys.argv[5])
            server.stop()

        asyncio.run(run())
    elif sys.argv[1] == "dhtserver":
        loop = asyncio.get_event_loop()
        loop.set_debug(True)
        server = Server()
        loop.run_until_complete(server.listen(8468))
        try:
            while True:
                logger.debug("DHT server loop iteration")
                loop_once(loop)
                time.sleep(0.5)
            # loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.stop()
            loop.close()
    elif sys.argv[1] == "dht":
        callsign = sys.argv[2]
        host = sys.argv[3]
        # Parse bootstrap nodes from command line (optional)
        # Usage: python -m m17.network dht CALLSIGN HOST [bootstrap_host:port ...]
        bootstrap_nodes: list[tuple[str, int]] = []
        for arg in sys.argv[4:]:
            if ":" in arg:
                bhost, bport = arg.rsplit(":", 1)
                bootstrap_nodes.append((bhost, int(bport)))
        loop = asyncio.get_event_loop()
        x = m17_networking_dht(callsign, host, 17001, bootstrap_nodes if bootstrap_nodes else None)
        loop.run_until_complete(x.run())
        loop.set_debug(True)
        loop.run_forever()

    else:
        primaries = [("m17.programradios.com.", 17000)]
        callsign = sys.argv[1]
        if "-s" in sys.argv[2:]:
            portnum = 17000
        else:
            portnum = (int.from_bytes(m17.address.Address.encode(callsign), "big") % 32767) + 32767
        logger.info("Starting direct networking on port %d", portnum)
        direct_net = m17_networking_direct(primaries, callsign=callsign, port=portnum)
        direct_net.loop()

    # x.callsign_connect("W2FBI") #this is how you do an automatic udp hole punch.
    # #Registers the connection and maintains keepalives with that host. They should do the same.
    # x.have_link("W2FBI") #check if we are connected.
    # x.callsign_disco("W2FBI") #this is how you stop the keepalives and kill that connection (not implemented yet)
    # callsign_disco implies have_link will return False

    # hosts behind the same nat can expect failure when doing a direct call to each other, not exactly sure why - seems to be related to hairpin NATing

# spin this up on a public host for a demo like
# `python3 -m m17.network CALLSIGN -s`
# (and put the address of the public server in primaries like m17.programradios.com, above)

# demo clients should each `python3 -m m17.network UNIQUE_CALLSIGN`
# and then one can type x.connect_callsign(
