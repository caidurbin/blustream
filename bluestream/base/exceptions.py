"""Custom exception hierarchy for Bluestream devices."""


class BluestreamError(Exception):
    """Base exception for all Bluestream errors."""

    pass


class ConnectionError(BluestreamError):
    """Raised when connection-related errors occur."""

    pass


class CommandError(BluestreamError):
    """Raised when command execution fails."""

    pass


class ParseError(BluestreamError):
    """Raised when response parsing fails."""

    pass


class ValidationError(BluestreamError):
    """Raised when parameter validation fails."""

    pass


class TimeoutError(BluestreamError):
    """Raised when an operation times out."""

    pass

