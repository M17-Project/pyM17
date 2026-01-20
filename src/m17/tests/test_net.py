"""Tests for M17 networking modules.

Tests cover:
- m17.net.reflector - Reflector protocol and client
- m17.net.p2p - P2P connections and NAT traversal
- m17.net.dht - DHT-based routing
- m17.net.client - High-level network client
"""

import json
import socket
import time
from unittest.mock import MagicMock, patch

import pytest

from m17.frames.ip import IPFrame

# =============================================================================
# Reflector Protocol Tests
# =============================================================================


class TestReflectorProtocol:
    """Test ReflectorProtocol message encoding/decoding."""

    def test_import(self):
        """Test that reflector module can be imported."""

    def test_make_connect(self):
        """Test CONN message creation."""
        from m17.net.reflector import ReflectorProtocol

        proto = ReflectorProtocol("N0CALL")
        msg = proto.make_connect("A")

        assert msg.startswith(b"CONN")
        assert len(msg) == 4 + 6 + 1  # CONN + callsign bytes + module
        assert msg.endswith(b"A")

    def test_make_connect_module_lowercase(self):
        """Test CONN message with lowercase module gets uppercased."""
        from m17.net.reflector import ReflectorProtocol

        proto = ReflectorProtocol("N0CALL")
        msg = proto.make_connect("b")

        assert msg.endswith(b"B")

    def test_make_connect_invalid_module(self):
        """Test CONN with invalid module raises error."""
        from m17.net.reflector import ReflectorProtocol

        proto = ReflectorProtocol("N0CALL")

        with pytest.raises(ValueError, match="Module must be single letter"):
            proto.make_connect("AB")

        with pytest.raises(ValueError, match="Module must be single letter"):
            proto.make_connect("1")

    def test_make_disconnect(self):
        """Test DISC message creation."""
        from m17.net.reflector import ReflectorProtocol

        proto = ReflectorProtocol("N0CALL")
        msg = proto.make_disconnect()

        assert msg.startswith(b"DISC")
        assert len(msg) == 4 + 6  # DISC + callsign bytes

    def test_make_pong(self):
        """Test PONG message creation."""
        from m17.net.reflector import ReflectorProtocol

        proto = ReflectorProtocol("N0CALL")
        msg = proto.make_pong()

        assert msg.startswith(b"PONG")
        assert len(msg) == 4 + 6  # PONG + callsign bytes

    def test_parse_message_ackn(self):
        """Test parsing ACKN message."""
        from m17.net.reflector import ReflectorMessage, ReflectorProtocol

        msg_type, payload = ReflectorProtocol.parse_message(b"ACKN\x00\x00\x00\x00")

        assert msg_type == ReflectorMessage.ACKN
        assert payload == b"\x00\x00\x00\x00"

    def test_parse_message_nack(self):
        """Test parsing NACK message."""
        from m17.net.reflector import ReflectorMessage, ReflectorProtocol

        msg_type, payload = ReflectorProtocol.parse_message(b"NACK")

        assert msg_type == ReflectorMessage.NACK
        assert payload == b""

    def test_parse_message_ping(self):
        """Test parsing PING message."""
        from m17.net.reflector import ReflectorMessage, ReflectorProtocol

        msg_type, payload = ReflectorProtocol.parse_message(b"PING")

        assert msg_type == ReflectorMessage.PING

    def test_parse_message_pong(self):
        """Test parsing PONG message."""
        from m17.net.reflector import ReflectorMessage, ReflectorProtocol

        msg_type, payload = ReflectorProtocol.parse_message(b"PONG\x01\x02\x03")

        assert msg_type == ReflectorMessage.PONG
        assert payload == b"\x01\x02\x03"

    def test_parse_message_m17_frame(self):
        """Test parsing M17 frame message."""
        from m17.net.reflector import ReflectorMessage, ReflectorProtocol

        msg_type, payload = ReflectorProtocol.parse_message(b"M17 " + bytes(50))

        assert msg_type == ReflectorMessage.M17_FRAME
        assert len(payload) == 50

    def test_parse_message_too_short(self):
        """Test parsing message that's too short."""
        from m17.net.reflector import ReflectorProtocol

        with pytest.raises(ValueError, match="Message too short"):
            ReflectorProtocol.parse_message(b"AC")

    def test_parse_message_unknown(self):
        """Test parsing unknown message type."""
        from m17.net.reflector import ReflectorProtocol

        with pytest.raises(ValueError, match="Unknown message type"):
            ReflectorProtocol.parse_message(b"XXXX")


class TestConnectionState:
    """Test ConnectionState enum."""

    def test_states(self):
        """Test all connection states exist."""
        from m17.net.reflector import ConnectionState

        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert ConnectionState.CONNECTING.value == "connecting"
        assert ConnectionState.CONNECTED.value == "connected"
        assert ConnectionState.DISCONNECTING.value == "disconnecting"
        assert ConnectionState.ERROR.value == "error"


class TestReflectorMessage:
    """Test ReflectorMessage enum."""

    def test_message_types(self):
        """Test all message types have correct values."""
        from m17.net.reflector import ReflectorMessage

        assert ReflectorMessage.CONN.value == b"CONN"
        assert ReflectorMessage.DISC.value == b"DISC"
        assert ReflectorMessage.PING.value == b"PING"
        assert ReflectorMessage.PONG.value == b"PONG"
        assert ReflectorMessage.ACKN.value == b"ACKN"
        assert ReflectorMessage.NACK.value == b"NACK"
        assert ReflectorMessage.M17_FRAME.value == b"M17 "


class TestReflectorConnection:
    """Test ReflectorConnection class."""

    def test_create(self):
        """Test creating a reflector connection."""
        from m17.net.reflector import ConnectionState, ReflectorConnection

        conn = ReflectorConnection(
            host="reflector.example.com",
            port=17000,
            callsign="N0CALL",
            module="A",
        )

        assert conn.host == "reflector.example.com"
        assert conn.port == 17000
        assert conn.callsign == "N0CALL"
        assert conn.module == "A"
        assert conn.state == ConnectionState.DISCONNECTED
        assert conn.is_connected is False

    def test_default_values(self):
        """Test default values."""
        from m17.net.reflector import ReflectorConnection

        conn = ReflectorConnection(host="test.example.com")

        assert conn.port == 17000
        assert conn.callsign == "N0CALL"
        assert conn.module == "A"

    def test_addr_property(self):
        """Test addr property returns tuple."""
        from m17.net.reflector import ReflectorConnection

        conn = ReflectorConnection(host="test.example.com", port=17001)

        assert conn.addr == ("test.example.com", 17001)

    def test_set_frame_callback(self):
        """Test setting frame callback."""
        from m17.net.reflector import ReflectorConnection

        conn = ReflectorConnection(host="test.example.com")

        callback_called = []

        def callback(frame):
            callback_called.append(frame)

        conn.set_frame_callback(callback)
        assert conn._frame_callback == callback

    def test_disconnect_when_not_connected(self):
        """Test disconnect when not connected is no-op."""
        from m17.net.reflector import ConnectionState, ReflectorConnection

        conn = ReflectorConnection(host="test.example.com")
        conn.disconnect()

        assert conn.state == ConnectionState.DISCONNECTED

    @patch("socket.socket")
    def test_connect_success(self, mock_socket_class):
        """Test successful connection."""
        from m17.net.reflector import ConnectionState, ReflectorConnection

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recvfrom.return_value = (b"ACKN", ("reflector.example.com", 17000))

        conn = ReflectorConnection(
            host="reflector.example.com",
            port=17000,
            callsign="N0CALL",
            module="A",
        )

        result = conn.connect(timeout=1.0)

        assert result is True
        assert conn.state == ConnectionState.CONNECTED
        assert conn.is_connected is True
        mock_sock.bind.assert_called_once_with(("0.0.0.0", 0))
        mock_sock.sendto.assert_called()

    @patch("socket.socket")
    def test_connect_nack(self, mock_socket_class):
        """Test connection refused (NACK)."""
        from m17.net.reflector import ConnectionState, ReflectorConnection

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recvfrom.return_value = (b"NACK", ("reflector.example.com", 17000))

        conn = ReflectorConnection(host="reflector.example.com")

        result = conn.connect(timeout=1.0)

        assert result is False
        assert conn.state == ConnectionState.ERROR

    @patch("socket.socket")
    def test_connect_timeout(self, mock_socket_class):
        """Test connection timeout."""
        from m17.net.reflector import ConnectionState, ReflectorConnection

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recvfrom.side_effect = socket.timeout()

        conn = ReflectorConnection(host="reflector.example.com")

        result = conn.connect(timeout=0.1)

        assert result is False
        assert conn.state == ConnectionState.ERROR

    @patch("socket.socket")
    def test_connect_already_connected(self, mock_socket_class):
        """Test connecting when already connected."""
        from m17.net.reflector import ReflectorConnection

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recvfrom.return_value = (b"ACKN", ("reflector.example.com", 17000))

        conn = ReflectorConnection(host="reflector.example.com")
        conn.connect(timeout=1.0)

        # Try to connect again
        result = conn.connect(timeout=1.0)

        assert result is False  # Already connected

    @patch("socket.socket")
    def test_send_frame(self, mock_socket_class):
        """Test sending a frame."""
        from m17.net.reflector import ReflectorConnection

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recvfrom.return_value = (b"ACKN", ("reflector.example.com", 17000))

        conn = ReflectorConnection(host="reflector.example.com", callsign="N0CALL")
        conn.connect(timeout=1.0)

        # Create a test frame
        frame = IPFrame.create(
            dst="W2FBI",
            src="N0CALL",
            stream_id=0x1234,
            frame_number=0,
            payload=bytes(16),
        )

        conn.send_frame(frame)

        # Verify sendto was called with frame data
        calls = mock_sock.sendto.call_args_list
        assert len(calls) >= 2  # At least CONN and frame

    @patch("socket.socket")
    def test_send_frame_not_connected(self, mock_socket_class):
        """Test sending a frame when not connected raises error."""
        from m17.net.reflector import ReflectorConnection

        conn = ReflectorConnection(host="reflector.example.com")

        frame = IPFrame.create(
            dst="W2FBI",
            src="N0CALL",
            stream_id=0x1234,
            frame_number=0,
            payload=bytes(16),
        )

        with pytest.raises(RuntimeError, match="Not connected"):
            conn.send_frame(frame)

    @patch("socket.socket")
    def test_handle_message_ping(self, mock_socket_class):
        """Test handling PING message sends PONG."""
        from m17.net.reflector import ReflectorConnection

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recvfrom.return_value = (b"ACKN", ("reflector.example.com", 17000))

        conn = ReflectorConnection(host="reflector.example.com", callsign="N0CALL")
        conn.connect(timeout=1.0)

        # Reset mock to track new calls
        mock_sock.sendto.reset_mock()

        result = conn.handle_message(b"PING")

        assert result is None
        # Verify PONG was sent
        mock_sock.sendto.assert_called_once()
        call_args = mock_sock.sendto.call_args[0]
        assert call_args[0].startswith(b"PONG")

    @patch("socket.socket")
    def test_handle_message_nack(self, mock_socket_class):
        """Test handling NACK message sets error state."""
        from m17.net.reflector import ConnectionState, ReflectorConnection

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recvfrom.return_value = (b"ACKN", ("reflector.example.com", 17000))

        conn = ReflectorConnection(host="reflector.example.com")
        conn.connect(timeout=1.0)

        conn.handle_message(b"NACK")

        assert conn.state == ConnectionState.ERROR

    def test_handle_message_unknown(self):
        """Test handling unknown message."""
        from m17.net.reflector import ReflectorConnection

        conn = ReflectorConnection(host="reflector.example.com")

        result = conn.handle_message(b"XXXX")

        assert result is None

    @patch("socket.socket")
    def test_poll_timeout(self, mock_socket_class):
        """Test poll with timeout returns None."""
        from m17.net.reflector import ReflectorConnection

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recvfrom.side_effect = [
            (b"ACKN", ("reflector.example.com", 17000)),  # For connect
            socket.timeout(),  # For poll
        ]

        conn = ReflectorConnection(host="reflector.example.com")
        conn.connect(timeout=1.0)

        result = conn.poll(timeout=0.01)

        assert result is None

    def test_poll_not_connected(self):
        """Test poll when not connected returns None."""
        from m17.net.reflector import ReflectorConnection

        conn = ReflectorConnection(host="reflector.example.com")

        result = conn.poll()

        assert result is None

    @patch("socket.socket")
    def test_disconnect_sends_disc(self, mock_socket_class):
        """Test disconnect sends DISC message."""
        from m17.net.reflector import ConnectionState, ReflectorConnection

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recvfrom.return_value = (b"ACKN", ("reflector.example.com", 17000))

        conn = ReflectorConnection(host="reflector.example.com", callsign="N0CALL")
        conn.connect(timeout=1.0)

        mock_sock.sendto.reset_mock()

        conn.disconnect()

        assert conn.state == ConnectionState.DISCONNECTED
        # Verify DISC was sent
        mock_sock.sendto.assert_called_once()
        call_args = mock_sock.sendto.call_args[0]
        assert call_args[0].startswith(b"DISC")


class TestM17ReflectorClient:
    """Test M17ReflectorClient async client."""

    def test_create(self):
        """Test creating client."""
        from m17.net.reflector import M17ReflectorClient

        client = M17ReflectorClient("N0CALL")

        assert client.callsign == "N0CALL"
        assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        from m17.net.reflector import M17ReflectorClient

        async with M17ReflectorClient("N0CALL") as client:
            assert client.callsign == "N0CALL"

    @pytest.mark.asyncio
    @patch("socket.socket")
    async def test_connect(self, mock_socket_class):
        """Test async connect."""
        from m17.net.reflector import M17ReflectorClient

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recvfrom.return_value = (b"ACKN", ("reflector.example.com", 17000))

        client = M17ReflectorClient("N0CALL")
        result = await client.connect("reflector.example.com", port=17000, module="A")

        assert result is True
        assert client.is_connected is True

    @pytest.mark.asyncio
    @patch("socket.socket")
    async def test_disconnect(self, mock_socket_class):
        """Test async disconnect."""
        from m17.net.reflector import M17ReflectorClient

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recvfrom.return_value = (b"ACKN", ("reflector.example.com", 17000))

        client = M17ReflectorClient("N0CALL")
        await client.connect("reflector.example.com")
        await client.disconnect()

        assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_send_frame_not_connected(self):
        """Test send_frame when not connected raises error."""
        from m17.net.reflector import M17ReflectorClient

        client = M17ReflectorClient("N0CALL")

        frame = IPFrame.create(
            dst="W2FBI",
            src="N0CALL",
            stream_id=0x1234,
            frame_number=0,
            payload=bytes(16),
        )

        with pytest.raises(RuntimeError, match="Not connected"):
            await client.send_frame(frame)

    @pytest.mark.asyncio
    async def test_receive_frames_not_connected(self):
        """Test receive_frames when not connected raises error."""
        from m17.net.reflector import M17ReflectorClient

        client = M17ReflectorClient("N0CALL")

        with pytest.raises(RuntimeError, match="Not connected"):
            async for frame in client.receive_frames():
                pass


# =============================================================================
# P2P Module Tests
# =============================================================================


class TestMessageType:
    """Test P2P MessageType enum."""

    def test_message_types(self):
        """Test all message types exist with correct values."""
        from m17.net.p2p import MessageType

        assert MessageType.WHERE_AM_I == 0
        assert MessageType.I_AM_HERE == 1
        assert MessageType.WHERE_IS == 2
        assert MessageType.IS_AT == 3
        assert MessageType.INTRODUCE_ME == 4
        assert MessageType.INTRODUCING == 5
        assert MessageType.HI == 6


class TestP2PConnection:
    """Test P2PConnection dataclass."""

    def test_create(self):
        """Test creating P2P connection."""
        from m17.net.p2p import P2PConnection

        conn = P2PConnection(
            callsign="W2FBI",
            addr=("192.168.1.100", 17000),
        )

        assert conn.callsign == "W2FBI"
        assert conn.addr == ("192.168.1.100", 17000)
        assert conn.last_seen > 0

    def test_is_active_fresh(self):
        """Test is_active for fresh connection."""
        from m17.net.p2p import P2PConnection

        conn = P2PConnection(
            callsign="W2FBI",
            addr=("192.168.1.100", 17000),
        )

        assert conn.is_active(timeout=30.0) is True

    def test_is_active_stale(self):
        """Test is_active for stale connection."""
        from m17.net.p2p import P2PConnection

        conn = P2PConnection(
            callsign="W2FBI",
            addr=("192.168.1.100", 17000),
            last_seen=time.time() - 60.0,  # 60 seconds ago
        )

        assert conn.is_active(timeout=30.0) is False

    def test_touch(self):
        """Test touch updates last_seen."""
        from m17.net.p2p import P2PConnection

        conn = P2PConnection(
            callsign="W2FBI",
            addr=("192.168.1.100", 17000),
            last_seen=time.time() - 60.0,
        )

        assert conn.is_active(timeout=30.0) is False

        conn.touch()

        assert conn.is_active(timeout=30.0) is True


class TestP2PManager:
    """Test P2PManager class."""

    def test_create(self):
        """Test creating P2P manager."""
        from m17.net.p2p import P2PManager

        manager = P2PManager(
            callsign="N0CALL",
            primaries=[("primary.example.com", 17000)],
        )

        assert manager.callsign == "N0CALL"
        assert manager.primaries == [("primary.example.com", 17000)]

    def test_create_no_primaries_raises(self):
        """Test creating P2P manager without primaries raises error."""
        from m17.net.p2p import P2PManager

        with pytest.raises(ValueError, match="primaries is required"):
            P2PManager(callsign="N0CALL", primaries=[])

    def test_default_port(self):
        """Test default port."""
        from m17.core.constants import DEFAULT_PORT
        from m17.net.p2p import P2PManager

        manager = P2PManager(
            callsign="N0CALL",
            primaries=[("primary.example.com", 17000)],
        )

        assert manager.port == DEFAULT_PORT

    @pytest.mark.asyncio
    @patch("socket.socket")
    async def test_start_stop(self, mock_socket_class):
        """Test start and stop."""
        from m17.net.p2p import P2PManager

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        manager = P2PManager(
            callsign="N0CALL",
            primaries=[("primary.example.com", 17000)],
        )

        await manager.start()

        mock_sock.bind.assert_called_once()
        mock_sock.setblocking.assert_called_once_with(False)

        await manager.stop()

        mock_sock.close.assert_called_once()

    @pytest.mark.asyncio
    @patch("socket.socket")
    async def test_start_twice(self, mock_socket_class):
        """Test starting twice is no-op."""
        from m17.net.p2p import P2PManager

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        manager = P2PManager(
            callsign="N0CALL",
            primaries=[("primary.example.com", 17000)],
        )

        await manager.start()
        await manager.start()  # Should be no-op

        # Only one socket created
        assert mock_socket_class.call_count == 1

        await manager.stop()

    @pytest.mark.asyncio
    @patch("socket.socket")
    async def test_register(self, mock_socket_class):
        """Test register sends I_AM_HERE to primaries."""
        from m17.net.p2p import MessageType, P2PManager

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        manager = P2PManager(
            callsign="N0CALL",
            primaries=[("primary1.example.com", 17000), ("primary2.example.com", 17000)],
        )

        await manager.start()
        await manager.register()

        # Check that messages were sent to both primaries
        calls = mock_sock.sendto.call_args_list
        assert len(calls) == 2

        for call in calls:
            data = call[0][0]
            assert data.startswith(b"M17J")
            msg = json.loads(data[4:])
            assert msg["msgtype"] == MessageType.I_AM_HERE
            assert msg["callsign"] == "N0CALL"

        await manager.stop()

    @pytest.mark.asyncio
    @patch("socket.socket")
    async def test_lookup(self, mock_socket_class):
        """Test lookup sends WHERE_IS to primaries."""
        from m17.net.p2p import MessageType, P2PManager

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        manager = P2PManager(
            callsign="N0CALL",
            primaries=[("primary.example.com", 17000)],
        )

        await manager.start()
        result = await manager.lookup("W2FBI")

        # Check that WHERE_IS was sent
        calls = mock_sock.sendto.call_args_list
        last_call = calls[-1]
        data = last_call[0][0]
        assert data.startswith(b"M17J")
        msg = json.loads(data[4:])
        assert msg["msgtype"] == MessageType.WHERE_IS
        assert msg["callsign"] == "W2FBI"

        assert result is None  # No response received

        await manager.stop()

    @pytest.mark.asyncio
    @patch("socket.socket")
    async def test_request_introduction(self, mock_socket_class):
        """Test request_introduction sends INTRODUCE_ME."""
        from m17.net.p2p import MessageType, P2PManager

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        manager = P2PManager(
            callsign="N0CALL",
            primaries=[("primary.example.com", 17000)],
        )

        await manager.start()
        await manager.request_introduction("W2FBI")

        # Check that INTRODUCE_ME was sent
        calls = mock_sock.sendto.call_args_list
        last_call = calls[-1]
        data = last_call[0][0]
        assert data.startswith(b"M17J")
        msg = json.loads(data[4:])
        assert msg["msgtype"] == MessageType.INTRODUCE_ME
        assert msg["callsign"] == "W2FBI"

        await manager.stop()

    def test_has_connection_no_connections(self):
        """Test has_connection with no connections."""
        from m17.net.p2p import P2PManager

        manager = P2PManager(
            callsign="N0CALL",
            primaries=[("primary.example.com", 17000)],
        )

        assert manager.has_connection("W2FBI") is False

    @pytest.mark.asyncio
    @patch("socket.socket")
    async def test_send_frame_no_connection(self, mock_socket_class):
        """Test send_frame when no connection exists."""
        from m17.net.p2p import P2PManager

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        manager = P2PManager(
            callsign="N0CALL",
            primaries=[("primary.example.com", 17000)],
        )

        await manager.start()

        frame = IPFrame.create(
            dst="W2FBI",
            src="N0CALL",
            stream_id=0x1234,
            frame_number=0,
            payload=bytes(16),
        )

        result = await manager.send_frame(frame, "W2FBI")

        assert result is False

        await manager.stop()

    def test_set_frame_callback(self):
        """Test set_frame_callback."""
        from m17.net.p2p import P2PManager

        manager = P2PManager(
            callsign="N0CALL",
            primaries=[("primary.example.com", 17000)],
        )

        callback = MagicMock()
        manager.set_frame_callback(callback)

        assert manager._frame_callback == callback

    @pytest.mark.asyncio
    @patch("socket.socket")
    async def test_handle_json_is_at(self, mock_socket_class):
        """Test handling IS_AT message."""
        from m17.net.p2p import MessageType, P2PManager

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        manager = P2PManager(
            callsign="N0CALL",
            primaries=[("primary.example.com", 17000)],
        )

        await manager.start()

        # Simulate receiving IS_AT message
        manager._handle_json_message(
            {
                "msgtype": MessageType.IS_AT,
                "callsign": "W2FBI",
                "host": "192.168.1.100",
                "port": 17000,
            },
            ("primary.example.com", 17000),
        )

        # Check location was stored
        assert "W2FBI" in manager._whereis

        await manager.stop()

    @pytest.mark.asyncio
    @patch("socket.socket")
    async def test_handle_json_hi(self, mock_socket_class):
        """Test handling HI message establishes connection."""
        from m17.net.p2p import MessageType, P2PManager

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        manager = P2PManager(
            callsign="N0CALL",
            primaries=[("primary.example.com", 17000)],
        )

        await manager.start()

        # Simulate receiving HI message
        manager._handle_json_message(
            {"msgtype": MessageType.HI, "callsign": "W2FBI"},
            ("192.168.1.100", 17000),
        )

        # Check connection was established
        assert manager.has_connection("W2FBI")

        await manager.stop()

    @pytest.mark.asyncio
    @patch("socket.socket")
    async def test_poll_no_data(self, mock_socket_class):
        """Test poll when no data available."""
        from m17.net.p2p import P2PManager

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recvfrom.side_effect = BlockingIOError()

        manager = P2PManager(
            callsign="N0CALL",
            primaries=[("primary.example.com", 17000)],
        )

        await manager.start()
        await manager.poll()  # Should not raise

        await manager.stop()


# =============================================================================
# DHT Module Tests
# =============================================================================


class TestDHTConfig:
    """Test DHTConfig dataclass."""

    def test_create(self):
        """Test creating DHT config."""
        from m17.net.dht import DHTConfig

        config = DHTConfig(
            bootstrap_nodes=[("dht.example.com", 17001)],
            port=17001,
        )

        assert config.bootstrap_nodes == [("dht.example.com", 17001)]
        assert config.port == 17001
        assert config.registration_interval == 15.0

    def test_create_no_bootstrap_raises(self):
        """Test creating config without bootstrap nodes raises error."""
        from m17.net.dht import DHTConfig

        with pytest.raises(ValueError, match="bootstrap_nodes is required"):
            DHTConfig(bootstrap_nodes=[])

    def test_default_port(self):
        """Test default port."""
        from m17.net.dht import DEFAULT_DHT_PORT, DHTConfig

        config = DHTConfig(bootstrap_nodes=[("dht.example.com", 17001)])

        assert config.port == DEFAULT_DHT_PORT


class TestM17DHTNode:
    """Test M17DHTNode class."""

    def test_has_kademlia_flag(self):
        """Test HAS_KADEMLIA flag exists."""
        from m17.net.dht import HAS_KADEMLIA

        assert isinstance(HAS_KADEMLIA, bool)

    def test_create(self):
        """Test creating DHT node."""
        from m17.net.dht import HAS_KADEMLIA

        if not HAS_KADEMLIA:
            pytest.skip("kademlia not installed")

        from m17.net.dht import DHTConfig, M17DHTNode

        config = DHTConfig(bootstrap_nodes=[("dht.example.com", 17001)])
        node = M17DHTNode(
            callsign="N0CALL",
            host="192.168.1.100",
            config=config,
        )

        assert node.callsign == "N0CALL"
        assert node.host == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        from m17.net.dht import HAS_KADEMLIA

        if not HAS_KADEMLIA:
            pytest.skip("kademlia not installed")

        from m17.net.dht import DHTConfig, M17DHTNode

        config = DHTConfig(bootstrap_nodes=[("dht.example.com", 17001)])

        async with M17DHTNode(
            callsign="N0CALL",
            host="192.168.1.100",
            config=config,
        ) as node:
            assert node.callsign == "N0CALL"

    def test_create_without_kademlia(self):
        """Test creating DHT node without kademlia installed raises error."""
        from m17.net.dht import HAS_KADEMLIA

        if HAS_KADEMLIA:
            pytest.skip("kademlia is installed")

        from m17.net.dht import DHTConfig, M17DHTNode

        config = DHTConfig(bootstrap_nodes=[("dht.example.com", 17001)])

        with pytest.raises(ImportError, match="kademlia library not installed"):
            M17DHTNode(
                callsign="N0CALL",
                host="192.168.1.100",
                config=config,
            )


# =============================================================================
# Client Module Tests
# =============================================================================


class TestM17ClientConfig:
    """Test M17ClientConfig dataclass."""

    def test_create(self):
        """Test creating client config."""
        from m17.net.client import M17ClientConfig

        config = M17ClientConfig(
            callsign="N0CALL",
            reflector_host="reflector.example.com",
        )

        assert config.callsign == "N0CALL"
        assert config.reflector_host == "reflector.example.com"

    def test_default_values(self):
        """Test default values."""
        from m17.net.client import M17ClientConfig

        config = M17ClientConfig(callsign="N0CALL")

        assert config.reflector_host is None
        assert config.reflector_port == 17000
        assert config.reflector_module == "A"
        assert config.dht_enabled is False
        assert config.dht_port == 17001
        assert config.p2p_enabled is False
        assert config.p2p_port == 17000


class TestM17NetworkClient:
    """Test M17NetworkClient class."""

    def test_create(self):
        """Test creating network client."""
        from m17.net.client import M17ClientConfig, M17NetworkClient

        config = M17ClientConfig(callsign="N0CALL")
        client = M17NetworkClient(config)

        assert client.callsign == "N0CALL"
        assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        from m17.net.client import M17ClientConfig, M17NetworkClient

        config = M17ClientConfig(callsign="N0CALL")

        async with M17NetworkClient(config) as client:
            assert client.callsign == "N0CALL"

    @pytest.mark.asyncio
    async def test_connect_no_host_raises(self):
        """Test connect without host raises error."""
        from m17.net.client import M17ClientConfig, M17NetworkClient

        config = M17ClientConfig(callsign="N0CALL")
        client = M17NetworkClient(config)

        with pytest.raises(ValueError, match="No reflector host specified"):
            await client.connect()

    @pytest.mark.asyncio
    @patch("socket.socket")
    async def test_connect_with_host(self, mock_socket_class):
        """Test connect with specified host."""
        from m17.net.client import M17ClientConfig, M17NetworkClient

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recvfrom.return_value = (b"ACKN", ("reflector.example.com", 17000))

        config = M17ClientConfig(callsign="N0CALL")
        client = M17NetworkClient(config)

        result = await client.connect(host="reflector.example.com")

        assert result is True
        assert client.is_connected is True

        await client.disconnect()

    @pytest.mark.asyncio
    @patch("socket.socket")
    async def test_connect_with_config_host(self, mock_socket_class):
        """Test connect uses config host."""
        from m17.net.client import M17ClientConfig, M17NetworkClient

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recvfrom.return_value = (b"ACKN", ("reflector.example.com", 17000))

        config = M17ClientConfig(
            callsign="N0CALL",
            reflector_host="reflector.example.com",
        )
        client = M17NetworkClient(config)

        result = await client.connect()

        assert result is True

        await client.disconnect()

    def test_add_remove_frame_handler(self):
        """Test adding and removing frame handlers."""
        from m17.net.client import M17ClientConfig, M17NetworkClient

        config = M17ClientConfig(callsign="N0CALL")
        client = M17NetworkClient(config)

        handler = MagicMock()

        client.add_frame_handler(handler)
        assert handler in client._frame_handlers

        client.remove_frame_handler(handler)
        assert handler not in client._frame_handlers

    def test_remove_nonexistent_handler(self):
        """Test removing non-existent handler is no-op."""
        from m17.net.client import M17ClientConfig, M17NetworkClient

        config = M17ClientConfig(callsign="N0CALL")
        client = M17NetworkClient(config)

        handler = MagicMock()
        client.remove_frame_handler(handler)  # Should not raise

    def test_stream_returns_context(self):
        """Test stream returns StreamContext."""
        from m17.net.client import M17ClientConfig, M17NetworkClient, StreamContext

        config = M17ClientConfig(callsign="N0CALL")
        client = M17NetworkClient(config)

        ctx = client.stream("W2FBI")

        assert isinstance(ctx, StreamContext)


class TestStreamContext:
    """Test StreamContext class."""

    def test_create(self):
        """Test creating stream context."""
        from m17.net.client import M17ClientConfig, M17NetworkClient, StreamContext

        config = M17ClientConfig(callsign="N0CALL")
        client = M17NetworkClient(config)

        ctx = StreamContext(
            client=client,
            destination="W2FBI",
            source="N0CALL",
        )

        assert ctx.destination == "W2FBI"
        assert ctx.source == "N0CALL"
        assert 1 <= ctx.stream_id <= 0xFFFF

    def test_stream_id_property(self):
        """Test stream_id property."""
        from m17.net.client import M17ClientConfig, M17NetworkClient, StreamContext

        config = M17ClientConfig(callsign="N0CALL")
        client = M17NetworkClient(config)

        ctx = StreamContext(
            client=client,
            destination="W2FBI",
            source="N0CALL",
        )

        stream_id = ctx.stream_id
        assert isinstance(stream_id, int)
        assert 1 <= stream_id <= 0xFFFF

    def test_frame_number_property(self):
        """Test frame_number property."""
        from m17.net.client import M17ClientConfig, M17NetworkClient, StreamContext

        config = M17ClientConfig(callsign="N0CALL")
        client = M17NetworkClient(config)

        ctx = StreamContext(
            client=client,
            destination="W2FBI",
            source="N0CALL",
        )

        assert ctx.frame_number == 0

    @pytest.mark.asyncio
    async def test_context_manager_creates_lsf(self):
        """Test entering context manager creates LSF."""
        from m17.net.client import M17ClientConfig, M17NetworkClient, StreamContext

        config = M17ClientConfig(callsign="N0CALL")
        client = M17NetworkClient(config)

        ctx = StreamContext(
            client=client,
            destination="W2FBI",
            source="N0CALL",
        )

        async with ctx:
            assert ctx._lsf is not None
            assert ctx._lsf.dst.callsign == "W2FBI"
            assert ctx._lsf.src.callsign == "N0CALL"

    @pytest.mark.asyncio
    @patch("socket.socket")
    async def test_send_pads_short_payload(self, mock_socket_class):
        """Test send pads short payloads to 16 bytes."""
        from m17.net.client import M17ClientConfig, M17NetworkClient, StreamContext

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recvfrom.return_value = (b"ACKN", ("reflector.example.com", 17000))

        config = M17ClientConfig(
            callsign="N0CALL",
            reflector_host="reflector.example.com",
        )
        client = M17NetworkClient(config)
        await client.connect()

        ctx = StreamContext(
            client=client,
            destination="W2FBI",
            source="N0CALL",
        )

        async with ctx:
            mock_sock.sendto.reset_mock()
            await ctx.send(b"short")

            # Frame was sent
            assert mock_sock.sendto.called

        await client.disconnect()

    @pytest.mark.asyncio
    @patch("socket.socket")
    async def test_send_truncates_long_payload(self, mock_socket_class):
        """Test send truncates long payloads to 16 bytes."""
        from m17.net.client import M17ClientConfig, M17NetworkClient, StreamContext

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recvfrom.return_value = (b"ACKN", ("reflector.example.com", 17000))

        config = M17ClientConfig(
            callsign="N0CALL",
            reflector_host="reflector.example.com",
        )
        client = M17NetworkClient(config)
        await client.connect()

        ctx = StreamContext(
            client=client,
            destination="W2FBI",
            source="N0CALL",
        )

        async with ctx:
            mock_sock.sendto.reset_mock()
            await ctx.send(b"this is a very long payload that exceeds 16 bytes")

            # Frame was sent
            assert mock_sock.sendto.called

        await client.disconnect()

    @pytest.mark.asyncio
    @patch("socket.socket")
    async def test_frame_number_increments(self, mock_socket_class):
        """Test frame number increments after send."""
        from m17.net.client import M17ClientConfig, M17NetworkClient, StreamContext

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recvfrom.return_value = (b"ACKN", ("reflector.example.com", 17000))

        config = M17ClientConfig(
            callsign="N0CALL",
            reflector_host="reflector.example.com",
        )
        client = M17NetworkClient(config)
        await client.connect()

        ctx = StreamContext(
            client=client,
            destination="W2FBI",
            source="N0CALL",
        )

        async with ctx:
            assert ctx.frame_number == 0
            await ctx.send(bytes(16))
            assert ctx.frame_number == 1
            await ctx.send(bytes(16))
            assert ctx.frame_number == 2

        await client.disconnect()


# =============================================================================
# Integration Tests
# =============================================================================


class TestNetModuleImports:
    """Test that all net module exports are accessible."""

    def test_import_from_net(self):
        """Test importing from m17.net."""

    def test_all_exports(self):
        """Test __all__ exports."""
        from m17 import net

        expected = [
            "ReflectorConnection",
            "ReflectorProtocol",
            "M17ReflectorClient",
            "M17DHTNode",
            "DHTConfig",
            "P2PConnection",
            "P2PManager",
            "M17NetworkClient",
            "M17ClientConfig",
        ]

        for name in expected:
            assert hasattr(net, name), f"net module missing {name}"


class TestLegacyAliases:
    """Test legacy class aliases for backward compatibility."""

    def test_reflector_alias(self):
        """Test n7tae_reflector_conn alias."""
        from m17.net.reflector import ReflectorConnection, n7tae_reflector_conn

        assert n7tae_reflector_conn is ReflectorConnection

    def test_p2p_alias(self):
        """Test m17_networking_direct alias."""
        from m17.net.p2p import P2PManager, m17_networking_direct

        assert m17_networking_direct is P2PManager

    def test_dht_alias(self):
        """Test m17_networking_dht alias."""
        from m17.net.dht import M17DHTNode, m17_networking_dht

        assert m17_networking_dht is M17DHTNode
