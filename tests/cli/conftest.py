"""CLI test fixtures.

The autouse ``_block_telnet`` fixture patches ``telnetlib3.open_connection``
so that any CLI test that accidentally makes a real network call fails
immediately with a clear message.
"""

from unittest.mock import patch

import pytest

SEATBELT_MESSAGE = (
    "telnetlib3.open_connection is blocked in CLI tests. "
    "Use the device_factory fixture to inject a "
    "MockConnection-backed device instead."
)


@pytest.fixture(autouse=True)
def _block_telnet():
    """Patch telnetlib3.open_connection to raise in all CLI tests."""

    def _blocked(*args, **kwargs):
        raise RuntimeError(SEATBELT_MESSAGE)

    with patch("telnetlib3.open_connection", side_effect=_blocked):
        yield
