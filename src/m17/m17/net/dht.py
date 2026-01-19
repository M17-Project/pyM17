"""
M17 DHT-based Routing

Implements Kademlia DHT for decentralized M17 routing and discovery.

Uses the kademlia library for the underlying DHT implementation.

Refactored from network.py with improved structure and type hints.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from kademlia.network import Server
    HAS_KADEMLIA = True
except ImportError:
    HAS_KADEMLIA = False
    Server = None

from m17.core.constants import DEFAULT_DHT_BOOTSTRAP_HOSTS, DEFAULT_DHT_PORT

__all__ = [
    "M17DHTNode",
    "DHTConfig",
    "HAS_KADEMLIA",
]

logger = logging.getLogger(__name__)

# Default bootstrap nodes (from m17.core.constants)
DEFAULT_BOOTSTRAP_NODES: List[Tuple[str, int]] = [
    (host, DEFAULT_DHT_PORT) for host in DEFAULT_DHT_BOOTSTRAP_HOSTS
]


@dataclass
class DHTConfig:
    """
    DHT configuration.

    Attributes:
        port: Local DHT port.
        bootstrap_nodes: List of (host, port) tuples for bootstrapping.
        registration_interval: Seconds between re-registration.
    """

    port: int = 17001
    bootstrap_nodes: List[Tuple[str, int]] = field(
        default_factory=lambda: list(DEFAULT_BOOTSTRAP_NODES)
    )
    registration_interval: float = 15.0


@dataclass
class M17DHTNode:
    """
    M17 DHT Node.

    Provides DHT-based callsign routing and discovery.

    Example:
        async with M17DHTNode("N0CALL", "192.168.1.100") as node:
            await node.start()
            location = await node.lookup("W2FBI")
            print(f"W2FBI is at {location}")
    """

    callsign: str
    host: str
    config: DHTConfig = field(default_factory=DHTConfig)
    _server: Any = field(default=None, init=False)
    _running: bool = field(default=False, init=False)
    _register_task: Optional[asyncio.Task] = field(default=None, init=False)

    def __post_init__(self) -> None:
        """Validate kademlia availability."""
        if not HAS_KADEMLIA:
            raise ImportError(
                "kademlia library not installed. "
                "Install with: pip install kademlia"
            )
        self._server = Server()

    async def __aenter__(self) -> M17DHTNode:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()

    async def start(self, should_bootstrap: bool = True) -> None:
        """
        Start the DHT node.

        Args:
            should_bootstrap: Whether to bootstrap from known nodes.
        """
        if self._running:
            logger.warning("DHT node already running")
            return

        await self._server.listen(self.config.port)
        logger.info(f"DHT listening on port {self.config.port}")

        if should_bootstrap and self.config.bootstrap_nodes:
            await self._server.bootstrap(self.config.bootstrap_nodes)
            logger.info(f"Bootstrapped from {len(self.config.bootstrap_nodes)} nodes")

        self._running = True

        # Start periodic registration
        self._register_task = asyncio.create_task(self._registration_loop())

    async def stop(self) -> None:
        """Stop the DHT node."""
        self._running = False

        if self._register_task:
            self._register_task.cancel()
            try:
                await self._register_task
            except asyncio.CancelledError:
                pass
            self._register_task = None

        if self._server:
            self._server.stop()

        logger.info("DHT node stopped")

    async def _registration_loop(self) -> None:
        """Periodically register this node."""
        while self._running:
            await self.register()
            await asyncio.sleep(self.config.registration_interval)

    async def register(self) -> None:
        """
        Register this node in the DHT.

        Stores both callsign -> location and location -> callsign mappings.
        """
        if not self._server:
            return

        location = json.dumps([self.host, self.config.port])

        # Callsign -> location
        await self._server.set(self.callsign, location)

        # Location -> callsign
        await self._server.set(location, self.callsign)

        logger.debug(f"Registered {self.callsign} at {location}")

    async def lookup(self, callsign: str) -> Optional[Tuple[str, int]]:
        """
        Look up a callsign in the DHT.

        Args:
            callsign: Callsign to look up.

        Returns:
            (host, port) tuple if found, None otherwise.
        """
        if not self._server:
            return None

        result = await self._server.get(callsign)
        if result:
            try:
                location = json.loads(result)
                return (location[0], location[1])
            except (json.JSONDecodeError, IndexError):
                logger.warning(f"Invalid DHT value for {callsign}: {result}")

        return None

    async def reverse_lookup(self, host: str, port: int) -> Optional[str]:
        """
        Reverse lookup: find callsign for a host/port.

        Args:
            host: Host address.
            port: Port number.

        Returns:
            Callsign if found, None otherwise.
        """
        if not self._server:
            return None

        location = json.dumps([host, port])
        result = await self._server.get(location)
        return result


# Legacy class alias
m17_networking_dht = M17DHTNode
