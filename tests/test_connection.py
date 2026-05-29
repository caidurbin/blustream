"""Tests for connection layer."""

import asyncio
from pathlib import Path
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

LIVE_STATUS_FIXTURE = Path(__file__).resolve().parent / "fixtures/status_live_full.txt"


def _accept_first(_line: str) -> bool:
    """Terminator predicate: ends on the first complete line."""
    return True


class TestTCPConnection:
    """Tests for TCPConnection."""

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_connect_success(self, mock_open_connection):
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_reader.read = AsyncMock(side_effect=[BANNER])
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.connect()

        mock_open_connection.assert_called_once()
        assert conn.is_connected()

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_connect_timeout(self, mock_open_connection):
        mock_open_connection.side_effect = asyncio.TimeoutError()

        conn = TCPConnection(host="192.168.1.100", port=23)
        with pytest.raises(TimeoutError):
            await conn.connect()

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_send_receive(self, mock_open_connection):
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_reader.read = AsyncMock(
            side_effect=[BANNER, asyncio.TimeoutError(), "response\r\n"]
        )
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.connect()

        await conn.send(b"test")
        mock_writer.write.assert_called_with("test")
        mock_writer.drain.assert_called()

        response = await conn.read_until(_accept_first, timeout=1.0)
        assert response == "response\r\n"

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_disconnect(self, mock_open_connection):
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
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
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)

        with pytest.raises(ConnectionError):
            await conn.send(b"test")

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_receive_when_disconnected(self, mock_open_connection):
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)

        with pytest.raises(ConnectionError):
            await conn.read_until(_accept_first, timeout=0.1)

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_read_until_timeout(self, mock_open_connection):
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_reader.read = AsyncMock(side_effect=[BANNER, asyncio.TimeoutError()])
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.connect()

        with pytest.raises(TimeoutError):
            await conn.read_until(_accept_first, timeout=0.1)

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_read_until_remote_closed(self, mock_open_connection):
        """Empty read after data signals remote close → ConnectionError."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_reader.read = AsyncMock(side_effect=[BANNER, "partial", ""])
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.connect()

        with pytest.raises(ConnectionError):
            await conn.read_until(_accept_first, timeout=1.0)

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_connect_already_connected(self, mock_open_connection):
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_reader.read = AsyncMock(side_effect=[BANNER])
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.connect()
        assert conn.is_connected()

        await conn.connect()
        assert conn.is_connected()
        assert mock_open_connection.call_count == 1

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_disconnect_when_not_connected(self, mock_open_connection):
        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.disconnect()
        assert not conn.is_connected()

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_connection_error_on_connect(self, mock_open_connection):
        mock_open_connection.side_effect = OSError("Connection refused")

        conn = TCPConnection(host="192.168.1.100", port=23)

        with pytest.raises(ConnectionError):
            await conn.connect()

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_banner_consumed_across_chunks(self, mock_open_connection):
        """Welcome banner split across multiple TCP chunks is consumed cleanly."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        banner_chunks = [
            "=" * 64 + "\r\n",
            "Welcome to DMP168 Terminal Control System\r\n",
            "FW Version: 1.5.0\r\n\r\n",
            'Type "HELP" For More Information\r\n',
            "=" * 64 + "\r\n",
        ]
        mock_reader.read = AsyncMock(
            side_effect=banner_chunks + ["OUT 4\r\n[SUCCESS]ok\r\n"]
        )
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.connect()

        assert mock_reader.read.call_count == 5

        response = await conn.read_until(
            lambda line: line.startswith("[SUCCESS]") or line.startswith("[ERROR]"),
            timeout=1.0,
        )
        assert response == "OUT 4\r\n[SUCCESS]ok\r\n"

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_no_banner_proceeds(self, mock_open_connection):
        """Port 8000 emits no banner; connect must succeed regardless.

        The banner discard is best-effort — under load the device may not
        deliver the banner at all (port 8000 never does). The drain in
        send() cleans up any banner-shaped noise that arrives later, so
        no banner on connect is not an error.
        """
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_reader.read = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=8000, banner_timeout=0.05)
        await conn.connect()
        assert conn.is_connected()

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_banner_then_immediate_command_response(self, mock_open_connection):
        """Banner ends inside the same chunk that also carries the next response."""
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
            side_effect=[full_banner, "[SUCCESS]ok\r\n"]
        )
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.connect()

        assert mock_reader.read.call_count == 1

        response = await conn.read_until(
            lambda line: line.startswith("[SUCCESS]"),
            timeout=1.0,
        )
        assert response == "[SUCCESS]ok\r\n"

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_send_encoding_error(self, mock_open_connection):
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_reader.read = AsyncMock(side_effect=[BANNER])
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.connect()

        mock_writer.write.side_effect = OSError("Write failed")

        with pytest.raises(ConnectionError):
            await conn.send(b"test")

        assert not conn.is_connected()


class TestStreamingResponseFraming:
    """Regression tests for the framing-bug fix (issue #26).

    The DMP168 streams long responses (notably STATUS) over hundreds of
    milliseconds with mid-message pauses. The old chunk-boundary
    heuristic ("got a read smaller than buffer ⇒ done") returned
    premature partial responses, and any unread bytes stayed in the
    underlying TCP buffer to poison the next command. These tests use
    the real captured response under spec/vectors/fixtures/ so the
    framing has to survive realistic chunking, not synthetic shapes.
    """

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_chunked_status_returns_complete_response(self, mock_open_connection):
        """A STATUS reply chunked into 5+ slices with pauses still returns whole.

        Splits the captured live STATUS response into 6 chunks, simulates
        a 250-ms gap between each (well above any plausible
        "settle after silence" timer), and asserts the connection returns
        the full byte-equivalent payload — no truncation, no premature
        return on a short chunk.
        """
        from blustream.devices.dmp168.device import _status_terminator

        # newline="" preserves the on-disk \r\n terminators verbatim — the
        # default text-mode read normalises them to \n, which would defeat
        # the framing under test.
        full_response = LIVE_STATUS_FIXTURE.read_text(newline="")
        # 6 chunks of roughly equal size
        n_chunks = 6
        chunk_size = (len(full_response) + n_chunks - 1) // n_chunks
        chunks = [
            full_response[i : i + chunk_size]
            for i in range(0, len(full_response), chunk_size)
        ]
        assert len(chunks) >= 5

        mock_reader = AsyncMock()
        mock_writer = AsyncMock()

        async def slow_read(_size: int) -> str:
            if not chunks:
                await asyncio.sleep(60)  # block forever, test should not reach here
                return ""
            await asyncio.sleep(0.25)  # 250 ms mid-message pause
            return chunks.pop(0)

        # Banner first, then the chunked STATUS body.
        async def reader_sequence(_size: int) -> str:
            nonlocal banner_sent
            if not banner_sent:
                banner_sent = True
                return BANNER
            return await slow_read(_size)

        banner_sent = False
        mock_reader.read = AsyncMock(side_effect=reader_sequence)
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.connect()

        response = await conn.read_until(_status_terminator(), timeout=10.0)

        # Whole response delivered, no truncation
        assert response == full_response
        # Both =-only sentinels present (body opener + footer)
        sentinel_lines = [
            ln for ln in response.splitlines()
            if ln and set(ln) == {"="} and len(ln) >= 16
        ]
        assert len(sentinel_lines) == 2

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_banner_broadcast_in_status_stream_is_stripped(self, mock_open_connection):
        """A welcome-banner re-broadcast inside the STATUS stream is filtered out.

        When a second client connects to port 23, the DMP168 broadcasts
        the welcome banner to every existing client. If that broadcast
        arrives in the middle of an in-flight STATUS reply, the read
        path must strip it — otherwise the banner's ``=``-only lines
        would prematurely satisfy the STATUS terminator and the parser
        would see banner content instead of system status.
        """
        from blustream.devices.dmp168.device import _status_terminator

        full_status = LIVE_STATUS_FIXTURE.read_text(newline="")
        banner = (
            "\r\n"
            "================================================================\r\n"
            "Welcome to DMP168 Terminal Control System\r\n"
            "FW Version: 1.5.0\r\n"
            "\r\n"
            "Type \"HELP\" For More Information\r\n"
            "================================================================\r\n"
        )

        # Splice the banner into the middle of the STATUS body so the
        # read sees a polluted stream.
        mid = len(full_status) // 2
        polluted = full_status[:mid] + banner + full_status[mid:]

        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_reader.read = AsyncMock(
            side_effect=[BANNER, asyncio.TimeoutError(), polluted]
        )
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.connect()
        await conn.send(b"STATUS\r\n")

        response = await conn.read_until(_status_terminator(), timeout=5.0)

        assert "Welcome to DMP168" not in response
        # Sanity check: the STATUS body content is intact end-to-end
        assert response.startswith("\r\n=")
        assert response.endswith("================================================================\r\n")
        assert "Power" in response and "Baud" in response

    @pytest.mark.asyncio
    @patch("telnetlib3.open_connection")
    async def test_back_to_back_commands_do_not_bleed(self, mock_open_connection):
        """Tail bytes of response #1 must not contaminate response #2.

        Stages a first response whose final read also delivers the *start*
        of the next response (a real-world TCP coalescing pattern). The
        first read_until should return only response #1; the next
        read_until must return only response #2, even when the second
        response itself arrives with mid-message pauses.
        """
        from blustream.devices.dmp168.device import _status_terminator

        full_status = LIVE_STATUS_FIXTURE.read_text(newline="")
        next_response = "[SUCCESS]ok\r\n"

        # Chunk plan: banner, then STATUS body split into 4 chunks where
        # the LAST chunk also carries the start of the next [SUCCESS]
        # response. After the bleed-chunk, the rest of [SUCCESS] arrives
        # as a final read.
        mid = len(full_status) // 2
        chunks = [
            full_status[:mid],
            full_status[mid : mid + (len(full_status) - mid) // 2],
        ]
        # Split tail so the last STATUS chunk carries the first 4 chars of the
        # next response. That's the bleed condition.
        status_tail = full_status[mid + (len(full_status) - mid) // 2 :]
        bleed_split = 4
        chunks.append(status_tail + next_response[:bleed_split])
        chunks.append(next_response[bleed_split:])

        async def reader_sequence(_size: int) -> str:
            nonlocal banner_sent
            if not banner_sent:
                banner_sent = True
                return BANNER
            await asyncio.sleep(0.3)  # 300 ms mid-message pause
            if not chunks:
                await asyncio.sleep(60)
                return ""
            return chunks.pop(0)

        banner_sent = False
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_reader.read = AsyncMock(side_effect=reader_sequence)
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_open_connection.return_value = (mock_reader, mock_writer)

        conn = TCPConnection(host="192.168.1.100", port=23)
        await conn.connect()

        first = await conn.read_until(_status_terminator(), timeout=10.0)
        assert first == full_status, "first response must be exactly the STATUS body"
        assert "[SUCCESS]" not in first, "tail of next response must NOT leak into first"

        second = await conn.read_until(
            lambda line: line.startswith("[SUCCESS]"),
            timeout=10.0,
        )
        assert second == next_response, "second response must be exactly its own bytes"
