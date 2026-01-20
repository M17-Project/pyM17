"""M17 Reflector Protocol (n7tae)

Implements the n7tae reflector protocol for M17-over-IP.

Protocol messages:
- CONN: Connect to reflector (callsign + module)
- DISC: Disconnect from reflector
- PING: Keep-alive request from reflector
- PONG: Keep-alive response to reflector
- ACKN: Connection acknowledged
- NACK: Connection refused
- M17 : Stream data frame

Refactored from network.py with improved structure and type hints.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import time
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from m17.core.address import Address
from m17.frames.ip import IPFrame

__all__ = [
    "ReflectorConnection",
    "ReflectorProtocol",
    "M17ReflectorClient",
    "ReflectorMessage",
    "ConnectionState",
]

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Reflector connection state."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    ERROR = "error"


class ReflectorMessage(Enum):
    """Reflector protocol message types."""

    CONN = b"CONN"
    DISC = b"DISC"
    PING = b"PING"
    PONG = b"PONG"
    ACKN = b"ACKN"
    NACK = b"NACK"
    M17_FRAME = b"M17 "


@dataclass
class ReflectorProtocol:
    """Low-level reflector protocol handler.

    Handles encoding/decoding of reflector protocol messages.
    """

    callsign: str
    _callsign_bytes: bytes = field(init=False)

    def __post_init__(self) -> None:
        """Initialize callsign bytes."""
        addr = Address(callsign=self.callsign)
        self._callsign_bytes = bytes(addr)

    def make_connect(self, module: str = "A") -> bytes:
        """Create CONN message.

        Args:
        ----
            module: Reflector module (A-Z).

        Returns:
        -------
            CONN message bytes.
        """
        if len(module) != 1 or not module.isalpha():
            raise ValueError(f"Module must be single letter A-Z, got {module!r}")
        return b"CONN" + self._callsign_bytes + module.upper().encode("ascii")

    def make_disconnect(self) -> bytes:
        """Create DISC message.

        Returns
        -------
            DISC message bytes.
        """
        return b"DISC" + self._callsign_bytes

    def make_pong(self) -> bytes:
        """Create PONG message.

        Returns
        -------
            PONG message bytes.
        """
        return b"PONG" + self._callsign_bytes

    @staticmethod
    def parse_message(data: bytes) -> tuple[ReflectorMessage, bytes]:
        """Parse a received message.

        Args:
        ----
            data: Received bytes.

        Returns:
        -------
            Tuple of (message type, payload).

        Raises:
        ------
            ValueError: If message is unknown.
        """
        if len(data) < 4:
            raise ValueError(f"Message too short: {len(data)} bytes")

        prefix = data[:4]
        payload = data[4:]

        for msg_type in ReflectorMessage:
            if prefix == msg_type.value:
                return msg_type, payload

        raise ValueError(f"Unknown message type: {prefix!r}")


@dataclass
class ReflectorConnection:
    """Manages a connection to an M17 reflector.

    Handles connection state, keep-alives, and message handling.

    Attributes
    ----------
        host: Reflector hostname or IP.
        port: Reflector port (default 17000).
        callsign: Local callsign.
        module: Reflector module (A-Z).
    """

    host: str
    port: int = 17000
    callsign: str = "N0CALL"
    module: str = "A"

    _sock: Optional[socket.socket] = field(default=None, init=False)
    _protocol: ReflectorProtocol = field(init=False)
    _state: ConnectionState = field(default=ConnectionState.DISCONNECTED, init=False)
    _last_ping: float = field(default=0.0, init=False)
    _frame_callback: Optional[Callable[[IPFrame], None]] = field(default=None, init=False)

    def __post_init__(self) -> None:
        """Initialize protocol handler."""
        self._protocol = ReflectorProtocol(self.callsign)

    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if connected to reflector."""
        return self._state == ConnectionState.CONNECTED

    @property
    def addr(self) -> tuple[str, int]:
        """Get reflector address tuple."""
        return (self.host, self.port)

    def set_frame_callback(self, callback: Callable[[IPFrame], None]) -> None:
        """Set callback for received M17 frames.

        Args:
        ----
            callback: Function to call with received IPFrame.
        """
        self._frame_callback = callback

    def connect(self, timeout: float = 5.0) -> bool:
        """Connect to the reflector.

        Args:
        ----
            timeout: Connection timeout in seconds.

        Returns:
        -------
            True if connected successfully.
        """
        if self._state != ConnectionState.DISCONNECTED:
            logger.warning("Already connected or connecting")
            return False

        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.settimeout(timeout)
            self._sock.bind(("0.0.0.0", 0))

            self._state = ConnectionState.CONNECTING

            # Send CONN message
            conn_msg = self._protocol.make_connect(self.module)
            self._send(conn_msg)
            logger.info(f"Connecting to {self.host}:{self.port} module {self.module}")

            # Wait for ACKN
            start = time.time()
            while time.time() - start < timeout:
                try:
                    data, addr = self._sock.recvfrom(1500)
                    msg_type, payload = ReflectorProtocol.parse_message(data)

                    if msg_type == ReflectorMessage.ACKN:
                        self._state = ConnectionState.CONNECTED
                        logger.info(f"Connected to reflector {self.host}")
                        return True
                    elif msg_type == ReflectorMessage.NACK:
                        self._state = ConnectionState.ERROR
                        logger.error("Connection refused by reflector")
                        return False

                except socket.timeout:
                    continue

            self._state = ConnectionState.ERROR
            logger.error("Connection timeout")
            return False

        except Exception as e:
            self._state = ConnectionState.ERROR
            logger.error(f"Connection error: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from the reflector."""
        if self._sock is None:
            return

        if self._state == ConnectionState.CONNECTED:
            try:
                disc_msg = self._protocol.make_disconnect()
                self._send(disc_msg)
            except Exception:
                pass

        self._state = ConnectionState.DISCONNECTED
        self._sock.close()
        self._sock = None
        logger.info("Disconnected from reflector")

    def _send(self, data: bytes) -> None:
        """Send data to reflector."""
        if self._sock is None:
            raise RuntimeError("Not connected")
        self._sock.sendto(data, self.addr)
        logger.debug(f"SEND: {data[:4]!r} ({len(data)} bytes)")

    def send_frame(self, frame: IPFrame) -> None:
        """Send an M17 frame to the reflector.

        Args:
        ----
            frame: IPFrame to send.
        """
        if not self.is_connected:
            raise RuntimeError("Not connected")
        self._send(bytes(frame))

    def handle_message(self, data: bytes) -> Optional[IPFrame]:
        """Handle a received message.

        Args:
        ----
            data: Received bytes.

        Returns:
        -------
            IPFrame if message was M17 data, None otherwise.
        """
        try:
            msg_type, payload = ReflectorProtocol.parse_message(data)
        except ValueError as e:
            logger.warning(f"Unknown message: {e}")
            return None

        if msg_type == ReflectorMessage.PING:
            self._send(self._protocol.make_pong())
            self._last_ping = time.time()
            logger.debug("Responded to PING")

        elif msg_type == ReflectorMessage.ACKN:
            logger.debug("Received ACKN")

        elif msg_type == ReflectorMessage.NACK:
            logger.warning("Received NACK")
            self._state = ConnectionState.ERROR

        elif msg_type == ReflectorMessage.M17_FRAME:
            try:
                frame = IPFrame.from_bytes(data)
                if self._frame_callback:
                    self._frame_callback(frame)
                return frame
            except Exception as e:
                logger.warning(f"Failed to parse M17 frame: {e}")

        return None

    def poll(self, timeout: float = 0.1) -> Optional[IPFrame]:
        """Poll for incoming messages.

        Args:
        ----
            timeout: Poll timeout in seconds.

        Returns:
        -------
            IPFrame if received, None otherwise.
        """
        if self._sock is None:
            return None

        try:
            self._sock.settimeout(timeout)
            data, addr = self._sock.recvfrom(1500)
            return self.handle_message(data)
        except socket.timeout:
            return None
        except Exception as e:
            logger.warning(f"Poll error: {e}")
            return None


class M17ReflectorClient:
    """High-level async M17 reflector client.

    Provides an async interface for connecting to and communicating
    with M17 reflectors.

    Example:
    -------
        async with M17ReflectorClient("N0CALL") as client:
            await client.connect("m17-usa.example.com", module="A")
            async for frame in client.receive_frames():
                print(f"Received: {frame}")
    """

    def __init__(self, callsign: str) -> None:
        """Initialize client.

        Args:
        ----
            callsign: Local callsign.
        """
        self.callsign = callsign
        self._conn: Optional[ReflectorConnection] = None
        self._running = False

    async def __aenter__(self) -> M17ReflectorClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

    async def connect(
        self,
        host: str,
        port: int = 17000,
        module: str = "A",
        timeout: float = 5.0,
    ) -> bool:
        """Connect to a reflector.

        Args:
        ----
            host: Reflector hostname or IP.
            port: Reflector port.
            module: Reflector module (A-Z).
            timeout: Connection timeout.

        Returns:
        -------
            True if connected.
        """
        self._conn = ReflectorConnection(
            host=host,
            port=port,
            callsign=self.callsign,
            module=module,
        )

        # Run blocking connect in executor
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._conn.connect, timeout)
        self._running = result
        return result

    async def disconnect(self) -> None:
        """Disconnect from reflector."""
        self._running = False
        if self._conn:
            self._conn.disconnect()
            self._conn = None

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._conn is not None and self._conn.is_connected

    async def send_frame(self, frame: IPFrame) -> None:
        """Send an M17 frame.

        Args:
        ----
            frame: Frame to send.
        """
        if not self._conn:
            raise RuntimeError("Not connected")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._conn.send_frame, frame)

    async def receive_frames(self, poll_interval: float = 0.01) -> AsyncGenerator[IPFrame, None]:
        """Async generator for received frames.

        Args:
        ----
            poll_interval: Poll interval in seconds.

        Yields:
        ------
            Received IPFrame objects.
        """
        if not self._conn:
            raise RuntimeError("Not connected")

        loop = asyncio.get_event_loop()

        while self._running and self._conn.is_connected:
            frame = await loop.run_in_executor(None, self._conn.poll, poll_interval)
            if frame:
                yield frame
            else:
                await asyncio.sleep(poll_interval)


# Legacy class name for backward compatibility
n7tae_reflector_conn = ReflectorConnection
