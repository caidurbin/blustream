"""Tests for base device class."""

from typing import Callable, Iterable, List, Union

import pytest

from blustream.base.connection import Connection
from blustream.base.device import BlustreamDevice
from blustream.base.exceptions import CommandError, ConnectionError, TimeoutError

LINE_TERMINATOR = "\r\n"


class MockConnection(Connection):
    """Mock connection that frames replies as ``read_until`` does.

    Tests stage a sequence of "remote chunks" — each chunk represents
    one segment as it would arrive off the wire. ``read_until`` consumes
    chunks one at a time, accumulating into a buffer, and returns the
    text up to and including the first line that satisfies ``predicate``.
    Anything past that line stays buffered for the next call, matching
    the real TCP connection's behaviour.
    """

    def __init__(self):
        self._connected = False
        self._send_calls: List[bytes] = []
        self._chunks: List[Union[str, Exception]] = []
        self._buffer = ""

    def queue(self, *chunks: Union[str, bytes, Exception]) -> None:
        for chunk in chunks:
            if isinstance(chunk, bytes):
                self._chunks.append(chunk.decode("utf-8", errors="replace"))
            else:
                self._chunks.append(chunk)

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def send(self, data: bytes) -> None:
        if not self._connected:
            raise ConnectionError("Not connected")
        self._send_calls.append(data)

    async def read_until(
        self,
        predicate: Callable[[str], bool],
        timeout: float,
    ) -> str:
        if not self._connected:
            raise ConnectionError("Not connected")

        accumulated = ""
        while True:
            idx = self._buffer.find(LINE_TERMINATOR)
            while idx >= 0:
                line_end = idx + len(LINE_TERMINATOR)
                line = self._buffer[:line_end]
                accumulated += line
                self._buffer = self._buffer[line_end:]
                if predicate(line):
                    return accumulated
                idx = self._buffer.find(LINE_TERMINATOR)

            if not self._chunks:
                raise TimeoutError("Mock connection exhausted before predicate satisfied")

            chunk = self._chunks.pop(0)
            if isinstance(chunk, Exception):
                raise chunk
            self._buffer += chunk

    def is_connected(self) -> bool:
        return self._connected


class ConcreteDevice(BlustreamDevice):
    def get_commands(self):
        return ["test"]

    async def execute_command(self, name: str, **kwargs):
        return "result"

    async def get_status(self):
        return {"status": "ok"}


class TestBlustreamDevice:

    def test_init(self):
        conn = MockConnection()
        device = ConcreteDevice(conn)
        assert device._connection == conn
        assert not device._connected

    @pytest.mark.asyncio
    async def test_connect(self):
        conn = MockConnection()
        device = ConcreteDevice(conn)
        await device.connect()
        assert device._connected
        assert conn._connected

    @pytest.mark.asyncio
    async def test_disconnect(self):
        conn = MockConnection()
        device = ConcreteDevice(conn)
        await device.connect()
        await device.disconnect()
        assert not device._connected
        assert not conn._connected

    @pytest.mark.asyncio
    async def test_context_manager(self):
        conn = MockConnection()
        async with ConcreteDevice(conn) as device:
            assert device.is_connected
            assert conn._connected
        assert not device._connected
        assert not conn._connected

    @pytest.mark.asyncio
    async def test_send_command_not_connected(self):
        conn = MockConnection()
        device = ConcreteDevice(conn)
        with pytest.raises(ConnectionError):
            await device.send_command("TEST")

    @pytest.mark.asyncio
    async def test_send_command_simple_response(self):
        conn = MockConnection()
        conn.queue("TEST\r\n[SUCCESS]ok\r\n")
        device = ConcreteDevice(conn)
        await device.connect()

        response = await device.send_command("TEST")
        assert "[SUCCESS]" in response
        assert len(conn._send_calls) == 1
        assert b"TEST\r\n" in conn._send_calls[0]

    @pytest.mark.asyncio
    async def test_send_command_info_response(self):
        """TEMP/UPTIME terminate on the standard [SUCCESS] marker line."""
        conn = MockConnection()
        conn.queue("[SUCCESS]The temperature of the system is 47.4C\r\n")
        device = ConcreteDevice(conn)
        await device.connect()

        response = await device.send_command("TEMP")
        assert "47.4C" in response

    @pytest.mark.asyncio
    async def test_send_command_connection_error(self):
        conn = MockConnection()
        conn.queue(ConnectionError("Connection lost"))
        device = ConcreteDevice(conn)
        await device.connect()

        with pytest.raises(CommandError):
            await device.send_command("TEST")

    @pytest.mark.asyncio
    async def test_send_command_timeout_error(self):
        conn = MockConnection()
        conn.queue(TimeoutError("Timeout"))
        device = ConcreteDevice(conn)
        await device.connect()

        with pytest.raises(CommandError):
            await device.send_command("TEST")

    @pytest.mark.asyncio
    async def test_send_command_no_marker_times_out(self):
        """Response without a marker line → CommandError when buffer drains."""
        conn = MockConnection()
        conn.queue("Partial response\r\n")
        device = ConcreteDevice(conn, response_timeout=0.05)
        await device.connect()

        with pytest.raises(CommandError):
            await device.send_command("TEST")

    @pytest.mark.asyncio
    async def test_send_command_error_marker(self):
        conn = MockConnection()
        conn.queue("BAD\r\n[ERROR]bad parameter\r\n")
        device = ConcreteDevice(conn)
        await device.connect()

        response = await device.send_command("BAD")
        assert "[ERROR]bad parameter" in response

    @pytest.mark.asyncio
    async def test_send_command_marker_across_chunks(self):
        """Marker line split across multiple reader chunks is reassembled."""
        conn = MockConnection()
        conn.queue(
            "OUT 4 REM 2\r\n",
            "[SUCC",
            "ESS]Set output 4 L/R remove input 2 L/R.\r\n",
        )
        device = ConcreteDevice(conn)
        await device.connect()

        response = await device.send_command("OUT 4 REM 2")
        assert "[SUCCESS]Set output 4 L/R remove input 2 L/R." in response

    @pytest.mark.asyncio
    async def test_is_connected_true(self):
        conn = MockConnection()
        device = ConcreteDevice(conn)
        await device.connect()
        assert device.is_connected

    @pytest.mark.asyncio
    async def test_is_connected_false(self):
        conn = MockConnection()
        device = ConcreteDevice(conn)
        assert not device.is_connected

    @pytest.mark.asyncio
    async def test_is_connected_connection_lost(self):
        conn = MockConnection()
        device = ConcreteDevice(conn)
        await device.connect()
        conn._connected = False
        assert not device.is_connected

    @pytest.mark.asyncio
    async def test_send_command_writes_command_log(self, tmp_path):
        import re

        log_path = tmp_path / "commands.log"
        conn = MockConnection()
        device = ConcreteDevice(conn, command_log_path=str(log_path))
        await device.connect()

        conn.queue("POWER ON\r\n[SUCCESS]ok\r\n")
        await device.send_command("POWER ON")
        conn.queue("VOL CH=0 LR 50%\r\n[SUCCESS]ok\r\n")
        await device.send_command("VOL CH=0 LR 50%")

        contents = log_path.read_text(encoding="utf-8")
        headers = re.findall(r"^==== (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) ====$", contents, re.MULTILINE)
        assert len(headers) == 2
        assert "command: POWER ON" in contents
        assert "command: VOL CH=0 LR 50%" in contents

    @pytest.mark.asyncio
    async def test_send_command_no_log_when_path_unset(self, tmp_path):
        log_path = tmp_path / "commands.log"
        conn = MockConnection()
        conn.queue("POWER ON\r\n[SUCCESS]ok\r\n")
        device = ConcreteDevice(conn)
        await device.connect()

        await device.send_command("POWER ON")

        assert not log_path.exists()

    @pytest.mark.asyncio
    async def test_send_command_log_failure_does_not_break_command(self, tmp_path, caplog):
        bad_path = tmp_path / "missing_dir" / "commands.log"
        conn = MockConnection()
        conn.queue("POWER ON\r\n[SUCCESS]ok\r\n")
        device = ConcreteDevice(conn, command_log_path=str(bad_path))
        await device.connect()

        with caplog.at_level("WARNING", logger="blustream.base.device"):
            response = await device.send_command("POWER ON")

        assert "[SUCCESS]" in response
        assert any("Failed to write command log" in rec.message for rec in caplog.records)
