"""Abstract connection interface for Bluestream devices."""

from abc import ABC, abstractmethod


class Connection(ABC):
    """Abstract base class for device connections."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the device."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the device."""
        pass

    @abstractmethod
    async def send(self, data: bytes) -> None:
        """Send data to the device."""
        pass

    @abstractmethod
    async def receive(self, timeout: float = 5.0) -> bytes:
        """Receive data from the device."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connection is active."""
        pass

