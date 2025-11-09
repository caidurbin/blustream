"""Tests for base device class."""

# No mock imports needed - using concrete MockConnection class

import pytest

from bluestream.base.connection import Connection
from bluestream.base.device import BluestreamDevice
from bluestream.base.exceptions import CommandError, ConnectionError, TimeoutError


class MockConnection(Connection):
    """Mock connection for testing."""

    def __init__(self):
        """Initialize mock connection."""
        self._connected = False
        self._send_calls = []
        self._receive_responses = []

    async def connect(self) -> None:
        """Mock connect."""
        self._connected = True

    async def disconnect(self) -> None:
        """Mock disconnect."""
        self._connected = False

    async def send(self, data: bytes) -> None:
        """Mock send."""
        if not self._connected:
            raise ConnectionError("Not connected")
        self._send_calls.append(data)

    async def receive(self, timeout: float = 5.0) -> bytes:
        """Mock receive."""
        if not self._connected:
            raise ConnectionError("Not connected")
        if self._receive_responses:
            return self._receive_responses.pop(0)
        raise TimeoutError("Timeout")

    def is_connected(self) -> bool:
        """Mock is_connected."""
        return self._connected


class ConcreteDevice(BluestreamDevice):
    """Concrete implementation for testing."""

    def get_commands(self):
        """Get commands."""
        return ["test"]

    async def execute_command(self, name: str, **kwargs):
        """Execute command."""
        return "result"

    async def get_status(self):
        """Get status."""
        return {"status": "ok"}


class TestBluestreamDevice:
    """Tests for BluestreamDevice base class."""

    def test_init(self):
        """Test device initialization."""
        conn = MockConnection()
        device = ConcreteDevice(conn)
        assert device._connection == conn
        assert not device._connected

    @pytest.mark.asyncio
    async def test_connect(self):
        """Test connecting device."""
        conn = MockConnection()
        device = ConcreteDevice(conn)
        await device.connect()
        assert device._connected
        assert conn._connected

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnecting device."""
        conn = MockConnection()
        device = ConcreteDevice(conn)
        await device.connect()
        await device.disconnect()
        assert not device._connected
        assert not conn._connected

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test device as async context manager."""
        conn = MockConnection()
        async with ConcreteDevice(conn) as device:
            assert device.is_connected
            assert conn._connected

        assert not device._connected
        assert not conn._connected

    @pytest.mark.asyncio
    async def test_send_command_not_connected(self):
        """Test sending command when not connected."""
        conn = MockConnection()
        device = ConcreteDevice(conn)
        # Don't connect

        with pytest.raises(ConnectionError):
            await device.send_command("TEST")

    @pytest.mark.asyncio
    async def test_send_command_simple_response(self):
        """Test sending simple command."""
        conn = MockConnection()
        conn._receive_responses = [b"OK\r\nDMP168>"]
        device = ConcreteDevice(conn)
        await device.connect()

        response = await device.send_command("TEST")
        assert "OK" in response
        assert len(conn._send_calls) == 1
        assert b"TEST\r\n" in conn._send_calls[0]

    @pytest.mark.asyncio
    async def test_send_command_status_response(self):
        """Test sending STATUS command."""
        conn = MockConnection()
        # STATUS response with multiple lines
        conn._receive_responses = [
            b"Power         Baud\n",
            b"On           57600\n",
            b"Input Settings Status\n",
            b"In1     On   50  50   Off Off\n",
        ]
        device = ConcreteDevice(conn)
        await device.connect()

        response = await device.send_command("STATUS")
        assert "Power" in response
        assert "Input Settings Status" in response

    @pytest.mark.asyncio
    async def test_send_command_info_response(self):
        """Test sending info command (TEMP/UPTIME)."""
        conn = MockConnection()
        conn._receive_responses = [b"[SUCCESS]The temperature of the system is 47.4C\r\nDMP168>"]
        device = ConcreteDevice(conn)
        await device.connect()

        response = await device.send_command("TEMP")
        assert "47.4C" in response

    @pytest.mark.asyncio
    async def test_send_command_connection_error(self):
        """Test sending command when connection error occurs."""
        conn = MockConnection()
        conn._receive_responses = [ConnectionError("Connection lost")]
        device = ConcreteDevice(conn)
        await device.connect()

        with pytest.raises(CommandError):
            await device.send_command("TEST")

    @pytest.mark.asyncio
    async def test_send_command_timeout_error(self):
        """Test sending command when timeout occurs."""
        conn = MockConnection()
        # First receive times out immediately
        conn._receive_responses = [TimeoutError("Timeout")]
        device = ConcreteDevice(conn)
        await device.connect()

        with pytest.raises(CommandError):
            await device.send_command("TEST")

    @pytest.mark.asyncio
    async def test_send_command_partial_response(self):
        """Test sending command with partial response."""
        conn = MockConnection()
        # Response without prompt
        conn._receive_responses = [b"Partial response\n"]
        device = ConcreteDevice(conn)
        await device.connect()

        response = await device.send_command("TEST")
        assert "Partial response" in response

    @pytest.mark.asyncio
    async def test_send_command_empty_response(self):
        """Test sending command with empty response."""
        conn = MockConnection()
        conn._receive_responses = [b"\r\nDMP168>"]
        device = ConcreteDevice(conn)
        await device.connect()

        response = await device.send_command("TEST")
        # Should return empty or minimal response
        assert isinstance(response, str)

    @pytest.mark.asyncio
    async def test_is_connected_true(self):
        """Test is_connected when connected."""
        conn = MockConnection()
        device = ConcreteDevice(conn)
        await device.connect()
        assert device.is_connected

    @pytest.mark.asyncio
    async def test_is_connected_false(self):
        """Test is_connected when not connected."""
        conn = MockConnection()
        device = ConcreteDevice(conn)
        assert not device.is_connected

    @pytest.mark.asyncio
    async def test_is_connected_connection_lost(self):
        """Test is_connected when connection is lost."""
        conn = MockConnection()
        device = ConcreteDevice(conn)
        await device.connect()
        # Manually disconnect the connection
        conn._connected = False
        assert not device.is_connected

