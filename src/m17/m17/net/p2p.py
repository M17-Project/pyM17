"""
M17 Peer-to-Peer Direct Connections

Implements direct P2P connections between M17 nodes with NAT traversal.

Uses UDP hole punching for NAT traversal with help from
a rendezvous server.

Refactored from network.py with improved structure and type hints.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Tuple

from m17.core.address import Address
from m17.core.constants import DEFAULT_PORT
from m17.frames.ip import IPFrame

__all__ = [
    "P2PConnection",
    "P2PManager",
    "MessageType",
]

logger = logging.getLogger(__name__)


class MessageType(IntEnum):
    """P2P message types."""

    WHERE_AM_I = 0  # Request own external IP
    I_AM_HERE = 1  # Register callsign with server
    WHERE_IS = 2  # Query for callsign location
    IS_AT = 3  # Response to WHERE_IS
    INTRODUCE_ME = 4  # Request introduction to another peer
    INTRODUCING = 5  # Introduction response
    HI = 6  # Hole punch acknowledgment


@dataclass
class P2PConnection:
    """
    Represents a P2P connection to another M17 node.

    Attributes:
        callsign: Remote callsign.
        addr: Remote (host, port) tuple.
        last_seen: Timestamp of last activity.
    """

    callsign: str
    addr: Tuple[str, int]
    last_seen: float = field(default_factory=time.time)

    def is_active(self, timeout: float = 30.0) -> bool:
        """Check if connection is still active."""
        return time.time() - self.last_seen < timeout

    def touch(self) -> None:
        """Update last seen timestamp."""
        self.last_seen = time.time()


@dataclass
class P2PManager:
    """
    Manages P2P connections to other M17 nodes.

    Handles NAT traversal through UDP hole punching and
    maintains connection state.

    Attributes:
        callsign: Local callsign.
        primaries: List of rendezvous server addresses (required).
        port: Local port.
    """

    callsign: str
    primaries: List[Tuple[str, int]]
    port: int = DEFAULT_PORT

    _sock: Optional[socket.socket] = field(default=None, init=False)
    _connections: Dict[str, P2PConnection] = field(default_factory=dict, init=False)
    _whereis: Dict[str, Tuple[float, Tuple[str, int]]] = field(
        default_factory=dict, init=False
    )
    _running: bool = field(default=False, init=False)
    _last_registration: float = field(default=0.0, init=False)
    _registration_interval: float = 25.0
    _connection_timeout: float = 25.0
    _frame_callback: Optional[Callable[[IPFrame, Tuple[str, int]], None]] = field(
        default=None, init=False
    )

    def __post_init__(self) -> None:
        """Initialize socket and address."""
        if not self.primaries:
            raise ValueError(
                "primaries is required: list of (host, port) tuples for rendezvous servers"
            )
        self._callsign_addr = Address.encode(self.callsign)

    async def start(self) -> None:
        """Start the P2P manager."""
        if self._running:
            return

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(("0.0.0.0", self.port))
        self._sock.setblocking(False)

        self._running = True
        logger.info(f"P2P manager started on port {self.port}")

    async def stop(self) -> None:
        """Stop the P2P manager."""
        self._running = False
        if self._sock:
            self._sock.close()
            self._sock = None
        self._connections.clear()
        logger.info("P2P manager stopped")

    def set_frame_callback(
        self, callback: Callable[[IPFrame, Tuple[str, int]], None]
    ) -> None:
        """Set callback for received M17 frames."""
        self._frame_callback = callback

    def _send(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Send data to address."""
        if self._sock:
            self._sock.sendto(data, addr)
            logger.debug(f"SEND to {addr}: {len(data)} bytes")

    def _send_json(self, msg: Dict[str, Any], addr: Tuple[str, int]) -> None:
        """Send JSON message to address."""
        payload = b"M17J" + json.dumps(msg).encode("utf-8")
        self._send(payload, addr)

    async def register(self) -> None:
        """Register with primary servers."""
        msg = {"msgtype": MessageType.I_AM_HERE, "callsign": self.callsign}
        for primary in self.primaries:
            self._send_json(msg, primary)
        self._last_registration = time.time()

    async def lookup(self, callsign: str) -> Optional[Tuple[str, int]]:
        """
        Look up a callsign location.

        Args:
            callsign: Callsign to look up.

        Returns:
            (host, port) if found, None otherwise.
        """
        # Check cache first
        if callsign in self._whereis:
            timestamp, addr = self._whereis[callsign]
            if time.time() - timestamp < self._connection_timeout:
                return addr

        # Query primaries
        msg = {"msgtype": MessageType.WHERE_IS, "callsign": callsign}
        for primary in self.primaries:
            self._send_json(msg, primary)

        return None

    async def request_introduction(self, target_callsign: str) -> None:
        """
        Request introduction to another node.

        Asks rendezvous servers to introduce us to the target.

        Args:
            target_callsign: Callsign to connect to.
        """
        msg = {"msgtype": MessageType.INTRODUCE_ME, "callsign": target_callsign}
        for primary in self.primaries:
            self._send_json(msg, primary)
        logger.info(f"Requested introduction to {target_callsign}")

    async def connect(self, callsign: str, timeout: float = 3.0) -> bool:
        """
        Establish P2P connection to a callsign.

        Uses NAT hole punching via rendezvous servers.

        Args:
            callsign: Target callsign.
            timeout: Connection timeout.

        Returns:
            True if connection established.
        """
        await self.request_introduction(callsign)

        start = time.time()
        while time.time() - start < timeout:
            if callsign in self._connections:
                if self._connections[callsign].is_active():
                    return True
            await asyncio.sleep(0.01)

        return False

    def has_connection(self, callsign: str) -> bool:
        """Check if we have an active connection to callsign."""
        if callsign in self._connections:
            conn = self._connections[callsign]
            if conn.is_active(self._connection_timeout):
                return True
            # Cleanup stale connection
            del self._connections[callsign]
        return False

    async def send_frame(self, frame: IPFrame, callsign: str) -> bool:
        """
        Send a frame to a callsign.

        Args:
            frame: IPFrame to send.
            callsign: Target callsign.

        Returns:
            True if sent successfully.
        """
        if not self.has_connection(callsign):
            logger.warning(f"No connection to {callsign}")
            return False

        conn = self._connections[callsign]
        self._send(bytes(frame), conn.addr)
        return True

    def _handle_json_message(
        self, msg: Dict[str, Any], addr: Tuple[str, int]
    ) -> None:
        """Handle received JSON message."""
        msg_type = msg.get("msgtype")

        if msg_type == MessageType.WHERE_AM_I:
            # Store their registration
            callsign = msg.get("callsign")
            if callsign:
                self._store_location(callsign, addr)

        elif msg_type == MessageType.I_AM_HERE:
            callsign = msg.get("callsign")
            if callsign:
                self._store_location(callsign, addr)

        elif msg_type == MessageType.IS_AT:
            callsign = msg.get("callsign")
            host = msg.get("host")
            port = msg.get("port", 17000)
            if callsign and host:
                logger.info(f"Found {callsign} at {host}:{port}")
                self._store_location(callsign, (host, port))

        elif msg_type == MessageType.INTRODUCING:
            # Received introduction - attempt hole punch
            callsign = msg.get("callsign")
            host = msg.get("host")
            port = msg.get("port")
            if callsign and host and port:
                # Send hi message to punch hole
                hi_msg = {"msgtype": MessageType.HI, "callsign": self.callsign}
                self._send_json(hi_msg, (host, port))
                logger.info(f"Attempting hole punch to {callsign} at {host}:{port}")

        elif msg_type == MessageType.HI:
            # Hole punch successful
            callsign = msg.get("callsign")
            if callsign:
                self._connections[callsign] = P2PConnection(callsign, addr)
                self._store_location(callsign, addr)
                logger.info(f"P2P connection established with {callsign}")

    def _store_location(self, callsign: str, addr: Tuple[str, int]) -> None:
        """Store callsign -> location mapping."""
        self._whereis[callsign] = (time.time(), addr)
        self._whereis[addr] = (time.time(), callsign)

    async def poll(self) -> None:
        """Poll for incoming messages."""
        if not self._sock:
            return

        # Check if we need to re-register
        if time.time() - self._last_registration > self._registration_interval:
            await self.register()

        try:
            data, addr = self._sock.recvfrom(1500)

            if data.startswith(b"M17 "):
                # M17 frame
                try:
                    frame = IPFrame.from_bytes(data)
                    if self._frame_callback:
                        self._frame_callback(frame, addr)
                except Exception as e:
                    logger.warning(f"Failed to parse M17 frame: {e}")

            elif data.startswith(b"M17J"):
                # JSON message
                try:
                    msg = json.loads(data[4:].decode("utf-8"))
                    self._handle_json_message(msg, addr)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON message from {addr}")

        except BlockingIOError:
            pass  # No data available
        except Exception as e:
            logger.warning(f"Poll error: {e}")


# Legacy class alias
m17_networking_direct = P2PManager
