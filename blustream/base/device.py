"""Abstract base device class for Blustream devices."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from blustream.base.connection import Connection
from blustream.base.exceptions import CommandError, ConnectionError, TimeoutError

logger = logging.getLogger(__name__)

DEFAULT_RESPONSE_TIMEOUT = 5.0

SIMPLE_RESPONSE_MARKERS = ("[SUCCESS]", "[ERROR]")


def is_simple_marker(line: str) -> bool:
    """True for ``[SUCCESS]…\\r\\n`` or ``[ERROR]…\\r\\n`` lines.

    Default terminator for ``send_command``: every plain command, plus
    TEMP and UPTIME, ends with one of these marker lines.
    """
    return any(marker in line for marker in SIMPLE_RESPONSE_MARKERS)


class BlustreamDevice(ABC):
    """Abstract base class for all Blustream devices."""

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

    def _log_command(self, command: str) -> None:
        if not self._command_log_path:
            return
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            with open(self._command_log_path, "a", encoding="utf-8") as fh:
                fh.write(f"\n==== {ts} ====\ncommand: {command}\n")
        except OSError as e:
            logger.warning("Failed to write command log %s: %s", self._command_log_path, e)

    async def connect(self) -> None:
        if not self._connected:
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
    def get_commands(self) -> list[str]:
        ...

    @abstractmethod
    async def execute_command(self, name: str, **kwargs: Any) -> Any:
        ...

    @abstractmethod
    async def get_status(self) -> Any:
        ...

    async def send_command(
        self,
        command: str,
        *,
        terminator: Callable[[str], bool] = is_simple_marker,
        timeout: Optional[float] = None,
    ) -> str:
        """Send a command and return its complete response.

        The response is whatever the connection layer accumulates up to
        and including the first line for which ``terminator(line)``
        returns True. The default terminator matches the
        ``[SUCCESS]``/``[ERROR]`` marker line every plain command emits;
        callers issuing multi-section replies (e.g. STATUS) pass their
        own end-of-response predicate.

        ``send_command`` is intentionally response-shape agnostic — no
        per-command branching here, no sleep/quick-read heuristics, no
        substring sentinels. All that knowledge lives in the terminator
        the caller supplies.
        """
        if not self.is_connected:
            raise ConnectionError(
                "Device is not connected. Please call 'connect()' or use the device as a context manager before sending commands."
            )

        self._log_command(command)

        budget = timeout if timeout is not None else self._response_timeout

        try:
            await self._connection.send(command.encode("utf-8") + b"\r\n")
            return await self._connection.read_until(terminator, timeout=budget)
        except (ConnectionError, TimeoutError) as e:
            raise CommandError(
                f"Command execution failed: {str(e)}. Please check the device connection and try again."
            ) from e
        except Exception as e:
            raise CommandError(
                f"An unexpected error occurred during command execution: {str(e)}. Please try again."
            ) from e
