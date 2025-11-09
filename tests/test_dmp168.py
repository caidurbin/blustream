"""Tests for DMP168 device."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bluestream.base.exceptions import CommandError, ConnectionError, ValidationError
from bluestream.devices.dmp168.commands import (
    build_output_volume_command,
    build_power_on_command,
    build_status_command,
)
from bluestream.devices.dmp168.device import DMP168


class TestDMP168Commands:
    """Tests for DMP168 command builders."""

    def test_build_status_command(self):
        """Test STATUS command builder."""
        assert build_status_command() == "STATUS"

    def test_build_power_on_command(self):
        """Test PON command builder."""
        assert build_power_on_command() == "PON"

    def test_build_output_volume_command(self):
        """Test output volume command builder."""
        cmd = build_output_volume_command(output=1, level=75, unit="percent")
        assert "OUT 1" in cmd
        assert "VOL" in cmd
        assert "75" in cmd

    def test_build_output_volume_command_db(self):
        """Test output volume command builder with dB."""
        cmd = build_output_volume_command(output=1, level=-10, unit="dB")
        assert "OUT 1" in cmd
        assert "VOL" in cmd
        assert "-10" in cmd
        assert "dB" in cmd

    def test_build_output_volume_command_invalid_output(self):
        """Test output volume command with invalid output."""
        with pytest.raises(ValidationError):
            build_output_volume_command(output=10, level=75)

    def test_build_output_volume_command_invalid_channel(self):
        """Test output volume command with invalid channel."""
        with pytest.raises(ValidationError):
            build_output_volume_command(output=1, level=75, channel="X")

    def test_build_output_volume_command_boundary_values(self):
        """Test output volume command with boundary values."""
        # Test minimum output (0 = All)
        cmd = build_output_volume_command(output=0, level=0, unit="percent")
        assert "OUT 0" in cmd
        assert "VOL" in cmd
        assert "0" in cmd

        # Test maximum output (8)
        cmd = build_output_volume_command(output=8, level=100, unit="percent")
        assert "OUT 8" in cmd
        assert "VOL" in cmd
        assert "100" in cmd

    def test_build_output_volume_command_relative(self):
        """Test output volume command with relative level."""
        cmd = build_output_volume_command(output=1, level="+", unit="percent")
        assert "OUT 1" in cmd
        assert "VOL" in cmd
        assert "+" in cmd

        cmd = build_output_volume_command(output=1, level="-", unit="percent")
        assert "-" in cmd

    def test_build_output_volume_command_db_boundary(self):
        """Test output volume command with dB boundary values."""
        # Test minimum dB (-76)
        cmd = build_output_volume_command(output=1, level=-76, unit="dB")
        assert "-76" in cmd
        assert "dB" in cmd

        # Test maximum dB (+24)
        cmd = build_output_volume_command(output=1, level=24, unit="dB")
        assert "24" in cmd
        assert "dB" in cmd

    def test_build_output_volume_command_channel_combinations(self):
        """Test output volume command with different channel combinations."""
        # Test L channel
        cmd = build_output_volume_command(output=1, level=50, channel="L")
        assert "OUT 1 L" in cmd
        assert "VOL L" in cmd

        # Test R channel
        cmd = build_output_volume_command(output=1, level=50, channel="R")
        assert "OUT 1 R" in cmd
        assert "VOL R" in cmd

        # Test LR channel (default)
        cmd = build_output_volume_command(output=1, level=50, channel="LR")
        assert "OUT 1" in cmd
        assert "VOL" in cmd
        assert "L" not in cmd.split() or "R" not in cmd.split()  # Should not have separate L/R

    def test_build_route_command_boundary_values(self):
        """Test route command with boundary values."""
        from bluestream.devices.dmp168.commands import build_route_command

        # Test minimum input (1)
        cmd = build_route_command(output=1, input_ch=1)
        assert "OUT 1" in cmd
        assert "FR 1" in cmd

        # Test maximum input (24)
        cmd = build_route_command(output=8, input_ch=24)
        assert "OUT 8" in cmd
        assert "FR 24" in cmd

    def test_build_route_command_invalid_input(self):
        """Test route command with invalid input."""
        from bluestream.devices.dmp168.commands import build_route_command

        with pytest.raises(ValidationError):
            build_route_command(output=1, input_ch=0)  # Input must be 1-24

        with pytest.raises(ValidationError):
            build_route_command(output=1, input_ch=25)  # Input must be 1-24

    def test_build_preset_command_boundary_values(self):
        """Test preset commands with boundary values."""
        from bluestream.devices.dmp168.commands import (
            build_preset_delete_command,
            build_preset_recall_command,
            build_preset_save_command,
        )

        # Test minimum preset (1)
        cmd = build_preset_save_command(preset=1)
        assert "PRESET 1" in cmd

        # Test maximum preset (8)
        cmd = build_preset_recall_command(preset=8)
        assert "PRESET 8" in cmd

        cmd = build_preset_delete_command(preset=8)
        assert "PRESET 8" in cmd

    def test_build_preset_command_invalid_preset(self):
        """Test preset commands with invalid preset number."""
        from bluestream.devices.dmp168.commands import build_preset_save_command

        with pytest.raises(ValidationError):
            build_preset_save_command(preset=0)  # Preset must be 1-8

        with pytest.raises(ValidationError):
            build_preset_save_command(preset=9)  # Preset must be 1-8

    def test_build_input_gain_command_boundary_values(self):
        """Test input gain command with boundary values."""
        from bluestream.devices.dmp168.commands import build_input_gain_command

        # Test minimum input (0 = All)
        cmd = build_input_gain_command(input_ch=0, gain=0)
        assert "IN 0" in cmd
        assert "GAIN" in cmd

        # Test maximum input (16)
        cmd = build_input_gain_command(input_ch=16, gain=100)
        assert "IN 16" in cmd
        assert "GAIN" in cmd
        assert "100" in cmd

    def test_build_input_gain_command_relative(self):
        """Test input gain command with relative level."""
        from bluestream.devices.dmp168.commands import build_input_gain_command

        cmd = build_input_gain_command(input_ch=1, gain="+")
        assert "IN 1" in cmd
        assert "GAIN" in cmd
        assert "+" in cmd

        cmd = build_input_gain_command(input_ch=1, gain="-")
        assert "-" in cmd

    def test_build_input_gain_command_invalid_input(self):
        """Test input gain command with invalid input."""
        from bluestream.devices.dmp168.commands import build_input_gain_command

        with pytest.raises(ValidationError):
            build_input_gain_command(input_ch=-1, gain=50)  # Input must be 0-16

        with pytest.raises(ValidationError):
            build_input_gain_command(input_ch=17, gain=50)  # Input must be 0-16

    def test_build_output_delay_command_boundary_values(self):
        """Test output delay command with boundary values."""
        from bluestream.devices.dmp168.commands import build_output_delay_command

        # Test minimum delay (0)
        cmd = build_output_delay_command(output=1, delay_ms=0)
        assert "OUT 1" in cmd
        assert "DELAY 0" in cmd

        # Test maximum delay (500)
        cmd = build_output_delay_command(output=1, delay_ms=500)
        assert "DELAY 500" in cmd

    def test_build_output_delay_command_invalid_delay(self):
        """Test output delay command with invalid delay."""
        from bluestream.devices.dmp168.commands import build_output_delay_command

        with pytest.raises(ValidationError):
            build_output_delay_command(output=1, delay_ms=-1)  # Delay must be 0-500

        with pytest.raises(ValidationError):
            build_output_delay_command(output=1, delay_ms=501)  # Delay must be 0-500

    def test_build_output_mix_command_boundary_values(self):
        """Test output mix command with boundary values."""
        from bluestream.devices.dmp168.commands import build_output_mix_command

        # Test minimum mode (0)
        cmd = build_output_mix_command(output=1, mode=0)
        assert "OUT 1" in cmd
        assert "MIX 0" in cmd

        # Test maximum mode (6)
        cmd = build_output_mix_command(output=1, mode=6)
        assert "MIX 6" in cmd

    def test_build_output_mix_command_invalid_mode(self):
        """Test output mix command with invalid mode."""
        from bluestream.devices.dmp168.commands import build_output_mix_command

        with pytest.raises(ValidationError):
            build_output_mix_command(output=1, mode=-1)  # Mode must be 0-6

        with pytest.raises(ValidationError):
            build_output_mix_command(output=1, mode=7)  # Mode must be 0-6

    def test_build_group_volume_command_boundary_values(self):
        """Test group volume command with boundary values."""
        from bluestream.devices.dmp168.commands import build_group_volume_command

        # Test minimum group (0 = All)
        cmd = build_group_volume_command(group=0, level=0, unit="percent")
        assert "GROUP 0" in cmd
        assert "VOL" in cmd

        # Test maximum group (4)
        cmd = build_group_volume_command(group=4, level=100, unit="percent")
        assert "GROUP 4" in cmd
        assert "100" in cmd

    def test_build_group_volume_command_invalid_group(self):
        """Test group volume command with invalid group."""
        from bluestream.devices.dmp168.commands import build_group_volume_command

        with pytest.raises(ValidationError):
            build_group_volume_command(group=-1, level=50)  # Group must be 0-4

        with pytest.raises(ValidationError):
            build_group_volume_command(group=5, level=50)  # Group must be 0-4

    def test_build_standby_command_boundary_values(self):
        """Test standby command with boundary values."""
        from bluestream.devices.dmp168.commands import build_standby_command

        # Test mode 0 (Sleep)
        cmd = build_standby_command(mode=0)
        assert "STANDBY 0" in cmd

        # Test mode 1 (Standby)
        cmd = build_standby_command(mode=1)
        assert "STANDBY 1" in cmd

    def test_build_standby_command_invalid_mode(self):
        """Test standby command with invalid mode."""
        from bluestream.devices.dmp168.commands import build_standby_command

        with pytest.raises(ValidationError):
            build_standby_command(mode=-1)  # Mode must be 0 or 1

        with pytest.raises(ValidationError):
            build_standby_command(mode=2)  # Mode must be 0 or 1


class TestDMP168Device:
    """Tests for DMP168 device class."""

    @patch("bluestream.devices.dmp168.device.TCPConnection")
    def test_get_commands(self, mock_connection_class):
        """Test getting available commands."""
        mock_conn = MagicMock()
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        commands = device.get_commands()

        assert "status" in commands
        assert "power_on" in commands
        assert "output_volume" in commands

    @pytest.mark.asyncio
    @patch("bluestream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_unknown(self, mock_connection_class):
        """Test executing unknown command."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        await device.connect()

        with pytest.raises(CommandError):
            await device.execute_command("unknown_command")

    @pytest.mark.asyncio
    @patch("bluestream.devices.dmp168.device.TCPConnection")
    async def test_high_level_api(self, mock_connection_class):
        """Test high-level API methods."""
        mock_conn = MagicMock()
        mock_connection_class.return_value = mock_conn
        mock_conn.send = AsyncMock()
        mock_conn.receive = AsyncMock(return_value=b"OK\r\nDMP168>")
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.connect = AsyncMock()

        device = DMP168(host="192.168.1.100")
        await device.connect()

        # Test power methods
        await device.power_on()
        await device.power_off()

        # Test volume
        await device.set_output_volume(1, 75)

        # Test mute
        await device.set_output_mute(1, True)

        # Test routing
        await device.route_input_to_output(input_ch=2, output=1)

    @pytest.mark.asyncio
    @patch("bluestream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_missing_parameter(self, mock_connection_class):
        """Test executing command with missing required parameter."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        await device.connect()

        with pytest.raises(ValidationError):
            await device.execute_command("output_volume")  # Missing 'output' and 'level'

    @pytest.mark.asyncio
    @patch("bluestream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_invalid_parameter_value(self, mock_connection_class):
        """Test executing command with invalid parameter value."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        await device.connect()

        with pytest.raises(ValidationError):
            await device.execute_command("output_volume", output=10, level=75)  # output=10 is invalid

    @pytest.mark.asyncio
    @patch("bluestream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_not_connected(self, mock_connection_class):
        """Test executing command when not connected."""
        mock_conn = MagicMock()
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        # Don't connect

        from bluestream.base.exceptions import ConnectionError

        with pytest.raises(ConnectionError):
            await device.execute_command("status")

    @pytest.mark.asyncio
    @patch("bluestream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_connection_error(self, mock_connection_class):
        """Test executing command when connection error occurs."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock(side_effect=ConnectionError("Connection lost"))
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        await device.connect()

        with pytest.raises(CommandError):
            await device.execute_command("status")

    @pytest.mark.asyncio
    @patch("bluestream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_uptime_success_pattern(self, mock_connection_class):
        """Test executing uptime command with [SUCCESS] pattern."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        mock_conn.receive = AsyncMock(return_value=b"[SUCCESS]The uptime of the system is 0000:08:57:01\r\nDMP168>")
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        await device.connect()

        result = await device.execute_command("uptime")
        assert result == "0000:08:57:01"

    @pytest.mark.asyncio
    @patch("bluestream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_temp_success_pattern(self, mock_connection_class):
        """Test executing temp command with [SUCCESS] pattern."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        mock_conn.receive = AsyncMock(return_value=b"[SUCCESS]The temperature of the system is 47.4C\r\nDMP168>")
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        await device.connect()

        result = await device.execute_command("temp")
        assert result == "47.4C"

    @pytest.mark.asyncio
    @patch("bluestream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_uptime_direct_pattern(self, mock_connection_class):
        """Test executing uptime command with direct value pattern."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        mock_conn.receive = AsyncMock(return_value=b"0000:08:57:01\r\nDMP168>")
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        await device.connect()

        result = await device.execute_command("uptime")
        assert result == "0000:08:57:01"

    @pytest.mark.asyncio
    @patch("bluestream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_temp_direct_pattern(self, mock_connection_class):
        """Test executing temp command with direct value pattern."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        mock_conn.receive = AsyncMock(return_value=b"47.4C\r\nDMP168>")
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        await device.connect()

        result = await device.execute_command("temp")
        assert result == "47.4C"

    @pytest.mark.asyncio
    @patch("bluestream.devices.dmp168.device.TCPConnection")
    async def test_command_requires_confirmation(self, mock_connection_class):
        """Test checking if command requires confirmation."""
        mock_conn = MagicMock()
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        assert device.command_requires_confirmation("preset_delete") is True
        assert device.command_requires_confirmation("reboot") is True
        assert device.command_requires_confirmation("status") is False
        assert device.command_requires_confirmation("unknown_command") is False

    @pytest.mark.asyncio
    @patch("bluestream.devices.dmp168.device.TCPConnection")
    async def test_context_manager(self, mock_connection_class):
        """Test device as async context manager."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.disconnect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_connection_class.return_value = mock_conn

        async with DMP168(host="192.168.1.100") as device:
            assert device.is_connected
            mock_conn.connect.assert_called_once()

        mock_conn.disconnect.assert_called_once()

    @pytest.mark.asyncio
    @patch("bluestream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_parse_error(self, mock_connection_class):
        """Test executing command that causes parse error."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        # Return invalid STATUS response
        mock_conn.receive = AsyncMock(return_value=b"Invalid STATUS response\r\nDMP168>")
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        await device.connect()

        from bluestream.base.exceptions import ParseError

        with pytest.raises(ParseError):
            await device.execute_command("status")

    @pytest.mark.asyncio
    @patch("bluestream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_timeout(self, mock_connection_class):
        """Test executing command that times out."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        from bluestream.base.exceptions import TimeoutError

        mock_conn.receive = AsyncMock(side_effect=TimeoutError("Timeout"))
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        await device.connect()

        with pytest.raises(CommandError):
            await device.execute_command("status")

    @pytest.mark.asyncio
    @patch("bluestream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_uptime_fallback(self, mock_connection_class):
        """Test executing uptime command with fallback parsing."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        # Response without [SUCCESS] pattern, but with uptime format
        mock_conn.receive = AsyncMock(return_value=b"Some text 0000:12:34:56 more text\r\nDMP168>")
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        await device.connect()

        result = await device.execute_command("uptime")
        assert result == "0000:12:34:56"

    @pytest.mark.asyncio
    @patch("bluestream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_temp_fallback(self, mock_connection_class):
        """Test executing temp command with fallback parsing."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        # Response without [SUCCESS] pattern, but with temp format
        mock_conn.receive = AsyncMock(return_value=b"Temperature is 42.5C degrees\r\nDMP168>")
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        await device.connect()

        result = await device.execute_command("temp")
        assert result == "42.5C"

    @pytest.mark.asyncio
    @patch("bluestream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_uptime_stripped_response(self, mock_connection_class):
        """Test executing uptime command with only stripped response fallback."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        # Response that doesn't match any pattern
        mock_conn.receive = AsyncMock(return_value=b"  0000:12:34:56  \r\nDMP168>")
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        await device.connect()

        result = await device.execute_command("uptime")
        # Should extract the uptime pattern even from stripped response
        assert "0000:12:34:56" in result

    @pytest.mark.asyncio
    @patch("bluestream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_handler_error(self, mock_connection_class):
        """Test executing command when handler raises error."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        await device.connect()

        # This should fail during parameter validation, not execution
        with pytest.raises(ValidationError):
            # Pass invalid parameter type that causes validation to fail
            await device.execute_command("output_volume", output="invalid", level=75)

    @pytest.mark.asyncio
    @patch("bluestream.devices.dmp168.device.TCPConnection")
    async def test_set_output_volume_relative(self, mock_connection_class):
        """Test setting output volume with relative level."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        mock_conn.receive = AsyncMock(return_value=b"OK\r\nDMP168>")
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        await device.connect()

        # Test relative volume increase
        await device.set_output_volume(1, "+", unit="percent")
        # Test relative volume decrease
        await device.set_output_volume(1, "-", unit="percent")

    @pytest.mark.asyncio
    @patch("bluestream.devices.dmp168.device.TCPConnection")
    async def test_set_input_gain_relative(self, mock_connection_class):
        """Test setting input gain with relative level."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        mock_conn.receive = AsyncMock(return_value=b"OK\r\nDMP168>")
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.168.1.100")
        await device.connect()

        # Test relative gain increase (unit=None is now handled correctly by validation)
        await device.set_input_gain(1, "+")
        # Test relative gain decrease
        await device.set_input_gain(1, "-")

