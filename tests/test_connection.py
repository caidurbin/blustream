"""Tests for connection layer."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from blustream.base.exceptions import ConnectionError, TimeoutError
from blustream.connection.tcp import TCPConnection

# Minimal DMP168 welcome banner: two "=…=\r\n" sentinels around the body.
# Tests that just need a successful connect can hand this to the mock reader.
BANNER = (
    "=" * 64 + "\r\n"
    "Welcome\r\n"
    + "=" * 64 + "\r\n"
)


class TestTCPConnection:
    """Tests for TCPConnection."""

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_connect_success(self, mock_open_connection):
        """Test successful connection."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        # telnetlib3 returns strings, not bytes
        mock_reader.read = AsyncMock(side_effect=[BANNER])
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.connect()

        mock_open_connection.assert_called_once()
        assert conn.is_connected()

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_connect_timeout(self, mock_open_connection):
        """Test connection timeout."""
        mock_open_connection.side_effect = asyncio.TimeoutError()

        conn = TCPConnection(host="192.168.1.100", port=23)
        with pytest.raises(TimeoutError):
            await conn.connect()

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_send_receive(self, mock_open_connection):
        """Test send and receive."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        # telnetlib3 returns strings, not bytes
        # First read during connect (discard initial data), then timeout, then response
        mock_reader.read = AsyncMock(side_effect=[BANNER, "response", asyncio.TimeoutError()])
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.connect()

        await conn.send(b"test")
        # telnetlib3 write() expects strings
        mock_writer.write.assert_called_with("test")
        mock_writer.drain.assert_called()

        response = await conn.receive()
        # Our receive() returns bytes (converted from string)
        assert response == b"response"

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_disconnect(self, mock_open_connection):
        """Test disconnect."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        # telnetlib3 returns strings, not bytes
        mock_reader.read = AsyncMock(side_effect=[BANNER])
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.connect()
        await conn.disconnect()

        mock_writer.close.assert_called_once()
        mock_writer.wait_closed.assert_called_once()
        assert not conn.is_connected()

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_send_when_disconnected(self, mock_open_connection):
        """Test sending when disconnected."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        # Don't connect

        with pytest.raises(ConnectionError):
            await conn.send(b"test")

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_receive_when_disconnected(self, mock_open_connection):
        """Test receiving when disconnected."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        # Don't connect

        with pytest.raises(ConnectionError):
            await conn.receive()

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_receive_timeout(self, mock_open_connection):
        """Test receive timeout."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        # First read during connect, then timeout on receive
        # Need to provide enough side_effect items for all reads
        mock_reader.read = AsyncMock(side_effect=[BANNER, asyncio.TimeoutError()])
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.connect()

        from blustream.base.exceptions import TimeoutError

        with pytest.raises(TimeoutError):
            await conn.receive(timeout=0.1)

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_receive_partial_data(self, mock_open_connection):
        """Test receiving partial data."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        # First read during connect, then partial data, then timeout
        mock_reader.read = AsyncMock(side_effect=[BANNER, "partial", asyncio.TimeoutError()])
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.connect()

        response = await conn.receive()
        assert response == b"partial"

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_connect_already_connected(self, mock_open_connection):
        """Test connecting when already connected."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_reader.read = AsyncMock(side_effect=[BANNER])
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.connect()
        assert conn.is_connected()

        # Connect again should be a no-op
        await conn.connect()
        assert conn.is_connected()
        # Should only be called once
        assert mock_open_connection.call_count == 1

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_disconnect_when_not_connected(self, mock_open_connection):
        """Test disconnecting when not connected."""
        conn = TCPConnection(host="192.168.1.100", port=23)
        # Should not raise error
        await conn.disconnect()
        assert not conn.is_connected()

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_connection_error_on_connect(self, mock_open_connection):
        """Test connection error during connect."""
        mock_open_connection.side_effect = OSError("Connection refused")

        conn = TCPConnection(host="192.168.1.100", port=23)
        from blustream.base.exceptions import ConnectionError

        with pytest.raises(ConnectionError):
            await conn.connect()

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_banner_consumed_across_chunks(self, mock_open_connection):
        """Full DMP168 welcome banner split across multiple TCP chunks is consumed.

        Regression test for the banner-race that left command responses
        corrupted: a slow-arriving banner used to fall through the old
        "read-until-quiet" discard and bleed into subsequent receive() calls.
        With sentinel-based discard, the connect() pass must consume both
        =\\r\\n sentinels before returning, so the next receive() sees only
        the actual command response.
        """
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        # Banner chunked the way the device actually sends it: top "=...=\\r\\n",
        # then body lines, then bottom "=...=\\r\\n". Then a TimeoutError to
        # signal "no more banner data," then the real command response.
        banner_chunks = [
            "=" * 64 + "\r\n",
            "Welcome to DMP168 Terminal Control System\r\n",
            "FW Version: 1.5.0\r\n\r\n",
            'Type "HELP" For More Information\r\n',
            "=" * 64 + "\r\n",
        ]
        mock_reader.read = AsyncMock(
            side_effect=banner_chunks + ["OUT 4\r\n[SUCCESS]ok\r\n", asyncio.TimeoutError()]
        )
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.connect()

        # The banner consumed exactly five reads (top, three body lines, bottom).
        # Anything more would mean we over-consumed into the next command.
        assert mock_reader.read.call_count == 5

        # Subsequent receive() should see only the command response.
        response = await conn.receive()
        assert response == b"OUT 4\r\n[SUCCESS]ok\r\n"

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_no_banner_raises_timeout(self, mock_open_connection):
        """No banner within budget → connect fails with TimeoutError.

        Under the strict discard contract, a port that emits no banner (or
        a device that never sends one) is treated as a connect failure
        instead of silently proceeding. Use a short banner_timeout so the
        test runs fast.
        """
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_reader.read = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=8000, banner_timeout=0.05)
        with pytest.raises(TimeoutError, match="banner not consumed"):
            await conn.connect()

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_banner_then_immediate_command_response(self, mock_open_connection):
        """Banner ends inside the same chunk that also carries the next response.

        Edge case the old timing-based discard couldn't handle: if both
        sentinels arrive in a single chunk and a response is already queued
        behind them, we must stop consuming exactly at the second sentinel
        and leave the response for receive() to pick up. With this mock the
        boundary is enforced by chunk shape (the response is delivered on the
        next read), but the test still proves discard exits after seeing both
        sentinels in one read rather than greedily continuing.
        """
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        full_banner = (
            "=" * 64 + "\r\n"
            "Welcome to DMP168 Terminal Control System\r\n"
            "FW Version: 1.5.0\r\n\r\n"
            'Type "HELP" For More Information\r\n'
            + "=" * 64 + "\r\n"
        )
        mock_reader.read = AsyncMock(
            side_effect=[full_banner, "[SUCCESS]ok\r\n", asyncio.TimeoutError()]
        )
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.connect()

        # Exactly one read needed — both sentinels arrived together.
        assert mock_reader.read.call_count == 1

        response = await conn.receive()
        assert response == b"[SUCCESS]ok\r\n"

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_send_encoding_error(self, mock_open_connection):
        """Test send with encoding error handling."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_reader.read = AsyncMock(side_effect=[BANNER])
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.connect()

        # Send invalid bytes that can't be decoded
        # telnetlib3 will handle this, but we should test the error path
        # This is a bit tricky to test since telnetlib3 handles encoding
        # But we can test that the connection state is updated on error
        mock_writer.write.side_effect = OSError("Write failed")

        from blustream.base.exceptions import ConnectionError

        with pytest.raises(ConnectionError):
            await conn.send(b"test")

        # Connection should be marked as disconnected
        assert not conn.is_connected()

