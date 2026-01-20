"""M17 Networking Layer

This module provides high-level networking components for M17:
- Reflector client (n7tae protocol)
- DHT-based routing (Kademlia)
- P2P direct connections
- High-level async client

This is pyM17's unique value - providing IP networking for M17.
"""

from m17.net.client import (
    M17ClientConfig,
    M17NetworkClient,
)
from m17.net.dht import (
    DHTConfig,
    M17DHTNode,
)
from m17.net.p2p import (
    P2PConnection,
    P2PManager,
)
from m17.net.reflector import (
    M17ReflectorClient,
    ReflectorConnection,
    ReflectorProtocol,
)

__all__ = [
    # Reflector
    "ReflectorConnection",
    "ReflectorProtocol",
    "M17ReflectorClient",
    # DHT
    "M17DHTNode",
    "DHTConfig",
    # P2P
    "P2PConnection",
    "P2PManager",
    # Client
    "M17NetworkClient",
    "M17ClientConfig",
]
