"""M17 High-Level Network Client

Provides a unified async interface for M17 networking,
combining reflector, DHT, and P2P capabilities.
"""

from __future__ import annotations

import logging
import random
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from typing import Optional

from m17.core.address import Address
from m17.frames.ip import IPFrame
from m17.frames.lsf import LinkSetupFrame

__all__ = [
    "M17NetworkClient",
    "M17ClientConfig",
]

logger = logging.getLogger(__name__)


@dataclass
class M17ClientConfig:
    """M17 client configuration.

    Attributes
    ----------
        callsign: Local callsign.
        reflector_host: Default reflector host.
        reflector_port: Default reflector port.
        reflector_module: Default reflector module.
        dht_enabled: Enable DHT routing.
        dht_port: DHT port.
        p2p_enabled: Enable P2P connections.
        p2p_port: P2P port.
    """

    callsign: str
    reflector_host: Optional[str] = None
    reflector_port: int = 17000
    reflector_module: str = "A"
    dht_enabled: bool = False
    dht_port: int = 17001
    p2p_enabled: bool = False
    p2p_port: int = 17000


class M17NetworkClient:
    """High-level M17 network client.

    Provides a unified interface for:
    - Connecting to reflectors
    - Sending/receiving M17 frames
    - Stream management

    Example:
    -------
        config = M17ClientConfig(
            callsign="N0CALL",
            reflector_host="m17-usa.example.com"
        )

        async with M17NetworkClient(config) as client:
            await client.connect()

            # Send a voice stream
            async with client.stream("W2FBI") as stream:
                for frame in audio_frames:
                    await stream.send(frame)
    """

    def __init__(self, config: M17ClientConfig) -> None:
        """Initialize client.

        Args:
        ----
            config: Client configuration.
        """
        self.config = config
        self._reflector = None
        self._dht = None
        self._p2p = None
        self._running = False
        self._frame_handlers: list[Callable[[IPFrame], None]] = []

    async def __aenter__(self) -> M17NetworkClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

    @property
    def callsign(self) -> str:
        """Get local callsign."""
        return self.config.callsign

    @property
    def is_connected(self) -> bool:
        """Check if connected to any network."""
        if self._reflector:
            from m17.net.reflector import M17ReflectorClient

            if isinstance(self._reflector, M17ReflectorClient):
                return self._reflector.is_connected
        return False

    async def connect(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        module: Optional[str] = None,
    ) -> bool:
        """Connect to reflector.

        Args:
        ----
            host: Reflector host (uses config default if not specified).
            port: Reflector port.
            module: Reflector module.

        Returns:
        -------
            True if connected successfully.
        """
        from m17.net.reflector import M17ReflectorClient

        host = host or self.config.reflector_host
        port = port or self.config.reflector_port
        module = module or self.config.reflector_module

        if not host:
            raise ValueError("No reflector host specified")

        self._reflector = M17ReflectorClient(self.config.callsign)
        result = await self._reflector.connect(host, port, module)

        if result:
            self._running = True
            logger.info(f"Connected to reflector {host}:{port} module {module}")

        return result

    async def disconnect(self) -> None:
        """Disconnect from all networks."""
        self._running = False

        if self._reflector:
            await self._reflector.disconnect()
            self._reflector = None

        if self._dht:
            await self._dht.stop()
            self._dht = None

        if self._p2p:
            await self._p2p.stop()
            self._p2p = None

        logger.info("Disconnected")

    def add_frame_handler(self, handler: Callable[[IPFrame], None]) -> None:
        """Add a frame handler.

        Args:
        ----
            handler: Function to call with received frames.
        """
        self._frame_handlers.append(handler)

    def remove_frame_handler(self, handler: Callable[[IPFrame], None]) -> None:
        """Remove a frame handler.

        Args:
        ----
            handler: Handler to remove.
        """
        if handler in self._frame_handlers:
            self._frame_handlers.remove(handler)

    async def send_frame(self, frame: IPFrame) -> None:
        """Send an M17 frame.

        Args:
        ----
            frame: Frame to send.
        """
        if self._reflector and self._reflector.is_connected:
            await self._reflector.send_frame(frame)

    async def receive_frames(self) -> AsyncGenerator[IPFrame, None]:
        """Async generator for received frames.

        Yields
        ------
            Received IPFrame objects.
        """
        if not self._reflector:
            return

        async for frame in self._reflector.receive_frames():
            # Call handlers
            for handler in self._frame_handlers:
                try:
                    handler(frame)
                except Exception as e:
                    logger.warning(f"Frame handler error: {e}")

            yield frame

    def stream(
        self,
        destination: str,
        stream_type: int = 0x0005,
        nonce: Optional[bytes] = None,
    ) -> StreamContext:
        """Create a stream context for sending.

        Args:
        ----
            destination: Destination callsign.
            stream_type: TYPE field value.
            nonce: Optional META/nonce field.

        Returns:
        -------
            StreamContext for sending frames.

        Example:
        -------
            async with client.stream("W2FBI") as stream:
                await stream.send(payload_bytes)
        """
        return StreamContext(
            client=self,
            destination=destination,
            source=self.config.callsign,
            stream_type=stream_type,
            nonce=nonce,
        )


class StreamContext:
    """Context manager for M17 stream transmission.

    Manages stream ID, frame numbering, and EOT signaling.
    """

    def __init__(
        self,
        client: M17NetworkClient,
        destination: str,
        source: str,
        stream_type: int = 0x0005,
        nonce: Optional[bytes] = None,
    ) -> None:
        """Initialize stream context."""
        self.client = client
        self.destination = destination
        self.source = source
        self.stream_type = stream_type
        self.nonce = nonce or bytes(14)
        self._stream_id = random.randint(1, 0xFFFF)
        self._frame_number = 0
        self._lsf: Optional[LinkSetupFrame] = None

    async def __aenter__(self) -> StreamContext:
        """Start the stream."""
        self._lsf = LinkSetupFrame(
            dst=Address(callsign=self.destination),
            src=Address(callsign=self.source),
            type_field=self.stream_type,
            meta=self.nonce,
        )
        self._frame_number = 0
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """End the stream with EOT."""
        # Send EOT frame
        await self.send(bytes(16), is_last=True)

    @property
    def stream_id(self) -> int:
        """Get stream ID."""
        return self._stream_id

    @property
    def frame_number(self) -> int:
        """Get current frame number."""
        return self._frame_number

    async def send(self, payload: bytes, is_last: bool = False) -> None:
        """Send a payload frame.

        Args:
        ----
            payload: 16-byte payload data.
            is_last: True if this is the last frame.
        """
        if len(payload) != 16:
            if len(payload) < 16:
                payload = payload + bytes(16 - len(payload))
            else:
                payload = payload[:16]

        frame_num = self._frame_number
        if is_last:
            frame_num |= 0x8000

        frame = IPFrame.create(
            dst=self.destination,
            src=self.source,
            stream_id=self._stream_id,
            stream_type=self.stream_type,
            nonce=self.nonce,
            frame_number=frame_num,
            payload=payload,
        )

        await self.client.send_frame(frame)
        self._frame_number = (self._frame_number + 1) & 0x7FFF
