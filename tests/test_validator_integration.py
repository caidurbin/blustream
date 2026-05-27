"""Integration tests: validator wiring through device.execute_command."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from blustream.base.exceptions import ValidationError
from blustream.devices.dmp168.device import DMP168


class TestValidatorIntegration:
    """Verify execute_command uses the centralized validator."""

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_multiple_errors_collected_via_execute_command(
        self, mock_connection_class
    ):
        """execute_command should collect all validation errors, not just first."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        await device.connect()

        with pytest.raises(ValidationError) as exc_info:
            await device.execute_command(
                "output_volume",
                output=99,
                level=50,
                channel="INVALID",
            )
        error = exc_info.value
        assert hasattr(error, "errors")
        assert len(error.errors) == 2
        param_names = [name for name, _ in error.errors]
        assert "output" in param_names
        assert "channel" in param_names

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_validation_callable_fires_via_execute_command(
        self, mock_connection_class
    ):
        """validation= callable on Parameter should fire through execute_command."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        await device.connect()

        with pytest.raises(ValidationError) as exc_info:
            await device.execute_command(
                "output_delay",
                output=1,
                delay_ms=999,
            )
        assert "delay_ms" in str(exc_info.value) or "Delay" in str(
            exc_info.value
        )

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_valid_command_still_works(self, mock_connection_class):
        """Valid commands should pass validation and execute normally."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        mock_conn.receive = AsyncMock(return_value=b"[SUCCESS]ok\r\n")
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        await device.connect()

        result = await device.execute_command(
            "output_volume", output=1, level=50
        )
        assert result is not None

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_missing_params_collected(self, mock_connection_class):
        """Missing required params should all be collected."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        await device.connect()

        with pytest.raises(ValidationError) as exc_info:
            await device.execute_command("output_volume")
        error = exc_info.value
        assert hasattr(error, "errors")
        assert len(error.errors) >= 2
