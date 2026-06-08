"""Custom exception hierarchy for Blustream devices."""

from typing import Optional


class BlustreamError(Exception):
    """Base exception for all Blustream errors."""

    pass


class ConnectionError(BlustreamError):
    """Raised when connection-related errors occur."""

    pass


class CommandError(BlustreamError):
    """Raised when command execution fails."""

    pass


class ParseError(BlustreamError):
    """Raised when response parsing fails."""

    pass


class ValidationError(BlustreamError):
    """Raised when parameter validation fails.

    Attributes:
        errors: List of (parameter_name, message) tuples.
    """

    def __init__(self, message: str, errors: Optional[list[tuple[str, str]]] = None):
        self.errors: list[tuple[str, str]] = errors or []
        super().__init__(message)


class TimeoutError(BlustreamError):
    """Raised when an operation times out."""

    pass
