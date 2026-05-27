"""TCP/IP connection implementation using telnetlib3 for Telnet protocol."""

import asyncio
import logging
from typing import Optional

import telnetlib3

from blustream.base.connection import Connection
from blustream.base.exceptions import ConnectionError, TimeoutError

logger = logging.getLogger(__name__)

# Buffer size constants (in bytes/characters)
BUFFER_SIZE_INITIAL = 1024  # Buffer size for reading initial data
BUFFER_SIZE_RECEIVE = 4096  # Buffer size for normal receive operations

# Timeout constants (in seconds)
DEFAULT_BANNER_TIMEOUT = 2.0  # Overall budget to consume the welcome banner
TIMEOUT_WAIT_CLOSED = 1.0  # Timeout for waiting for connection to close
TIMEOUT_QUICK_READ = 0.1  # Quick read timeout for catching remaining data

# Welcome-banner sentinel
BANNER_SENTINEL = "=\r\n"  # The DMP168 banner brackets itself with two "=…=\r\n" lines
BANNER_SENTINEL_COUNT = 2  # Stop after consuming this many sentinels


class TCPConnection(Connection):
    """TCP/IP connection using telnetlib3 for Telnet protocol support."""

    def __init__(
        self,
        host: str,
        port: int = 23,
        timeout: float = 5.0,
        response_timeout: float = 5.0,
        banner_timeout: float = DEFAULT_BANNER_TIMEOUT,
    ):
        """Initialize TCP connection.

        Args:
            host: Device hostname or IP address
            port: TCP port (default 23 for Telnet)
            timeout: Connection timeout in seconds
            response_timeout: Response read timeout in seconds
            banner_timeout: Overall budget for consuming the welcome banner on
                connect. If the banner's two ``=\\r\\n`` sentinels are not seen
                within this many seconds, the connect fails.
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.response_timeout = response_timeout
        self.banner_timeout = banner_timeout
        self._reader: Optional[telnetlib3.TelnetReader] = None
        self._writer: Optional[telnetlib3.TelnetWriter] = None
        self._connected = False

    async def connect(self) -> None:
        """Establish TCP connection to device using telnetlib3."""
        if self._connected:
            return

        try:
            self._reader, self._writer = await asyncio.wait_for(
                telnetlib3.open_connection(self.host, self.port),
                timeout=self.timeout,
            )
            self._connected = True

            # telnetlib3 handles Telnet negotiation automatically, but we may still
            # need to discard initial welcome message data
            await self._discard_initial_data()

            logger.info(f"Connected to {self.host}:{self.port}")
        except asyncio.TimeoutError as e:
            raise TimeoutError(
                f"Connection timeout while trying to connect to {self.host}:{self.port}. "
                f"Please check that the device is powered on, connected to the network, and the host/port are correct."
            ) from e
        except OSError as e:
            raise ConnectionError(
                f"Unable to connect to device at {self.host}:{self.port}. "
                f"Error: {str(e)}. Please check the network connection, host address, and port number."
            ) from e
        except (TimeoutError, ConnectionError):
            # Banner-discard errors are already shaped for the user; pass through.
            raise
        except Exception as e:
            raise ConnectionError(
                f"An unexpected error occurred while connecting to {self.host}:{self.port}: {str(e)}. "
                f"Please check the device connection and try again."
            ) from e

    async def _discard_initial_data(self) -> None:
        """Consume the welcome banner up to its bottom ``=…=\\r\\n`` sentinel.

        The DMP168 brackets its banner with two lines of ``=`` characters
        terminated by ``\\r\\n``. We accumulate inbound data until two such
        sentinels have been seen — race-free regardless of how the banner is
        chunked across TCP packets.

        If both sentinels do not arrive within ``self.banner_timeout``
        seconds, raise ``TimeoutError`` so the caller fails the connect.
        """
        if not self._reader:
            return

        buffer = ""
        loop = asyncio.get_event_loop()
        deadline = loop.time() + self.banner_timeout

        while buffer.count(BANNER_SENTINEL) < BANNER_SENTINEL_COUNT:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TimeoutError(
                    f"Welcome banner not consumed within {self.banner_timeout:.1f}s. "
                    f"Got {len(buffer)} chars, expected two '=\\r\\n' sentinels. "
                    f"The device may be unresponsive, or this port does not emit a banner."
                )

            try:
                chunk = await asyncio.wait_for(
                    self._reader.read(BUFFER_SIZE_INITIAL),
                    timeout=remaining,
                )
            except asyncio.TimeoutError as e:
                raise TimeoutError(
                    f"Welcome banner not consumed within {self.banner_timeout:.1f}s. "
                    f"Got {len(buffer)} chars, expected two '=\\r\\n' sentinels. "
                    f"The device may be unresponsive, or this port does not emit a banner."
                ) from e

            if not chunk:
                raise ConnectionError(
                    f"Connection closed by remote during welcome banner. "
                    f"Got {len(buffer)} chars."
                )

            buffer += chunk

        logger.debug(f"Discarded welcome banner: {len(buffer)} chars")

    async def disconnect(self) -> None:
        """Close TCP connection."""
        if self._writer:
            try:
                # Close the writer - telnetlib3 will handle cleanup
                self._writer.close()
                # Wait for close with a timeout to avoid hanging
                try:
                    await asyncio.wait_for(self._writer.wait_closed(), timeout=TIMEOUT_WAIT_CLOSED)
                except asyncio.TimeoutError:
                    # If wait_closed times out, the connection is likely already closed
                    pass
            except Exception as e:
                # Suppress "feed_data after feed_eof" errors from telnetlib3
                # These are harmless race conditions that occur when closing
                error_msg = str(e)
                if "feed_data after feed_eof" not in error_msg:
                    logger.warning(f"Error closing connection: {e}")
            finally:
                self._reader = None
                self._writer = None
                self._connected = False
                logger.info(f"Disconnected from {self.host}:{self.port}")

    async def send(self, data: bytes) -> None:
        """Send data to device.

        Args:
            data: Data bytes to send

        Raises:
            ConnectionError: If not connected
        """
        if not self._connected or not self._writer:
            raise ConnectionError(
                "Connection is not active. Please ensure the device is connected before sending data."
            )

        try:
            # telnetlib3 works in text mode, so convert bytes to string
            data_str = data.decode("utf-8", errors="replace")
            self._writer.write(data_str)
            await self._writer.drain()
            logger.debug(f"Sent: {data!r}")
        except (OSError, UnicodeDecodeError) as e:
            self._connected = False
            raise ConnectionError(
                f"Failed to send data to device: {str(e)}. The connection may have been lost. "
                f"Please check the device connection and try again."
            ) from e

    async def receive(self, timeout: Optional[float] = None) -> bytes:
        """Receive data from device.

        Reads data until timeout or connection closes. For multi-line responses,
        continues reading until no more data is available.

        Args:
            timeout: Optional timeout override

        Returns:
            Received data bytes

        Raises:
            ConnectionError: If not connected
            TimeoutError: If read times out
        """
        if not self._connected or not self._reader:
            raise ConnectionError(
                "Connection is not active. Please ensure the device is connected before receiving data."
            )

        read_timeout = timeout if timeout is not None else self.response_timeout
        data_parts = []

        try:
            while True:
                try:
                    # telnetlib3 works in text mode, so read() returns a string
                    chunk_str = await asyncio.wait_for(
                        self._reader.read(BUFFER_SIZE_RECEIVE),
                        timeout=read_timeout,
                    )
                    if not chunk_str:
                        break
                    # Convert string to bytes
                    chunk = chunk_str.encode("utf-8", errors="replace")
                    data_parts.append(chunk)
                    # If we got less than full buffer size, likely end of transmission
                    if len(chunk_str) < BUFFER_SIZE_RECEIVE:
                        # Try one more quick read to catch any remaining data
                        try:
                            more_str = await asyncio.wait_for(
                                self._reader.read(BUFFER_SIZE_RECEIVE),
                                timeout=TIMEOUT_QUICK_READ,
                            )
                            if more_str:
                                more = more_str.encode("utf-8", errors="replace")
                                data_parts.append(more)
                        except asyncio.TimeoutError:
                            pass
                        break
                except asyncio.TimeoutError:
                    # Timeout is OK if we've already received some data
                    if data_parts:
                        break
                    raise TimeoutError(
                        "Device did not respond within the expected time. "
                        "The device may be busy or unresponsive. Please try again."
                    )

            data = b"".join(data_parts)
            logger.debug(f"Received: {len(data)} bytes")
            return data
        except asyncio.TimeoutError as e:
            raise TimeoutError(
                "Device did not respond within the expected time. "
                "The device may be busy or unresponsive. Please try again."
            ) from e
        except (OSError, UnicodeEncodeError) as e:
            self._connected = False
            raise ConnectionError(
                f"Failed to receive data from device: {str(e)}. The connection may have been lost. "
                f"Please check the device connection and try again."
            ) from e

    def is_connected(self) -> bool:
        """Check if connection is active.

        Returns:
            True if connected, False otherwise
        """
        return self._connected and self._reader is not None and self._writer is not None

