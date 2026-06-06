"""Tests for the CLI test seatbelt."""

import pytest
import telnetlib3


class TestSeatbelt:
    """Verify the autouse seatbelt blocks real telnetlib3 connections."""

    @pytest.mark.asyncio
    async def test_open_connection_raises_with_seatbelt_message(self):
        """Calling telnetlib3.open_connection in a CLI test raises RuntimeError."""
        with pytest.raises(RuntimeError, match="telnetlib3.open_connection"):
            await telnetlib3.open_connection("192.0.2.1", 23)
