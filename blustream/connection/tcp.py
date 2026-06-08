"""TCP/IP connection implementation using telnetlib3 for Telnet protocol."""

import asyncio
import logging
import re
from typing import Callable, Optional

import telnetlib3

from blustream.base.connection import Connection
from blustream.base.exceptions import ConnectionError, TimeoutError

logger = logging.getLogger(__name__)

BUFFER_SIZE_INITIAL = 1024
BUFFER_SIZE_RECEIVE = 4096

# Hard ceiling on a single ``read_until`` accumulation. The library is a
# LAN client pointed at an operator-trusted device, but a malfunctioning
# or hostile device could otherwise stream indefinitely within the read
# timeout window and inflate memory. 1 MiB is far larger than any real
# DMP168 response (a full STATUS dump is a few KiB).
MAX_RESPONSE_CHARS = 1024 * 1024

DEFAULT_BANNER_TIMEOUT = 2.0
TIMEOUT_WAIT_CLOSED = 1.0

# Per-read budget for the pre-send drain in ``send()``. The drain is a
# best-effort flush of anything the kernel already has buffered for us
# right now — typically the welcome-banner re-broadcasts the device
# sends to every connected port-23 client when another client connects.
# This is NOT a framing knob: ``read_until`` does the real framing and
# strips any banner bytes that arrive after the drain. The budget only
# has to be long enough to scoop up bytes that are immediately
# readable; anything that arrives later is handled in the read path.
DRAIN_PENDING_POLL = 0.05

BANNER_SENTINEL = "=\r\n"
BANNER_SENTINEL_COUNT = 2

LINE_TERMINATOR = "\r\n"

# Welcome-banner pattern. The DMP168 broadcasts this entire block to
# every currently-connected port-23 client whenever a new client
# connects, so a long-lived connection accumulates re-broadcast banners
# between the commands it actually issues. Stripping the pattern from
# the buffer before line consumption keeps responses clean regardless
# of when the broadcast arrives — before, during, or after our command.
BANNER_PATTERN = re.compile(
    r"={16,}\r\n"
    r"Welcome to DMP168[^\r\n]*\r\n"
    r"(?:[^\r\n]*\r\n)*?"
    r"={16,}\r\n"
)


def _strip_banner_broadcasts(buffer: str) -> str:
    """Remove any complete welcome-banner blocks from ``buffer``.

    Only complete banners (with both top and bottom sentinel lines) are
    stripped; a partial banner whose bottom hasn't arrived yet stays in
    the buffer so a subsequent read can complete it. Once the banner is
    whole, the next strip clears it. Returns the cleaned buffer.
    """
    return BANNER_PATTERN.sub("", buffer)


class TCPConnection(Connection):
    """TCP/IP connection using telnetlib3 for Telnet protocol support.

    Maintains a per-connection line buffer so reads frame on ``\\r\\n``
    rather than on chunk boundaries. Any bytes that arrive after a
    satisfied ``read_until`` stay in the buffer for the next call — the
    DMP168 streams its STATUS reply over hundreds of milliseconds with
    mid-message pauses, so chunk-boundary heuristics ("got less than full
    buffer, must be done") return premature partial responses and leave
    the tail to bleed into the next command's reply.
    """

    def __init__(
        self,
        host: str,
        port: int = 23,
        timeout: float = 5.0,
        response_timeout: float = 5.0,
        banner_timeout: float = DEFAULT_BANNER_TIMEOUT,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.response_timeout = response_timeout
        self.banner_timeout = banner_timeout
        self._reader: Optional[telnetlib3.TelnetReader] = None
        self._writer: Optional[telnetlib3.TelnetWriter] = None
        self._connected = False
        self._buffer = ""

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
            self._buffer = ""

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
            raise
        except Exception as e:
            raise ConnectionError(
                f"An unexpected error occurred while connecting to {self.host}:{self.port}: {str(e)}. "
                f"Please check the device connection and try again."
            ) from e

    async def _discard_initial_data(self) -> None:
        """Best-effort: consume the welcome banner if one arrives.

        Port 23 (telnet) emits a banner bracketed by two ``=…=\\r\\n``
        sentinels; port 8000 (raw TCP) emits nothing. Under load the
        device sometimes serves the banner slowly or not at all to a
        new connection (especially when other clients are connecting
        simultaneously). Treat all of these as fine — the framing layer
        does not depend on banner discard for correctness, and the
        per-send drain in ``send()`` cleans up any banner-shaped noise
        that arrives later.
        """
        if not self._reader:
            return

        buffer = ""
        loop = asyncio.get_event_loop()
        deadline = loop.time() + self.banner_timeout

        while buffer.count(BANNER_SENTINEL) < BANNER_SENTINEL_COUNT:
            remaining = deadline - loop.time()
            if remaining <= 0:
                logger.debug(
                    f"Banner discard giving up after {self.banner_timeout:.1f}s; got {len(buffer)} chars"
                )
                return

            try:
                chunk = await asyncio.wait_for(
                    self._reader.read(BUFFER_SIZE_INITIAL),
                    timeout=remaining,
                )
            except asyncio.TimeoutError:
                logger.debug(
                    f"Banner discard timed out after {self.banner_timeout:.1f}s; got {len(buffer)} chars"
                )
                return

            if not chunk:
                logger.debug(
                    f"Remote closed during banner discard; got {len(buffer)} chars"
                )
                return

            buffer += chunk

        logger.debug(f"Discarded welcome banner: {len(buffer)} chars")

    async def disconnect(self) -> None:
        """Close TCP connection."""
        if self._writer:
            try:
                self._writer.close()
                try:
                    await asyncio.wait_for(
                        self._writer.wait_closed(), timeout=TIMEOUT_WAIT_CLOSED
                    )
                except asyncio.TimeoutError:
                    pass
            except Exception as e:
                error_msg = str(e)
                if "feed_data after feed_eof" not in error_msg:
                    logger.warning(f"Error closing connection: {e}")
            finally:
                self._reader = None
                self._writer = None
                self._connected = False
                self._buffer = ""
                logger.info(f"Disconnected from {self.host}:{self.port}")

    async def send(self, data: bytes) -> None:
        """Send bytes after draining any unsolicited pending data.

        The DMP168 on port 23 broadcasts its welcome banner to every
        currently-connected client whenever a new client connects, so a
        long-lived connection accumulates banner re-broadcasts between
        the commands it actually issues. Draining the line buffer and
        any immediately-readable bytes here makes the post-send read
        deterministic — whatever arrives next is the device's response
        to the command we just sent, not stale broadcast noise.
        """
        if not self._connected or not self._writer:
            raise ConnectionError(
                "Connection is not active. Please ensure the device is connected before sending data."
            )

        await self._drain_pending()

        try:
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

    async def _drain_pending(self) -> None:
        """Discard whatever bytes the reader has buffered right now.

        Reads in a tight loop with a short timeout; the first read that
        finds no data within the budget breaks the loop. Also resets the
        line buffer so a partial-line tail from a prior abandoned read
        cannot prefix the next response.
        """
        if not self._reader:
            return

        discarded = 0
        if self._buffer:
            discarded += len(self._buffer)
            self._buffer = ""

        while True:
            try:
                chunk = await asyncio.wait_for(
                    self._reader.read(BUFFER_SIZE_RECEIVE),
                    timeout=DRAIN_PENDING_POLL,
                )
            except asyncio.TimeoutError:
                break
            except BaseException:
                # StopAsyncIteration from exhausted AsyncMock side_effect in
                # tests; treat any non-timeout signal as "no more buffered
                # data right now" rather than letting the drain trip the
                # whole send.
                break
            if not chunk:
                break
            discarded += len(chunk)

        if discarded:
            logger.debug(f"Drained {discarded} pending chars before send")

    async def read_until(
        self,
        predicate: Callable[[str], bool],
        timeout: float,
    ) -> str:
        """Read complete CRLF-terminated lines until ``predicate(line)`` is True.

        Maintains the per-connection ``_buffer`` so any bytes that arrive
        after the satisfying line stay queued for the next call. Each
        complete line — including its ``\\r\\n`` terminator — is passed
        to ``predicate``; the first line that returns True ends the read.
        """
        if not self._connected or not self._reader:
            raise ConnectionError(
                "Connection is not active. Please ensure the device is connected before receiving data."
            )

        accumulated = ""
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout

        while True:
            self._buffer = _strip_banner_broadcasts(self._buffer)
            consumed, satisfied, leftover = self._consume_lines(self._buffer, predicate)
            accumulated += consumed
            self._buffer = leftover
            if satisfied:
                return accumulated

            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TimeoutError(
                    f"No matching line received within {timeout:.1f}s. "
                    f"Got {len(accumulated)} chars; buffer holds {len(self._buffer)} chars."
                )

            try:
                chunk_str = await asyncio.wait_for(
                    self._reader.read(BUFFER_SIZE_RECEIVE),
                    timeout=remaining,
                )
            except asyncio.TimeoutError as e:
                raise TimeoutError(
                    f"No matching line received within {timeout:.1f}s. "
                    f"Got {len(accumulated)} chars; buffer holds {len(self._buffer)} chars."
                ) from e
            except (OSError, UnicodeEncodeError) as e:
                self._connected = False
                raise ConnectionError(
                    f"Failed to receive data from device: {str(e)}. The connection may have been lost. "
                    f"Please check the device connection and try again."
                ) from e

            if not chunk_str:
                raise ConnectionError(
                    f"Connection closed before a matching line arrived. "
                    f"Got {len(accumulated)} chars; buffer holds {len(self._buffer)} chars."
                )

            self._buffer += chunk_str
            logger.debug(
                f"Received {len(chunk_str)} chars; buffer now {len(self._buffer)}"
            )

            if len(accumulated) + len(self._buffer) > MAX_RESPONSE_CHARS:
                raise ConnectionError(
                    f"Response exceeded {MAX_RESPONSE_CHARS} chars without a "
                    f"matching line; aborting to avoid unbounded buffering. "
                    f"The device may be malfunctioning."
                )

    @staticmethod
    def _consume_lines(
        buffer: str,
        predicate: Callable[[str], bool],
    ) -> tuple[str, bool, str]:
        """Pull complete CRLF-terminated lines off the front of ``buffer``.

        Returns ``(consumed, satisfied, leftover)``. ``consumed`` is the
        concatenation of every complete line drained (each ending in
        ``\\r\\n``). ``satisfied`` is True if some consumed line caused
        ``predicate`` to return True — at which point we stop draining
        and return whatever follows that line as ``leftover``.
        """
        consumed = ""
        pos = 0
        while True:
            idx = buffer.find(LINE_TERMINATOR, pos)
            if idx < 0:
                break
            line_end = idx + len(LINE_TERMINATOR)
            line = buffer[pos:line_end]
            consumed += line
            pos = line_end
            if predicate(line):
                return consumed, True, buffer[pos:]
        return consumed, False, buffer[pos:]

    def is_connected(self) -> bool:
        return self._connected and self._reader is not None and self._writer is not None
