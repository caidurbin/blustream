"""Tests for base device class."""

import asyncio
from typing import Callable, Union

import pytest

from blustream.base.connection import Connection
from blustream.base.device import BlustreamDevice, _is_echo_of, is_simple_marker
from blustream.base.exceptions import CommandError, ConnectionError, TimeoutError

LINE_TERMINATOR = "\r\n"
PROMPT = "DMP168> "


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
        self.connect_calls = 0
        self._send_calls: list[bytes] = []
        self._chunks: list[Union[str, Exception]] = []
        self._buffer = ""

    def queue(self, *chunks: Union[str, bytes, Exception]) -> None:
        for chunk in chunks:
            if isinstance(chunk, bytes):
                self._chunks.append(chunk.decode("utf-8", errors="replace"))
            else:
                self._chunks.append(chunk)

    async def connect(self) -> None:
        self.connect_calls += 1
        # Yield once, as a real connect does, so concurrent callers interleave.
        await asyncio.sleep(0)
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
                raise TimeoutError(
                    "Mock connection exhausted before predicate satisfied"
                )

            chunk = self._chunks.pop(0)
            if isinstance(chunk, Exception):
                raise chunk
            self._buffer += chunk

    def is_connected(self) -> bool:
        return self._connected


class EchoingMockConnection(MockConnection):
    """A mock link that echoes commands, as the DMP168's port 23 does."""

    @property
    def echoes_commands(self) -> bool:
        return True


def _armed_on(header: str):
    """Terminator factory: the first ``=====`` line after ``header``."""

    def make():
        armed = False

        def predicate(line: str) -> bool:
            nonlocal armed
            if header in line:
                armed = True
                return False
            return armed and line.startswith("=====")

        return predicate

    return make


class ConcreteDevice(BlustreamDevice):
    _echo_prompt = PROMPT

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
    async def test_send_command_error_marker_raises_with_device_message(self):
        conn = MockConnection()
        conn.queue("BAD\r\n[ERROR]bad parameter\r\n")
        device = ConcreteDevice(conn)
        await device.connect()

        with pytest.raises(CommandError, match="bad parameter") as exc_info:
            await device.send_command("BAD")
        assert "BAD" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_command_bare_error_marker_raises(self):
        conn = MockConnection()
        conn.queue("[ERROR]\r\n")
        device = ConcreteDevice(conn)
        await device.connect()

        with pytest.raises(CommandError, match="no message"):
            await device.send_command("BAD")

    @pytest.mark.asyncio
    async def test_send_command_error_text_in_custom_terminated_reply_is_data(self):
        """A multi-section reply that ends on its own footer is returned whole."""
        conn = MockConnection()
        conn.queue("Name [ERROR]x\r\n=====\r\n")
        device = ConcreteDevice(conn)
        await device.connect()

        response = await device.send_command(
            "STATUS", terminator=lambda line: line.startswith("=====")
        )
        assert "[ERROR]x" in response

    @pytest.mark.asyncio
    async def test_send_command_error_does_not_poison_next_command(self):
        conn = MockConnection()
        conn.queue("[ERROR]nope\r\n")
        conn.queue("[SUCCESS]ok\r\n")
        device = ConcreteDevice(conn)
        await device.connect()

        with pytest.raises(CommandError):
            await device.send_command("BAD")
        assert "[SUCCESS]ok" in await device.send_command("GOOD")

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

    async def test_connect_after_connection_lost_reconnects(self):
        conn = MockConnection()
        device = ConcreteDevice(conn)
        await device.connect()
        conn._connected = False

        await device.connect()

        assert conn.connect_calls == 2
        assert device.is_connected

    async def test_connect_while_connected_is_noop(self):
        conn = MockConnection()
        device = ConcreteDevice(conn)
        await device.connect()
        await device.connect()
        assert conn.connect_calls == 1

    async def test_concurrent_reconnects_open_one_link(self):
        conn = MockConnection()
        device = ConcreteDevice(conn)
        await device.connect()
        conn._connected = False

        await asyncio.gather(device.connect(), device.connect())

        assert conn.connect_calls == 2
        assert device.is_connected

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
        headers = re.findall(
            r"^==== (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) ====$",
            contents,
            re.MULTILINE,
        )
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
    async def test_send_command_log_failure_does_not_break_command(
        self, tmp_path, caplog
    ):
        bad_path = tmp_path / "missing_dir" / "commands.log"
        conn = MockConnection()
        conn.queue("POWER ON\r\n[SUCCESS]ok\r\n")
        device = ConcreteDevice(conn, command_log_path=str(bad_path))
        await device.connect()

        with caplog.at_level("WARNING", logger="blustream.base.device"):
            response = await device.send_command("POWER ON")

        assert "[SUCCESS]" in response
        assert any(
            "Failed to write command log" in rec.message for rec in caplog.records
        )


class TestIsEchoOf:
    """The echo matcher finds our echo and nothing else."""

    def test_bare_echo(self):
        assert _is_echo_of("UPTIME", PROMPT)("UPTIME\r\n")

    def test_echo_after_the_prompt(self):
        assert _is_echo_of("UPTIME", PROMPT)("DMP168> UPTIME\r\n")

    def test_without_a_prompt_a_prompted_line_is_not_the_echo(self):
        assert not _is_echo_of("UPTIME")("DMP168> UPTIME\r\n")

    def test_echo_after_a_prompt_glued_onto_a_torn_line(self):
        assert _is_echo_of("UPTIME", PROMPT)("=====DMP168> UPTIME\r\n")

    def test_echo_after_repeated_prompts(self):
        assert _is_echo_of("PON", PROMPT)("DMP168> DMP168> PON\r\n")

    def test_lowercase_command_matches_its_lowercase_echo(self):
        assert _is_echo_of("uptime", PROMPT)("DMP168> uptime\r\n")

    def test_case_must_match_the_command_as_sent(self):
        assert not _is_echo_of("uptime", PROMPT)("UPTIME\r\n")

    def test_echo_with_parameters(self):
        assert _is_echo_of("PRESET 9 STATUS", PROMPT)("PRESET 9 STATUS\r\n")

    def test_echo_glued_onto_a_torn_rule(self):
        assert _is_echo_of("STATUS", PROMPT)("23       8000      ==========STATUS\r\n")

    def test_status_row_ending_in_question_mark_is_not_the_help_echo(self):
        line = "23       8000      34:D0:B8:00:00:01   ?\r\n"
        assert not _is_echo_of("?", PROMPT)(line)

    def test_echo_glued_onto_a_letter_or_digit_is_not_recognised(self):
        assert not _is_echo_of("UPTIME", PROMPT)("34:D0:B8:00:0UPTIME\r\n")

    def test_another_command_is_not_our_echo(self):
        assert not _is_echo_of("OUT 1 FR 1", PROMPT)("OUT 11 FR 1\r\n")
        assert not _is_echo_of("TEMP", PROMPT)("UPTIME\r\n")

    def test_reply_text_is_not_an_echo(self):
        assert not _is_echo_of("PON", PROMPT)("[SUCCESS]Set system power on.\r\n")


class TestAttributedFraming:
    """send_command reads our reply from its start line, skipping others'."""

    @staticmethod
    async def _device(conn: MockConnection, **kwargs) -> ConcreteDevice:
        device = ConcreteDevice(conn, **kwargs)
        await device.connect()
        return device

    async def test_echo_link_skips_a_foreign_reply_before_our_echo(self):
        conn = EchoingMockConnection()
        conn.queue(
            "TEMP\r\n[SUCCESS]The temperature of the system is 38.1C\r\n",
            "\r\nDMP168> OUT 1 FR 2\r\n[SUCCESS]Set output 1 L/R from input 2 L/R.\r\n",
        )
        device = await self._device(conn)

        response = await device.send_command("OUT 1 FR 2")
        assert response == (
            "DMP168> OUT 1 FR 2\r\n[SUCCESS]Set output 1 L/R from input 2 L/R.\r\n"
        )

    async def test_echo_link_foreign_error_before_our_echo_does_not_raise(self):
        conn = EchoingMockConnection()
        conn.queue("FOO\r\n[ERROR]Command not found.\r\n\r\nDMP168> ")
        conn.queue("PON\r\n[SUCCESS]ok\r\n")
        device = await self._device(conn)

        assert (await device.send_command("PON")).endswith("[SUCCESS]ok\r\n")

    async def test_echo_link_our_error_raises_without_the_attribution_note(self):
        conn = EchoingMockConnection()
        conn.queue("PON\r\n[SUCCESS]ok\r\n\r\nDMP168> BAD\r\n[ERROR]nope\r\n")
        device = await self._device(conn)

        with pytest.raises(CommandError, match="nope") as exc_info:
            await device.send_command("BAD")
        assert "another client" not in str(exc_info.value)

    async def test_echo_link_error_after_our_echo_ends_a_custom_terminated_read(
        self,
    ):
        conn = EchoingMockConnection()
        conn.queue("STATUS\r\n[ERROR]busy\r\n")
        device = await self._device(conn)

        with pytest.raises(CommandError, match="busy"):
            await device.send_command(
                "STATUS", make_terminator=_armed_on("HEADER"), timeout=0.05
            )

    async def test_echo_link_without_our_echo_times_out(self):
        conn = EchoingMockConnection()
        conn.queue("TEMP\r\n[SUCCESS]The temperature of the system is 38.1C\r\n")
        device = await self._device(conn)

        with pytest.raises(CommandError, match="Command execution failed"):
            await device.send_command("UPTIME")

    async def test_echo_link_ignores_reply_start(self):
        conn = EchoingMockConnection()
        conn.queue("X\r\nSTART\r\n[SUCCESS]theirs\r\nY\r\n[SUCCESS]ours\r\n")
        device = await self._device(conn)

        response = await device.send_command(
            "Y", reply_start=lambda line: line.startswith("START")
        )
        assert response == "Y\r\n[SUCCESS]ours\r\n"

    async def test_reply_start_skips_lines_before_it(self):
        conn = MockConnection()
        conn.queue("[SUCCESS]theirs\r\n[SUCCESS]The uptime is 1\r\n")
        device = await self._device(conn)

        response = await device.send_command(
            "UPTIME", reply_start=lambda line: "uptime" in line
        )
        assert response == "[SUCCESS]The uptime is 1\r\n"

    async def test_each_start_line_gets_a_fresh_terminator(self):
        """A torn reply that armed the terminator must not end ours early."""
        conn = MockConnection()
        conn.queue(
            "TITLE\r\nHEADER\r\nhalf a foreign du",
            "TITLE\r\n=====\r\nHEADER\r\nrow\r\n=====\r\n",
        )
        device = await self._device(conn)

        response = await device.send_command(
            "STATUS",
            reply_start=lambda line: "TITLE" in line,
            make_terminator=_armed_on("HEADER"),
        )
        assert response == (
            "half a foreign duTITLE\r\n=====\r\nHEADER\r\nrow\r\n=====\r\n"
        )

    async def test_make_terminator_takes_precedence_over_terminator(self):
        conn = MockConnection()
        conn.queue("[SUCCESS]early\r\nEND\r\n")
        device = await self._device(conn)

        response = await device.send_command(
            "X",
            terminator=is_simple_marker,
            make_terminator=lambda: lambda line: line.startswith("END"),
        )
        assert response == "[SUCCESS]early\r\nEND\r\n"

    async def test_each_read_without_a_start_line_gets_a_fresh_terminator(self):
        conn = MockConnection()
        conn.queue("HEADER\r\n=====\r\n", "HEADER\r\n=====\r\n")
        device = await self._device(conn)
        make = _armed_on("HEADER")

        assert await device.send_command("A", make_terminator=make)
        assert await device.send_command("B", make_terminator=make)

    async def test_unanchored_error_says_the_reply_may_be_another_clients(self):
        conn = MockConnection()
        conn.queue("[ERROR]Command not found.\r\n")
        device = await self._device(conn)

        with pytest.raises(CommandError, match="may belong to another client"):
            await device.send_command("OUT 1 FR 2")

    async def test_anchored_error_has_no_attribution_note(self):
        conn = MockConnection()
        conn.queue("[ERROR]Preset 1 config status null.\r\n")
        device = await self._device(conn)

        with pytest.raises(CommandError) as exc_info:
            await device.send_command(
                "PRESET 1 STATUS", reply_start=lambda line: "Preset 1" in line
            )
        assert "another client" not in str(exc_info.value)
