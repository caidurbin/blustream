"""Abstract base device class for Blustream devices."""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from blustream.base.connection import Connection
from blustream.base.exceptions import CommandError, ConnectionError, TimeoutError

logger = logging.getLogger(__name__)

DEFAULT_RESPONSE_TIMEOUT = 5.0

ERROR_MARKER = "[ERROR]"
SIMPLE_RESPONSE_MARKERS = ("[SUCCESS]", ERROR_MARKER)

# Makes a fresh line terminator for each read, or each start line in a read.
_TerminatorFactory = Callable[[], Callable[[str], bool]]

_UNATTRIBUTED_ERROR_NOTE = (
    " This link does not echo commands, so the reply may belong to another"
    " client of the device."
)


def _device_error_message(response: str) -> Optional[str]:
    """Return the text of a closing ``[ERROR]`` line, or None.

    Only the last line is read: it is the line that ended the read. Any
    ``[ERROR]`` text earlier in a multi-section reply is data.
    """
    last_line = response.rstrip("\r\n").rpartition("\n")[2]
    _, marker, message = last_line.partition(ERROR_MARKER)
    return message.strip() if marker else None


def is_simple_marker(line: str) -> bool:
    """True for ``[SUCCESS]…\\r\\n`` or ``[ERROR]…\\r\\n`` lines.

    Default terminator for ``send_command``: every plain command, plus
    TEMP and UPTIME, ends with one of these marker lines.
    """
    return any(marker in line for marker in SIMPLE_RESPONSE_MARKERS)


def _is_echo_of(command: str, prompt: str = "") -> Callable[[str], bool]:
    """Return a predicate that matches the device's echo of ``command``.

    The match is on the command text as sent; the device echoes it
    verbatim, case included. A prompt has no line end, so the next echo
    shares its line (``DMP168> UPTIME``): a line that ends with ``prompt``
    and the command matches, and so does one that, after leading prompts
    are dropped, matches as follows. The line then
    either equals the command, or ends with it after a character that is
    neither a letter, a digit nor a space. The second form takes an echo
    glued onto a line another client's reply left torn
    (``==========STATUS``), but not a line of data that merely ends with
    the command's text, such as a STATUS row ending in ``   ?`` for the
    ``?`` command. An echo glued onto a torn line that ends in a letter or
    digit is not recognised; the command then times out.
    """
    expected = command.strip()

    def predicate(line: str) -> bool:
        text = line.rstrip()
        if prompt and text.endswith(prompt + expected):
            return True
        while prompt and text.startswith(prompt):
            text = text[len(prompt) :]
        if text == expected:
            return True
        if not expected or not text.endswith(expected):
            return False
        before = text[-len(expected) - 1]
        return not (before.isalnum() or before.isspace())

    return predicate


def _or_error_line(make_terminator: _TerminatorFactory) -> _TerminatorFactory:
    """Wrap a terminator factory so an ``[ERROR]`` line also ends the read."""

    def make() -> Callable[[str], bool]:
        terminator = make_terminator()
        return lambda line: line.startswith(ERROR_MARKER) or terminator(line)

    return make


class _ReplyFramer:
    """Line predicate that finds our reply among other clients' output.

    Our reply starts at the last line ``is_start`` accepts. Each start line
    makes a fresh terminator from ``make_terminator``, so a stateful
    terminator that another client's partial reply armed starts over. With
    ``start_is_data`` the start line belongs to the reply and is passed to
    the new terminator; otherwise (an echo) it is not. With no ``is_start``
    the reply starts at the first line and one terminator is made up front.
    ``reply_at`` is the offset of the last start line in the text the read
    accumulated.
    """

    def __init__(
        self,
        is_start: Optional[Callable[[str], bool]],
        make_terminator: _TerminatorFactory,
        *,
        start_is_data: bool,
    ) -> None:
        self._is_start = is_start
        self._make_terminator = make_terminator
        self._start_is_data = start_is_data
        self._terminator = make_terminator() if is_start is None else None
        self._consumed = 0
        self.reply_at = 0

    def __call__(self, line: str) -> bool:
        offset = self._consumed
        self._consumed += len(line)
        if self._is_start is not None and self._is_start(line):
            self.reply_at = offset
            self._terminator = self._make_terminator()
            if not self._start_is_data:
                return False
        return self._terminator is not None and self._terminator(line)


class BlustreamDevice(ABC):
    """Abstract base class for all Blustream devices."""

    # The device's prompt on a link that echoes commands. It has no line
    # end, so the echo of the next command shares its line.
    _echo_prompt = ""

    def __init__(
        self,
        connection: Connection,
        command_log_path: Optional[str] = None,
        response_timeout: float = DEFAULT_RESPONSE_TIMEOUT,
    ):
        self._connection = connection
        self._connected = False
        self._command_log_path = command_log_path
        self._response_timeout = response_timeout
        # Serialises full request/response cycles over the single shared
        # connection. The device fronts one telnetlib3 reader, which raises
        # ``RuntimeError("read() called while another coroutine is already
        # waiting for incoming data")`` if two coroutines read at once — e.g.
        # a Home Assistant service call landing mid-poll. One transaction at a
        # time on the wire (Python >=3.12, so constructing here binds no loop).
        self._command_lock = asyncio.Lock()

    def _log_command(self, command: str) -> None:
        if not self._command_log_path:
            return
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            with open(self._command_log_path, "a", encoding="utf-8") as fh:
                fh.write(f"\n==== {ts} ====\ncommand: {command}\n")
        except OSError as e:
            logger.warning(
                "Failed to write command log %s: %s", self._command_log_path, e
            )

    async def connect(self) -> None:
        """Open the link, or reopen it after the device dropped it.

        A no-op while the link is up. After a drop, ``is_connected`` is
        False and this opens a new link. Runs under ``_command_lock``, so
        two callers reconnecting at once open one link, not two, and a
        reconnect never overlaps a command still running on the old link.
        """
        async with self._command_lock:
            if not self.is_connected:
                await self._connection.connect()
                self._connected = True

    async def disconnect(self) -> None:
        if self._connected:
            await self._connection.disconnect()
            self._connected = False

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    @property
    def is_connected(self) -> bool:
        return self._connected and self._connection.is_connected()

    @abstractmethod
    def get_commands(self) -> list[str]: ...

    @abstractmethod
    async def execute_command(self, name: str, **kwargs: Any) -> Any: ...

    @abstractmethod
    async def get_status(self) -> Any: ...

    async def send_command(
        self,
        command: str,
        *,
        terminator: Callable[[str], bool] = is_simple_marker,
        timeout: Optional[float] = None,
        reply_start: Optional[Callable[[str], bool]] = None,
        make_terminator: Optional[Callable[[], Callable[[str], bool]]] = None,
    ) -> str:
        """Send a command and return its reply.

        The device sends every client's replies to every connected client
        and tags none of them, so the read has to find which lines are
        ours. Our reply starts at a *start line* and ends at the first
        line after it that the terminator accepts:

        - On a link that echoes commands (``connection.echoes_commands``,
          the DMP168's port 23), the start line is the device's echo of
          ``command``. The device writes each command's echo and reply as
          one unbroken block, so the lines after our echo are our reply,
          and an ``[ERROR]`` line among them is our rejection: it ends the
          read whatever the terminator. ``reply_start`` is not used.
        - On a link that does not echo (port 8000), the start line is the
          first line ``reply_start`` accepts, and it is part of the reply.
          Pass a ``reply_start`` that only our command's reply can match.
        - With no echo and no ``reply_start``, there is no start line: the
          reply is everything up to the first line the terminator accepts,
          whoever it came from. This is best-effort. Writes on port 8000
          read this way, so another client's ``[SUCCESS]`` or ``[ERROR]``
          that lands first is taken as ours.

        Each start line restarts the frame with a fresh terminator, so
        output from another client before ours, even a reply cut off part
        way, is skipped. One case is not: without an echo, a terminator
        that another client's torn reply armed can still end the read on a
        line of ours that comes before our start line. The text returned
        begins at the last start line. A command whose start line never
        arrives times out.

        The terminator is ``make_terminator()`` when ``make_terminator`` is
        given, and ``terminator`` is then ignored. Use ``make_terminator``
        for a stateful predicate, such as one that arms on a header line,
        so each start line gets a new one. ``terminator`` is reused as is.
        The default matches the ``[SUCCESS]``/``[ERROR]`` marker line every
        plain command emits.

        A response that closes with an ``[ERROR]`` line is a command the
        device rejected: it raises ``CommandError`` carrying the device's
        message instead of returning the text. When the read had no start
        line, the message adds that the reply may belong to another client.

        No sleeps or quick-read heuristics: the knowledge of where a reply
        starts and ends lives in the predicates the caller supplies.

        The send-then-read pair is held under ``_command_lock`` so a command
        and the status poll (or two commands) can't interleave their reads on
        the one shared connection — overlapping reads on the underlying
        telnetlib3 reader raise ``RuntimeError`` and surface as a spurious
        ``CommandError``. The lock makes transactions atomic, not merely the
        individual reads. It is not reentrant: no code path calls
        ``send_command`` while already holding it.
        """
        if not self.is_connected:
            raise ConnectionError(
                "Device is not connected. Please call 'connect()' or use the device as a context manager before sending commands."
            )

        self._log_command(command)

        budget = timeout if timeout is not None else self._response_timeout
        new_terminator = make_terminator or (lambda: terminator)

        try:
            async with self._command_lock:
                echoes = self._connection.echoes_commands
                if echoes:
                    start = _is_echo_of(command, self._echo_prompt)
                    new_terminator = _or_error_line(new_terminator)
                else:
                    start = reply_start
                framer = _ReplyFramer(start, new_terminator, start_is_data=not echoes)
                await self._connection.send(command.encode("utf-8") + b"\r\n")
                received = await self._connection.read_until(framer, timeout=budget)
                response = received[framer.reply_at :]
        except (ConnectionError, TimeoutError) as e:
            raise CommandError(
                f"Command execution failed: {str(e)}. Please check the device connection and try again."
            ) from e
        except Exception as e:
            raise CommandError(
                f"An unexpected error occurred during command execution: {str(e)}. Please try again."
            ) from e

        device_error = _device_error_message(response)
        if device_error is not None:
            note = _UNATTRIBUTED_ERROR_NOTE if start is None else ""
            raise CommandError(
                f"Device rejected command {command!r}: "
                f"{device_error or 'no message'}{note}"
            )
        return response
