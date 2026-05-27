"""Abstract base device class for Blustream devices."""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, List, Optional

from blustream.base.connection import Connection
from blustream.base.exceptions import CommandError, ConnectionError, TimeoutError

logger = logging.getLogger(__name__)

# Timeout constants (in seconds)
TIMEOUT_SHORT = 0.1  # Short timeout for quick reads and sleeps
TIMEOUT_INITIAL_READ = 0.5  # Initial read timeout used by the multi-read fallback
TIMEOUT_INFO_COMMAND = 0.3  # Per-read timeout for info commands (TEMP, UPTIME)
TIMEOUT_STATUS_COMMAND = 1.0  # Per-read timeout for STATUS
DEFAULT_RESPONSE_TIMEOUT = 2.0  # Overall budget to receive a marker-terminated reply

# Sleep durations (in seconds)
SLEEP_STATUS_COMMAND = 0.1  # Sleep before reading STATUS response
SLEEP_INFO_COMMAND = 0.2  # Sleep before reading info-command response
SLEEP_FINAL_READ = 0.2  # Sleep before the final STATUS read

# Response reading limits
MAX_READS_INFO = 10  # Maximum reads for info commands
MAX_READS_STATUS = 20  # Maximum reads for STATUS

# Response size threshold (info-command path)
RESPONSE_SIZE_SIMPLE = 2000

# Markers that delimit a simple command's reply. The device emits one of these
# tags followed by message text and a CRLF; the CRLF after the marker is the
# end-of-response signal.
SIMPLE_RESPONSE_MARKERS = (b"[SUCCESS]", b"[ERROR]")


class BlustreamDevice(ABC):
    """Abstract base class for all Blustream devices."""

    def __init__(
        self,
        connection: Connection,
        command_log_path: Optional[str] = None,
        response_timeout: float = DEFAULT_RESPONSE_TIMEOUT,
    ):
        """Initialize device with a connection.

        Args:
            connection: Connection instance for device communication
            command_log_path: Optional path to a text file. When set, every
                command sent via send_command is appended with a UTC timestamp,
                matching the format used by monitor_dmp168.sh.
            response_timeout: Overall budget (in seconds) for a simple command
                reply to arrive. If the device does not emit a ``[SUCCESS]`` or
                ``[ERROR]`` marker line within this window, the command fails.
        """
        self._connection = connection
        self._connected = False
        self._command_log_path = command_log_path
        self._response_timeout = response_timeout

    def _log_command(self, command: str) -> None:
        """Append a timestamped entry for the outgoing command.

        Best-effort: logging failures are reported via the module logger but
        never raised — the command must still be sent even if the log file
        is unwritable.
        """
        if not self._command_log_path:
            return
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            with open(self._command_log_path, "a", encoding="utf-8") as fh:
                fh.write(f"\n==== {ts} ====\ncommand: {command}\n")
        except OSError as e:
            logger.warning("Failed to write command log %s: %s", self._command_log_path, e)

    async def connect(self) -> None:
        """Connect to the device."""
        if not self._connected:
            await self._connection.connect()
            self._connected = True

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._connected:
            await self._connection.disconnect()
            self._connected = False

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    @property
    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self._connected and self._connection.is_connected()

    @abstractmethod
    def get_commands(self) -> List[str]:
        """Get list of available command names.

        Returns:
            List of command names this device supports
        """
        pass

    @abstractmethod
    async def execute_command(self, name: str, **kwargs: Any) -> Any:
        """Execute a command by name.

        Args:
            name: Command name
            **kwargs: Command parameters

        Returns:
            Command result (type depends on command)

        Raises:
            CommandError: If command execution fails
            ValidationError: If parameters are invalid
        """
        pass

    @abstractmethod
    async def get_status(self) -> Any:
        """Get device status.

        Returns:
            Device status object (device-specific)
        """
        pass

    async def _read_until_response_marker(self) -> str:
        """Accumulate inbound bytes until a SIMPLE_RESPONSE_MARKERS line ends.

        The device replies with either ``[SUCCESS]<message>\\r\\n`` or
        ``[ERROR]<message>\\r\\n`` (often preceded by an echo of the command).
        We keep reading until one of those marker tags is followed by ``\\r\\n``
        in the accumulated buffer.

        Raises:
            TimeoutError: If no complete marker line arrives within
                ``self._response_timeout`` seconds.
            ConnectionError: If the remote closes the connection before a
                marker is seen.
        """
        buffer = b""
        loop = asyncio.get_event_loop()
        deadline = loop.time() + self._response_timeout

        while True:
            for marker in SIMPLE_RESPONSE_MARKERS:
                idx = buffer.find(marker)
                if idx < 0:
                    continue
                end = buffer.find(b"\r\n", idx + len(marker))
                if end >= 0:
                    return buffer[: end + 2].decode("utf-8", errors="replace")

            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TimeoutError(
                    f"Response marker not received within {self._response_timeout:.1f}s. "
                    f"Got {len(buffer)} bytes: {buffer[:200]!r}"
                )

            try:
                chunk = await self._connection.receive(timeout=remaining)
            except TimeoutError as e:
                raise TimeoutError(
                    f"Response marker not received within {self._response_timeout:.1f}s. "
                    f"Got {len(buffer)} bytes: {buffer[:200]!r}"
                ) from e

            if not chunk:
                raise ConnectionError(
                    f"Connection closed before response marker. "
                    f"Got {len(buffer)} bytes: {buffer[:200]!r}"
                )

            buffer += chunk

    async def send_command(self, command: str) -> str:
        """Send a raw command string and return response.

        Args:
            command: Command string to send

        Returns:
            Response string from device

        Raises:
            ConnectionError: If not connected
            CommandError: If command fails
        """
        if not self.is_connected:
            raise ConnectionError(
                "Device is not connected. Please call 'connect()' or use the device as a context manager before sending commands."
            )

        self._log_command(command)

        try:
            # Send command
            await self._connection.send(command.encode("utf-8") + b"\r\n")

            is_status = command.upper() == "STATUS"
            # TEMP and UPTIME need more time to respond
            is_info_command = command.upper() in ["TEMP", "UPTIME"]

            # Simple commands reply with one of SIMPLE_RESPONSE_MARKERS followed
            # by a message line. Read until that line is complete — race-free
            # regardless of how the device chunks its echo and reply.
            if not is_status and not is_info_command:
                return await self._read_until_response_marker()

            # Multi-read logic for STATUS and info commands (TEMP/UPTIME). Simple
            # commands take the marker-based path above and never reach here.
            response_parts = []

            if is_status:
                await asyncio.sleep(SLEEP_STATUS_COMMAND)
            else:
                # TEMP and UPTIME need a moment before responding.
                await asyncio.sleep(SLEEP_INFO_COMMAND)

            max_reads = MAX_READS_STATUS if is_status else MAX_READS_INFO
            read_timeout = TIMEOUT_STATUS_COMMAND if is_status else TIMEOUT_INITIAL_READ
            timeout_threshold = read_timeout
            read_count = 0
            last_data_time = time.time()

            while read_count < max_reads:
                try:
                    chunk = await self._connection.receive(timeout=read_timeout)
                    if chunk:
                        response_parts.append(chunk)
                        last_data_time = time.time()
                        full_response = b"".join(response_parts).decode("utf-8", errors="replace")

                        if is_status:
                            # STATUS is complete when we see the input-settings section
                            # or at least three `===` separators.
                            if "Input Settings Status" in full_response or full_response.count("===") >= 3:
                                try:
                                    await asyncio.sleep(SLEEP_FINAL_READ)
                                    more = await self._connection.receive(timeout=TIMEOUT_INITIAL_READ)
                                    if more:
                                        response_parts.append(more)
                                except (TimeoutError, ConnectionError):
                                    pass
                                break
                        else:
                            # TEMP/UPTIME: the device echoes the command then returns
                            # the value. Drain briefly to ensure we have the value,
                            # not just the echo.
                            if len(full_response) < RESPONSE_SIZE_SIMPLE:
                                try:
                                    await asyncio.sleep(TIMEOUT_SHORT)
                                    more = await self._connection.receive(timeout=TIMEOUT_INFO_COMMAND)
                                    if more:
                                        response_parts.append(more)
                                        full_response = b"".join(response_parts).decode("utf-8", errors="replace")
                                except (TimeoutError, ConnectionError):
                                    pass
                                # Heuristic: TEMP shows digits + "C", UPTIME shows colons.
                                if (":" in full_response or "C" in full_response.upper() or
                                        any(c.isdigit() for c in full_response)):
                                    try:
                                        more = await self._connection.receive(timeout=TIMEOUT_SHORT)
                                        if more:
                                            response_parts.append(more)
                                    except (TimeoutError, ConnectionError):
                                        pass
                                    break
                    else:
                        # No data this iteration; if we've been idle past the
                        # per-iteration threshold and have something buffered, stop.
                        if time.time() - last_data_time > timeout_threshold and response_parts:
                            break
                except (TimeoutError, ConnectionError):
                    if response_parts:
                        full_response = b"".join(response_parts).decode("utf-8", errors="replace")
                        # STATUS minimally OK once we have the header section.
                        if is_status and "Power" in full_response and "Baud" in full_response:
                            break
                        # Info commands accept any accumulated data on timeout.
                        if not is_status:
                            break
                    if read_count == 0:
                        raise
                    if not response_parts:
                        raise
                    break
                read_count += 1

            full_response = b"".join(response_parts).decode("utf-8", errors="replace")
            return full_response
        except (ConnectionError, TimeoutError) as e:
            raise CommandError(
                f"Command execution failed: {str(e)}. Please check the device connection and try again."
            ) from e
        except Exception as e:
            raise CommandError(
                f"An unexpected error occurred during command execution: {str(e)}. Please try again."
            ) from e

