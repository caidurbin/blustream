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
TIMEOUT_PROMPT_CHECK = 0.05  # Very short timeout for prompt detection
TIMEOUT_SHORT = 0.1  # Short timeout for quick reads and sleeps
TIMEOUT_INITIAL_READ = 0.5  # Initial read timeout for simple commands
TIMEOUT_INFO_COMMAND = 0.3  # Timeout for info commands (TEMP, UPTIME)
TIMEOUT_STATUS_COMMAND = 1.0  # Timeout for STATUS command reads

# Sleep durations (in seconds)
SLEEP_STATUS_COMMAND = 0.1  # Sleep before reading STATUS command response
SLEEP_INFO_COMMAND = 0.2  # Sleep before reading info command response
SLEEP_FINAL_READ = 0.2  # Sleep before final read for STATUS command

# Response reading limits
MAX_READS_SIMPLE = 5  # Maximum reads for simple commands
MAX_READS_INFO = 10  # Maximum reads for info commands
MAX_READS_STATUS = 20  # Maximum reads for STATUS command

# Response size thresholds
RESPONSE_SIZE_SHORT = 100  # Threshold for short response detection
RESPONSE_SIZE_SIMPLE = 2000  # Threshold for simple command response size


class BlustreamDevice(ABC):
    """Abstract base class for all Blustream devices."""

    def __init__(self, connection: Connection, command_log_path: Optional[str] = None):
        """Initialize device with a connection.

        Args:
            connection: Connection instance for device communication
            command_log_path: Optional path to a text file. When set, every
                command sent via send_command is appended with a UTC timestamp,
                matching the format used by monitor_dmp168.sh.
        """
        self._connection = connection
        self._connected = False
        self._command_log_path = command_log_path

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

            # For simple commands, use newline-based detection
            # STATUS commands need special multi-line handling
            if not is_status and not is_info_command:
                # Simple commands typically return single-line or short responses
                # Read until we see a newline, then check for prompt or short timeout
                response_parts = []

                try:
                    # Initial read with reasonable timeout
                    chunk = await self._connection.receive(timeout=TIMEOUT_INITIAL_READ)
                    if chunk:
                        response_parts.append(chunk)
                        response_text = chunk.decode("utf-8", errors="replace")

                        # Check if we have a newline (response likely complete)
                        if "\n" in response_text or "\r\n" in response_text:
                            # Check if prompt follows (device prompt typically ends with ">")
                            # Try a very short read to see if prompt comes
                            try:
                                prompt_chunk = await self._connection.receive(timeout=TIMEOUT_SHORT)
                                if prompt_chunk:
                                    prompt_text = prompt_chunk.decode("utf-8", errors="replace")
                                    response_parts.append(prompt_chunk)
                                    response_text += prompt_text

                                    # If we see a prompt pattern (ends with ">"), response is definitely complete
                                    if response_text.rstrip().endswith(">"):
                                        return b"".join(response_parts).decode("utf-8", errors="replace")
                            except (TimeoutError, ConnectionError):
                                # Timeout on prompt check is OK - might not have prompt
                                pass

                            # If we got a newline but no prompt, do one more very short check
                            # to ensure no more data is coming
                            try:
                                more = await self._connection.receive(timeout=TIMEOUT_PROMPT_CHECK)
                                if more:
                                    response_parts.append(more)
                                    response_text += more.decode("utf-8", errors="replace")
                                    # Check again for prompt
                                    if response_text.rstrip().endswith(">"):
                                        return b"".join(response_parts).decode("utf-8", errors="replace")
                            except (TimeoutError, ConnectionError):
                                # No more data after newline - response is complete
                                pass

                            # We have a newline and no more data came - response is complete
                            return b"".join(response_parts).decode("utf-8", errors="replace")

                        # No newline yet, but got some data - might be incomplete
                        # Check if it looks like a complete response anyway (very short)
                        if len(response_text) < RESPONSE_SIZE_SHORT and len(response_text.strip()) > 0:
                            # Very short response without newline - might be complete
                            # Do a quick check for more data
                            try:
                                more = await self._connection.receive(timeout=TIMEOUT_SHORT)
                                if more:
                                    response_parts.append(more)
                            except (TimeoutError, ConnectionError):
                                # No more data - return what we have
                                pass
                            return b"".join(response_parts).decode("utf-8", errors="replace")

                        # If we got here, response might be incomplete
                        # Fall through to multi-read logic below

                except (TimeoutError, ConnectionError, ValueError):
                    # If newline-based read fails, fall through to multi-read logic
                    pass

            # Multi-read logic for STATUS or if fast read didn't work
            response_parts = []

            # Only sleep for STATUS commands (they need more processing time)
            if is_status:
                await asyncio.sleep(SLEEP_STATUS_COMMAND)
            elif is_info_command:
                # TEMP and UPTIME need a bit of time to respond
                await asyncio.sleep(SLEEP_INFO_COMMAND)

            # Read until we have a complete response
            # STATUS responses end with input settings section
            max_reads = MAX_READS_STATUS if is_status else (MAX_READS_INFO if is_info_command else MAX_READS_SIMPLE)
            read_count = 0
            last_data_time = time.time()

            # Read with longer timeout for STATUS command
            read_timeout = TIMEOUT_STATUS_COMMAND if is_status else (TIMEOUT_INITIAL_READ if is_info_command else TIMEOUT_INFO_COMMAND)

            while read_count < max_reads:
                try:
                    chunk = await self._connection.receive(timeout=read_timeout)
                    if chunk:
                        response_parts.append(chunk)
                        last_data_time = time.time()
                        # Check if we have complete response
                        full_response = b"".join(response_parts).decode("utf-8", errors="replace")
                        # STATUS is complete when we see "Input Settings Status" or multiple ===
                        if is_status:
                            if "Input Settings Status" in full_response or full_response.count("===") >= 3:
                                # Try one more read to get any remaining data
                                try:
                                    await asyncio.sleep(SLEEP_FINAL_READ)
                                    more = await self._connection.receive(timeout=TIMEOUT_INITIAL_READ)
                                    if more:
                                        response_parts.append(more)
                                except (TimeoutError, ConnectionError):
                                    pass
                                break
                        else:
                            # For simple commands, use newline-based completion detection
                            if len(full_response) < RESPONSE_SIZE_SIMPLE:
                                # For info commands (TEMP, UPTIME), wait a bit longer and check for more data
                                if is_info_command:
                                    # These commands might echo the command, then return the value
                                    # Wait a bit and try to get more data
                                    try:
                                        await asyncio.sleep(TIMEOUT_SHORT)
                                        more = await self._connection.receive(timeout=TIMEOUT_INFO_COMMAND)
                                        if more:
                                            response_parts.append(more)
                                            full_response = b"".join(response_parts).decode("utf-8", errors="replace")
                                    except (TimeoutError, ConnectionError):
                                        pass
                                    # Check if we have the actual value (not just command echo)
                                    # TEMP should have a number and C, UPTIME should have colons
                                    if (is_info_command and
                                        (":" in full_response or "C" in full_response.upper() or
                                         any(c.isdigit() for c in full_response))):
                                        # We likely have the value, but try one more quick check
                                        try:
                                            more = await self._connection.receive(timeout=TIMEOUT_SHORT)
                                            if more:
                                                response_parts.append(more)
                                        except (TimeoutError, ConnectionError):
                                            pass
                                        break
                                else:
                                    # For simple commands, check for newline + prompt or newline + no more data
                                    if "\n" in full_response or "\r\n" in full_response:
                                        # Check for prompt (device prompt typically ends with ">")
                                        if full_response.rstrip().endswith(">"):
                                            # Response complete - found prompt
                                            break

                                        # No prompt, but have newline - check if more data is coming
                                        try:
                                            more = await self._connection.receive(timeout=TIMEOUT_PROMPT_CHECK)
                                            if more:
                                                response_parts.append(more)
                                                full_response = b"".join(response_parts).decode("utf-8", errors="replace")
                                                # Check again for prompt
                                                if full_response.rstrip().endswith(">"):
                                                    break
                                            else:
                                                # No more data after newline - response complete
                                                break
                                        except (TimeoutError, ConnectionError):
                                            # No more data available after newline - response complete
                                            break
                    else:
                        # No data - if we haven't received anything in a while, we're done
                        timeout_threshold = TIMEOUT_STATUS_COMMAND if is_status else (TIMEOUT_INITIAL_READ if is_info_command else TIMEOUT_INFO_COMMAND)
                        if time.time() - last_data_time > timeout_threshold and response_parts:
                            break
                except (TimeoutError, ConnectionError):
                    # Timeout or error - if we have substantial data, use it
                    if response_parts:
                        full_response = b"".join(response_parts).decode("utf-8", errors="replace")
                        # If we have the status header, we might have enough
                        if is_status and "Power" in full_response and "Baud" in full_response:
                            break
                        # For simple commands, any data is likely complete
                        if not is_status:
                            break
                    if read_count == 0:
                        # First read failed - re-raise
                        raise
                    # Subsequent timeouts are OK if we have data
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

