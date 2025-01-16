import os
import sys
import enum
import time
import json
import struct
import random
import logging
import unittest
import binascii
import socket

import queue
import threading

import asyncio
from kademlia.network import Server

import bitstruct
import m17
import m17.misc
from m17.misc import dattr
import m17.address

import requests

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


primaries = [("m17.tarxvf.tech.",17000)]
dhtbootstraps = [("m17dhtboot0.tarxvf.tech.", 17001)]

def m17ref_name2host(refname):
    return "%s.m17ref.tarxvf.tech"%(refname)

# def m17ref_name2dict(refname):
    # return "%s.m17ref.tarxvf.tech"%(refname)

class n7tae_reflector_conn:
    def __init__(self, sock, conn, mycallsign, theirmodule="A"):
        self.module = theirmodule
        self.sock = sock
        self.conn = conn
        self.mycallsign=mycallsign
        self.mycall_b = bytes(m17.address.Address(callsign=self.mycallsign))
        print("MYCALL=%s"%(self.mycallsign))
    def connect(self):
        data = b"CONN" + self.mycall_b + self.module.encode("ascii")
        self.send(data)
    def pong(self):
        data = b"PONG" + self.mycall_b 
        self.send(data)
    def disco(self):
        data = b"DISC" + self.mycall_b 
        self.send(data)
    def send(self,data):
        print("TAE SEND:",data)
        self.sock.sendto(data,self.conn)
    def handle(self,pkt,conn):
        if pkt.startswith(b"PING"):
            self.pong()
        elif pkt.startswith(b"ACKN"):
            pass #everything's fine
        elif pkt.startswith(b"NACK"):
            self.disco()
            raise(Exception("Refused by reflector"))
        elif pkt.startswith(b"CONN"):
            raise(NotImplementedError)
        else:
            print(pkt)
            raise(NotImplementedError)





class msgtype(enum.Enum):
    where_am_i  = 0 #remote host asks what their public IP is
    i_am_here  = 1 #remote host asks to tie their host and callsign together
    where_is = 2 #getting a query for a stored callsign
    is_at = 3 #getting a reply to a query
    introduce_me = 4 #got a request: please introduce me to host, i'm trying to talk to them on port...
    introducing = 5 #got an intro: I have an introduction for you, please contact ...
    hi = 6 #got an "oh hey" packet

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
    def __init__(self, primaries, callsign, port=17000):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind( ("0.0.0.0", port) )
        self.sock.setblocking(False)
        # self.sock.bind( ("::1", 17000) )

        self.recvQ = queue.Queue()
        self.sendQ = queue.Queue()
        network = threading.Thread(target=self.networker, args=(self.recvQ, self.sendQ))
        network.start()
 
        self.conns = {} #i was intending this for client side, not sure it makes sense

        self.whereis = {}

        self.primaries = primaries
        self.callsign = callsign
        self.m17_addr = m17.address.Address.encode(self.callsign)

        self.last = 0
        self.registration_keepalive_period = 25
        self.connection_timeout = 25

    def networker(self, recvq, sendq):
        """
        """
        while 1:
            try:
                data,conn = self.sock.recvfrom(1500)
                print("RECV",conn, data)
                recvq.put((data,conn))
            except BlockingIOError as e:
                pass
            if not sendq.empty():
                data,conn = sendq.get_nowait()
                print("SEND",conn, data)
                self.sock.sendto(data,conn)
            time.sleep(.0001)

    def loop(self):
        def looper(self):
            while 1:
                self.loop_once()
                time.sleep(.005)
        self.looper = threading.Thread(target=looper, args=(self,))
        self.looper.start()

    def clean_conns(self):
        ...
        # self.conns = {conn: data for conn, data in self.conns if time.time() - data.last > self.connection_timeout}

    def loop_once(self):
        self.registration_keepalive()
        if not self.recvQ.empty():
            data,conn = self.recvQ.get_nowait()
            print("Recv:", data,conn)
            if conn[0] not in self.conns:
                self.conns[ conn ] = dattr({
                    "last": time.time(),
                    "conn": conn,
                        })
                print(self.conns)
            else:
                self.conns[ conn[0] ].last = time.time()
            self.process_packet( data, conn )
        # self.clean_conns()
        # self.clean_whereis()

    def M17J_send(self, payload, conn):
        # print("Sending to %s M17J %s"%(conn,payload))
        self.sendQ.put((b"M17J" + payload, conn))

    def process_packet(self, payload, conn):
        if payload.startswith(b"M17 "):
            ...
            #voice and data packets
        elif payload.startswith(b"M17J"): #M17 Json development and evaluation protocol - the standard is, there is no standard
            msg = dattr(json.loads(payload[4:].decode("utf-8")))
            if msg.msgtype == msgtype.where_am_i: 
                self.reg_store(msg.callsign, conn) #so we store it
            elif msg.msgtype == msgtype.i_am_here: 
                self.reg_store(msg.callsign, conn) #so we store it
            elif msg.msgtype == msgtype.where_is:
                lastseen,theirconn = self.reg_fetch( callsign )
                self.answer_where_is( conn, callsign, theirconn)
            elif msg.msgtype == msgtype.is_at:
                print("Found %s at %s!"%(msg.callsign, msg.host))
                self.reg_store(msg.callsign, (msg.host,msg.port))

            elif msg.msgtype == msgtype.introduce_me: 
                self.arrange_rendezvous(conn,msg)
            elif msg.msgtype == msgtype.introducing: 
                self.attempt_rendezvous(conn,msg)
            elif msg.msgtype == msgtype.hi:
                print("Got a holepunch packet from %s!"%(str(conn)))
                self.reg_store(msg.callsign, conn)
        else:
            print("payload unrecognized")
            print("payload = ",payload)
            import pdb; pdb.set_trace()


    #user registration handling starts here
    def registration_keepalive(self):
        """
        Periodically re-register
        """
        if not self.callsign:
            return
        sincelastrun = time.time() - self.last
        if sincelastrun > self.registration_keepalive_period:
            for primary in primaries:
                self.register_me_with( primary )
            self.last = time.time()

    def register_me_with(self, server):
        payload = json.dumps({"msgtype":"i am here", "callsign": self.callsign }).encode("utf-8")
        self.M17J_send(payload, server)

    def reg_store(self, callsign, conn):
        print("[M17 registration] %s -> %s"%(callsign, conn))
        self.whereis[ callsign ] = (time.time(), conn)
        self.whereis[ conn ] = (time.time(), callsign)

    def reg_fetch_by_callsign( self, callsign ):
        return self.whereis[callsign]

    def reg_fetch_by_conn( self, conn ):
        return self.whereis[conn]

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

    #the rendezvous stuff starts here
    def request_rendezvous(self, callsign):
        payload = json.dumps({"msgtype":"introduce me?", "callsign": callsign }).encode("utf-8")
        for introducer in self.primaries:
            self.M17J_send(payload, introducer)
    
    def arrange_rendezvous(self, conn, msg):
        # requires peer1 and peer2 both be connected live to self (e.g. keepalives)
        #sent to opposing peer with other sides host and expected port
        try:
            _,requestor_callsign = self.reg_fetch_by_conn(conn)
            target_callsign = msg.callsign
            _,theirconn = self.reg_fetch_by_callsign(msg.callsign)
        except KeyError as e:
            logging.error("Missing a registration, didn't find %s"%(e))
            return
        payload = json.dumps({"msgtype":"introducing", "callsign": requestor_callsign, "host": conn[0], "port":conn[1] }).encode("utf-8")
        self.M17J_send(payload, theirconn) #this port needs to be from our existing list of connections appropriate to the _callsign_
        #we need to arrange the port too, don't we? 
        payload = json.dumps({"msgtype":"introducing", "callsign": target_callsign, "host": theirconn[0], "port":theirconn[1] }).encode("utf-8")
        self.M17J_send(payload, conn) #this one we can reply to directly, of course

    def attempt_rendezvous(self, conn, msg):
        payload = json.dumps({"msgtype":"hi!", "callsign": self.callsign}).encode("utf-8")
        self.M17J_send(payload, (msg.host,msg.port))

    def have_link(self, callsign):
        try:
            last,conn = self.reg_fetch_by_callsign(callsign)
            return time.time() - last #<30
        except KeyError as e:
            return False

    def callsign_connect(self, callsign):
        self.request_rendezvous(callsign)

    def callsign_wait_connect(self, callsign):
        self.callsign_connect(callsign)
        start = time.time()
        while not self.have_link(callsign):
            time.sleep(.003)
            if time.time() - start > 3:
                return False
        #TODO now start the auto-keepalives here
        return True

async def repeat(interval, func, *args, **kwargs):
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
    """
    https://github.com/bmuller/kademlia


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
    def __init__(self, callsign, myhost, port, should_boot=True):
        self.callsign = callsign
        self.host = myhost
        self.port = port
        self.should_boot = should_boot
        self.node = Server()

    async def run(self):
        await self.node.listen(self.port)
        if self.should_boot:
            await self.node.bootstrap([
                ("m17dhtboot0.tarxvf.tech", 17001),
                # ("m17dhtboot1.tarxvf.tech", 17001)
                ])
        t1 = asyncio.ensure_future(repeat(15, self.register_me))
        t2 = asyncio.ensure_future(repeat(15, self.check))

    async def check(self):
        for c in ["","-M","-T","-F"]:
            call = "W2FBI" + c
            x = await self.node.get(call)
            print(call,x)
        
    async def register_me(self):
        me = [self.host,self.port]
        jme = json.dumps(me)
        await self.node.set( self.callsign, jme)
        await self.node.set( jme , self.callsign)

if __name__ == "__main__":
    def loop_once(loop):
        loop.stop()
        loop.run_forever()
    if sys.argv[1] == "dhtclient":
        async def run():
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
            while 1:
                print("test")
                loop_once(loop)
                time.sleep(.5)
            # loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.stop()
            loop.close()
    elif sys.argv[1] == "dht":
        callsign = sys.argv[2]
        host = sys.argv[3] 
        #curl ident.me, or should check with dht bootstrapping nodes
        should_boot = bool(sys.argv[4].lower() in ["true","yes","1"])
        loop = asyncio.get_event_loop()
        x=m17_networking_dht(callsign,host,should_boot)
        loop.run_until_complete(x.run())
        loop.set_debug(True)
        loop.run_forever()

    else:
        primaries = [("m17.programradios.com.",17000)]
        callsign = sys.argv[1]
        if "-s" in sys.argv[2:]:
            portnum = 17000
        else:
            portnum = (m17.address.Address.encode(callsign) % 32767) + 32767
        print(portnum)
        x = m17_networking_direct(primaries, callsign=callsign, port=portnum )
        x.loop()
        import pdb; pdb.set_trace()

    # x.callsign_connect("W2FBI") #this is how you do an automatic udp hole punch. 
    # #Registers the connection and maintains keepalives with that host. They should do the same.
    # x.have_link("W2FBI") #check if we are connected.
    # x.callsign_disco("W2FBI") #this is how you stop the keepalives and kill that connection (not implemented yet)
    # callsign_disco implies have_link will return False

    #hosts behind the same nat can expect failure when doing a direct call to each other, not exactly sure why - seems to be related to hairpin NATing


#spin this up on a public host for a demo like 
#`python3 -m m17.network CALLSIGN -s`
# (and put the address of the public server in primaries like m17.programradios.com, above) 

# demo clients should each `python3 -m m17.network UNIQUE_CALLSIGN` 
# and then one can type x.connect_callsign(
