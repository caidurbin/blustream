"""Abstract connection interface for Blustream devices."""

from abc import ABC, abstractmethod
from typing import Callable


class Connection(ABC):
    """Abstract base class for device connections.

    Implementations are responsible for line-aware framing: reads must
    deliver complete ``\\r\\n``-terminated lines, and any bytes that arrive
    after a satisfied read must be buffered for the next call so a slow
    or chunked response cannot bleed into the next command's reply.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the device."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the device."""

    @abstractmethod
    async def send(self, data: bytes) -> None:
        """Send data to the device."""

    @abstractmethod
    async def read_until(
        self,
        predicate: Callable[[str], bool],
        timeout: float,
    ) -> str:
        """Read complete CRLF-terminated lines until ``predicate(line)`` is True.

        Accumulates lines as they arrive and calls ``predicate`` on each
        complete line. As soon as the predicate returns True, returns the
        full accumulated text up to and including that terminating line.
        Any bytes already received past that line stay in the connection
        buffer for the next ``read_until`` call.

        Args:
            predicate: Function called with each complete line (including
                its terminator). When it returns True, the read completes.
            timeout: Overall budget in seconds for a satisfying line to
                arrive. Tolerant of mid-message pauses — the timeout only
                trips when no satisfying line is seen within the window.

        Returns:
            All accumulated text up to and including the line that
            satisfied the predicate.

        Raises:
            ConnectionError: Connection is not active or the remote
                closed before the predicate was satisfied.
            TimeoutError: ``timeout`` elapsed before a satisfying line
                arrived.
        """

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connection is active."""

    @property
    def echoes_commands(self) -> bool:
        """Whether the device echoes each command line ahead of its reply.

        On a link that echoes, ``BlustreamDevice.send_command`` reads our
        reply from our own echo onward, so a reply the device broadcasts
        for another client is never taken as ours. The base connection
        reports False: no echo is expected and replies are matched by
        their shape only.
        """
        return False
