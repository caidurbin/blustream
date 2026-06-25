"""Tests for DMP168 device."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from blustream.base.connection import Connection
from blustream.base.exceptions import CommandError, ConnectionError, ValidationError
from blustream.devices.dmp168.commands import (
    build_help_command,
    build_output_volume_command,
    build_power_on_command,
    build_status_command,
)
from blustream.devices.dmp168.device import DMP168, _help_terminator
from blustream.devices.dmp168.models import (
    OutputRouting,
    OutputSource,
    SystemStatus,
)


def _status_with_routing(*routing: OutputRouting) -> SystemStatus:
    return SystemStatus(
        power="On",
        baud=57600,
        level_unit="%",
        auto_standby_time=0,
        dsp_usage=10.0,
        fade=False,
        temperature=25.0,
        uptime="0000:01:00:00",
        firmware_version="1.2.3",
        inputs=[],
        routing=list(routing),
    )


class TestSetOutputSource:
    """High-level set_output_source maps to route / output_remove wire ops."""

    @pytest.mark.asyncio
    async def test_route_input_source(self):
        device = DMP168(host="192.0.2.100")
        device.execute_command = AsyncMock()

        await device.set_output_source(1, OutputSource.for_input(5))

        device.execute_command.assert_awaited_once_with("route", output=1, input=5)

    @pytest.mark.asyncio
    async def test_route_bus_source_uses_unified_column(self):
        device = DMP168(host="192.0.2.100")
        device.execute_command = AsyncMock()

        # Bus 3 addresses unified column 19 (16 + 3) on the wire.
        await device.set_output_source(2, OutputSource.for_bus(3))

        device.execute_command.assert_awaited_once_with("route", output=2, input=19)

    @pytest.mark.asyncio
    async def test_clear_removes_current_source(self):
        device = DMP168(host="192.0.2.100")
        device.get_status = AsyncMock(
            return_value=_status_with_routing(
                OutputRouting(output=1, channel="L", source=OutputSource.for_input(7)),
                OutputRouting(output=1, channel="R", source=OutputSource.for_input(7)),
            )
        )
        device.execute_command = AsyncMock()

        await device.set_output_source(1, None)

        device.execute_command.assert_awaited_once_with(
            "output_remove", output=1, input=7
        )

    @pytest.mark.asyncio
    async def test_clear_bus_source_uses_unified_column(self):
        device = DMP168(host="192.0.2.100")
        device.get_status = AsyncMock(
            return_value=_status_with_routing(
                OutputRouting(output=4, channel="L", source=OutputSource.for_bus(2)),
            )
        )
        device.execute_command = AsyncMock()

        await device.set_output_source(4, None)

        device.execute_command.assert_awaited_once_with(
            "output_remove", output=4, input=18
        )

    @pytest.mark.asyncio
    async def test_clear_already_unrouted_is_noop(self):
        device = DMP168(host="192.0.2.100")
        device.get_status = AsyncMock(
            return_value=_status_with_routing(
                OutputRouting(output=1, channel="L", source=None),
            )
        )
        device.execute_command = AsyncMock()

        await device.set_output_source(1, None)

        device.execute_command.assert_not_awaited()


class TestDMP168Commands:
    """Tests for DMP168 command builders."""

    def test_build_status_command(self):
        """Test STATUS command builder."""
        assert build_status_command() == "STATUS"

    def test_build_help_command(self):
        """Test HELP command builder."""
        assert build_help_command() == "HELP"

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
        assert (
            "L" not in cmd.split() or "R" not in cmd.split()
        )  # Should not have separate L/R

    def test_build_route_command_boundary_values(self):
        """Test route command with boundary values."""
        from blustream.devices.dmp168.commands import build_route_command

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
        from blustream.devices.dmp168.commands import build_route_command

        with pytest.raises(ValidationError):
            build_route_command(output=1, input_ch=0)  # Input must be 1-24

        with pytest.raises(ValidationError):
            build_route_command(output=1, input_ch=25)  # Input must be 1-24

    def test_build_preset_command_boundary_values(self):
        """Test preset commands with boundary values."""
        from blustream.devices.dmp168.commands import (
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
        from blustream.devices.dmp168.commands import build_preset_save_command

        with pytest.raises(ValidationError):
            build_preset_save_command(preset=0)  # Preset must be 1-8

        with pytest.raises(ValidationError):
            build_preset_save_command(preset=9)  # Preset must be 1-8

    def test_build_input_gain_command_boundary_values(self):
        """Test input gain command with boundary values."""
        from blustream.devices.dmp168.commands import build_input_gain_command

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
        from blustream.devices.dmp168.commands import build_input_gain_command

        cmd = build_input_gain_command(input_ch=1, gain="+")
        assert "IN 1" in cmd
        assert "GAIN" in cmd
        assert "+" in cmd

        cmd = build_input_gain_command(input_ch=1, gain="-")
        assert "-" in cmd

    def test_build_input_gain_command_invalid_input(self):
        """Test input gain command with invalid input."""
        from blustream.devices.dmp168.commands import build_input_gain_command

        with pytest.raises(ValidationError):
            build_input_gain_command(input_ch=-1, gain=50)  # Input must be 0-16

        with pytest.raises(ValidationError):
            build_input_gain_command(input_ch=17, gain=50)  # Input must be 0-16

    def test_build_output_delay_command_boundary_values(self):
        """Test output delay command with boundary values."""
        from blustream.devices.dmp168.commands import build_output_delay_command

        # Test minimum delay (0)
        cmd = build_output_delay_command(output=1, delay_ms=0)
        assert "OUT 1" in cmd
        assert "DELAY 0" in cmd

        # Test maximum delay (500)
        cmd = build_output_delay_command(output=1, delay_ms=500)
        assert "DELAY 500" in cmd

    def test_build_output_delay_command_invalid_delay(self):
        """Test output delay command with invalid delay."""
        from blustream.devices.dmp168.commands import build_output_delay_command

        with pytest.raises(ValidationError):
            build_output_delay_command(output=1, delay_ms=-1)  # Delay must be 0-500

        with pytest.raises(ValidationError):
            build_output_delay_command(output=1, delay_ms=501)  # Delay must be 0-500

    def test_build_output_mix_command_boundary_values(self):
        """Test output mix command with boundary values."""
        from blustream.devices.dmp168.commands import build_output_mix_command

        # Test minimum mode (0)
        cmd = build_output_mix_command(output=1, mode=0)
        assert "OUT 1" in cmd
        assert "MIX 0" in cmd

        # Test maximum mode (6)
        cmd = build_output_mix_command(output=1, mode=6)
        assert "MIX 6" in cmd

    def test_build_output_mix_command_invalid_mode(self):
        """Test output mix command with invalid mode."""
        from blustream.devices.dmp168.commands import build_output_mix_command

        with pytest.raises(ValidationError):
            build_output_mix_command(output=1, mode=-1)  # Mode must be 0-6

        with pytest.raises(ValidationError):
            build_output_mix_command(output=1, mode=7)  # Mode must be 0-6

    def test_build_group_volume_command_boundary_values(self):
        """Test group volume command with boundary values."""
        from blustream.devices.dmp168.commands import build_group_volume_command

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
        from blustream.devices.dmp168.commands import build_group_volume_command

        with pytest.raises(ValidationError):
            build_group_volume_command(group=-1, level=50)  # Group must be 0-4

        with pytest.raises(ValidationError):
            build_group_volume_command(group=5, level=50)  # Group must be 0-4

    def test_build_standby_command_boundary_values(self):
        """Test standby command with boundary values."""
        from blustream.devices.dmp168.commands import build_standby_command

        # Test mode 0 (Sleep)
        cmd = build_standby_command(mode=0)
        assert "STANDBY 0" in cmd

        # Test mode 1 (Standby)
        cmd = build_standby_command(mode=1)
        assert "STANDBY 1" in cmd

    def test_build_standby_command_invalid_mode(self):
        """Test standby command with invalid mode."""
        from blustream.devices.dmp168.commands import build_standby_command

        with pytest.raises(ValidationError):
            build_standby_command(mode=-1)  # Mode must be 0 or 1

        with pytest.raises(ValidationError):
            build_standby_command(mode=2)  # Mode must be 0 or 1


class TestDMP168Device:
    """Tests for DMP168 device class."""

    @patch("blustream.devices.dmp168.device.TCPConnection")
    def test_get_commands(self, mock_connection_class):
        """Test getting available commands."""
        mock_conn = MagicMock()
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        commands = device.get_commands()

        assert "status" in commands
        assert "power_on" in commands
        assert "output_volume" in commands
        assert "help" in commands

    def test_help_terminator_frames_on_footer_after_header(self):
        """HELP has no [SUCCESS] marker; the predicate fires on the =-only
        footer, and only after the help header arms it — so a welcome-banner
        =-only sentinel arriving first can't end the read early."""
        predicate = _help_terminator()
        footer = "=" * 64 + "\r\n"
        # Banner sentinel before the header must NOT fire (not yet armed).
        assert predicate(footer) is False
        # Header arms the predicate.
        assert predicate("?/HELP                 Print Help Information\r\n") is False
        # Section headers carry text -> not =-only -> never fire.
        assert predicate("======================= System Control Command\r\n") is False
        # The closing =-only footer fires.
        assert predicate(footer) is True

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_help_sends_help_and_returns_listing(
        self, mock_connection_class
    ):
        """execute_command('help') sends HELP and returns the raw listing."""
        listing = (
            "DMP168 Help Info\r\n"
            "======================= System Control Command\r\n"
            "REBOOT                 Set System Reboot\r\n"
            "================================================================\r\n"
        )
        mock_conn = MagicMock()
        mock_conn.send = AsyncMock()
        mock_conn.read_until = AsyncMock(return_value=listing)
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.connect = AsyncMock()
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        await device.connect()
        result = await device.execute_command("help")

        mock_conn.send.assert_awaited_once_with(b"HELP\r\n")
        assert "REBOOT                 Set System Reboot" in result
        # Raw listing returned verbatim, only the outer CRLF stripped.
        assert result.startswith("DMP168 Help Info")
        assert not result.endswith("\r\n")

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_get_help_delegates_to_execute_command(self, mock_connection_class):
        """The high-level get_help() wrapper delegates to execute_command('help')."""
        mock_connection_class.return_value = MagicMock()
        device = DMP168(host="192.0.2.100")
        device.execute_command = AsyncMock(return_value="DMP168 Help Info ...")

        result = await device.get_help()

        device.execute_command.assert_awaited_once_with("help")
        assert result == "DMP168 Help Info ..."

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_unknown(self, mock_connection_class):
        """Test executing unknown command."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        await device.connect()

        with pytest.raises(CommandError):
            await device.execute_command("unknown_command")

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_high_level_api(self, mock_connection_class):
        """Test high-level API methods."""
        mock_conn = MagicMock()
        mock_connection_class.return_value = mock_conn
        mock_conn.send = AsyncMock()
        mock_conn.read_until = AsyncMock(return_value="[SUCCESS]ok\r\n")
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.connect = AsyncMock()

        device = DMP168(host="192.0.2.100")
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
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_missing_parameter(self, mock_connection_class):
        """Test executing command with missing required parameter."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        await device.connect()

        with pytest.raises(ValidationError):
            await device.execute_command(
                "output_volume"
            )  # Missing 'output' and 'level'

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_invalid_parameter_value(self, mock_connection_class):
        """Test executing command with invalid parameter value."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        await device.connect()

        with pytest.raises(ValidationError):
            await device.execute_command(
                "output_volume", output=10, level=75
            )  # output=10 is invalid

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_not_connected(self, mock_connection_class):
        """Test executing command when not connected."""
        mock_conn = MagicMock()
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        # Don't connect

        from blustream.base.exceptions import ConnectionError

        with pytest.raises(ConnectionError):
            await device.execute_command("status")

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_connection_error(self, mock_connection_class):
        """Test executing command when connection error occurs."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock(side_effect=ConnectionError("Connection lost"))
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        await device.connect()

        with pytest.raises(CommandError):
            await device.execute_command("status")

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_uptime_success_pattern(self, mock_connection_class):
        """Test executing uptime command with [SUCCESS] pattern."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        mock_conn.read_until = AsyncMock(
            return_value="[SUCCESS]The uptime of the system is 0000:08:57:01\r\nDMP168>"
        )
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        await device.connect()

        result = await device.execute_command("uptime")
        assert result == "0000:08:57:01"

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_temp_success_pattern(self, mock_connection_class):
        """Test executing temp command with [SUCCESS] pattern."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        mock_conn.read_until = AsyncMock(
            return_value="[SUCCESS]The temperature of the system is 47.4C\r\nDMP168>"
        )
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        await device.connect()

        result = await device.execute_command("temp")
        assert result == "47.4C"

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_uptime_direct_pattern(self, mock_connection_class):
        """Test executing uptime command with direct value pattern."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        mock_conn.read_until = AsyncMock(return_value="0000:08:57:01\r\nDMP168>")
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        await device.connect()

        result = await device.execute_command("uptime")
        assert result == "0000:08:57:01"

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_temp_direct_pattern(self, mock_connection_class):
        """Test executing temp command with direct value pattern."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        mock_conn.read_until = AsyncMock(return_value="47.4C\r\nDMP168>")
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        await device.connect()

        result = await device.execute_command("temp")
        assert result == "47.4C"

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_command_requires_confirmation(self, mock_connection_class):
        """Test checking if command requires confirmation."""
        mock_conn = MagicMock()
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        assert device.command_requires_confirmation("preset_delete") is True
        assert device.command_requires_confirmation("reboot") is True
        assert device.command_requires_confirmation("output_remove") is True
        assert device.command_requires_confirmation("status") is False
        assert device.command_requires_confirmation("unknown_command") is False

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_confirmation_message_static_string(self, mock_connection_class):
        """Test that reboot has a static string confirmation_message."""
        mock_conn = MagicMock()
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        command = device.get_command("reboot")
        assert command is not None
        assert isinstance(command.confirmation_message, str)
        assert "reboot" in command.confirmation_message.lower()

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_confirmation_message_callable(self, mock_connection_class):
        """Test that preset_delete has a callable confirmation_message with kwarg substitution."""
        mock_conn = MagicMock()
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        command = device.get_command("preset_delete")
        assert command is not None
        assert callable(command.confirmation_message)
        msg = command.confirmation_message({"preset": 3})
        assert "3" in msg
        assert "preset" in msg.lower()

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_confirmation_message_callable_output_remove(
        self, mock_connection_class
    ):
        """Test that output_remove has a callable confirmation_message with kwarg substitution."""
        mock_conn = MagicMock()
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        command = device.get_command("output_remove")
        assert command is not None
        assert callable(command.confirmation_message)
        msg = command.confirmation_message({"output": 2, "input": 5})
        assert "2" in msg
        assert "5" in msg

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_confirmation_message_unset_is_none(self, mock_connection_class):
        """Test that non-destructive commands have no confirmation_message."""
        mock_conn = MagicMock()
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        command = device.get_command("status")
        assert command is not None
        assert command.confirmation_message is None

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_get_command_unknown(self, mock_connection_class):
        """Test get_command returns None for unknown commands."""
        mock_conn = MagicMock()
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        assert device.get_command("nonexistent") is None

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_context_manager(self, mock_connection_class):
        """Test device as async context manager."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.disconnect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_connection_class.return_value = mock_conn

        async with DMP168(host="192.0.2.100") as device:
            assert device.is_connected
            mock_conn.connect.assert_called_once()

        mock_conn.disconnect.assert_called_once()

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_parse_error(self, mock_connection_class):
        """Test executing command that causes parse error."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        # Return invalid STATUS response
        mock_conn.read_until = AsyncMock(
            return_value="Invalid STATUS response\r\nDMP168>"
        )
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        await device.connect()

        from blustream.base.exceptions import ParseError

        with pytest.raises(ParseError):
            await device.execute_command("status")

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_timeout(self, mock_connection_class):
        """Test executing command that times out."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        from blustream.base.exceptions import TimeoutError

        mock_conn.read_until = AsyncMock(side_effect=TimeoutError("Timeout"))
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        await device.connect()

        with pytest.raises(CommandError):
            await device.execute_command("status")

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_uptime_fallback(self, mock_connection_class):
        """Test executing uptime command with fallback parsing."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        # Response without [SUCCESS] pattern, but with uptime format
        mock_conn.read_until = AsyncMock(
            return_value="Some text 0000:12:34:56 more text\r\nDMP168>"
        )
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        await device.connect()

        result = await device.execute_command("uptime")
        assert result == "0000:12:34:56"

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_temp_fallback(self, mock_connection_class):
        """Test executing temp command with fallback parsing."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        # Response without [SUCCESS] pattern, but with temp format
        mock_conn.read_until = AsyncMock(
            return_value="Temperature is 42.5C degrees\r\nDMP168>"
        )
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        await device.connect()

        result = await device.execute_command("temp")
        assert result == "42.5C"

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_uptime_stripped_response(
        self, mock_connection_class
    ):
        """Test executing uptime command with only stripped response fallback."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        # Response that doesn't match any pattern
        mock_conn.read_until = AsyncMock(return_value="  0000:12:34:56  \r\nDMP168>")
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        await device.connect()

        result = await device.execute_command("uptime")
        # Should extract the uptime pattern even from stripped response
        assert "0000:12:34:56" in result

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_execute_command_handler_error(self, mock_connection_class):
        """Test executing command when handler raises error."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        await device.connect()

        # This should fail during parameter validation, not execution
        with pytest.raises(ValidationError):
            # Pass invalid parameter type that causes validation to fail
            await device.execute_command("output_volume", output="invalid", level=75)

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_set_output_volume_relative(self, mock_connection_class):
        """Test setting output volume with relative level."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        mock_conn.read_until = AsyncMock(return_value="[SUCCESS]ok\r\n")
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        await device.connect()

        # Test relative volume increase
        await device.set_output_volume(1, "+")
        # Test relative volume decrease
        await device.set_output_volume(1, "-")

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_set_input_gain_relative(self, mock_connection_class):
        """Test setting input gain with relative level."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        mock_conn.read_until = AsyncMock(return_value="[SUCCESS]ok\r\n")
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        await device.connect()

        # Test relative gain increase (unit=None is now handled correctly by validation)
        await device.set_input_gain(1, "+")
        # Test relative gain decrease
        await device.set_input_gain(1, "-")

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_get_uptime_raw_returns_raw_string(self, mock_connection_class):
        """get_uptime_raw() preserves the old get_uptime() string behavior."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        mock_conn.read_until = AsyncMock(
            return_value="[SUCCESS]The uptime of the system is 0000:08:57:01\r\nDMP168>"
        )
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        await device.connect()

        raw = await device.get_uptime_raw()
        assert raw == "0000:08:57:01"

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_get_uptime_returns_timedelta(self, mock_connection_class):
        """get_uptime() now returns a parsed timedelta, not the raw string."""
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.send = AsyncMock()
        mock_conn.read_until = AsyncMock(
            return_value="[SUCCESS]The uptime of the system is 0000:08:57:01\r\nDMP168>"
        )
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        await device.connect()

        uptime = await device.get_uptime()
        assert uptime == timedelta(hours=8, minutes=57, seconds=1)

    @pytest.mark.asyncio
    @patch("blustream.devices.dmp168.device.TCPConnection")
    async def test_get_uptime_propagates_parse_error(self, mock_connection_class):
        """get_uptime() surfaces ParseError when the raw reply isn't a duration."""
        mock_conn = MagicMock()
        mock_connection_class.return_value = mock_conn

        device = DMP168(host="192.0.2.100")
        device.get_uptime_raw = AsyncMock(return_value="garbage-not-uptime")

        from blustream.base.exceptions import ParseError

        with pytest.raises(ParseError):
            await device.get_uptime()


_STATUS_FIXTURE = Path(__file__).resolve().parent / "fixtures/status_live_full.txt"


class _SingleReaderConnection(Connection):
    """A connection that mimics the one shared telnetlib3 reader.

    The integration shares a single ``TCPConnection`` — and therefore a single
    ``telnetlib3`` reader — between the coordinator's status poll and every
    service call. That reader carries its own single-waiter guard (telnetlib3
    reimplements asyncio's ``_wait_for_data`` rather than subclassing
    ``asyncio.StreamReader``): awaiting ``read()`` from two coroutines at once
    raises ``RuntimeError("read() called while another coroutine is already
    waiting for incoming data")``.

    This stand-in reproduces that exact guard: a second ``read_until`` entered
    while one is still in flight raises the same error. It also returns ``str``,
    as telnetlib3's reader does with an encoding set (the default). Replies are
    handed out one per ``read_until`` from a queue the test feeds, so the
    in-flight window is controlled with no sleeps.
    """

    def __init__(self) -> None:
        self._connected = True
        self._reading = False
        self.read_in_flight = asyncio.Event()
        self.sent: list[bytes] = []
        self._responses: asyncio.Queue[str] = asyncio.Queue()

    def feed_response(self, text: str) -> None:
        """Queue the full reply the next ``read_until`` will return."""
        self._responses.put_nowait(text)

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    async def send(self, data: bytes) -> None:
        if not self._connected:
            raise ConnectionError("Not connected")
        self.sent.append(data)

    async def read_until(self, predicate: Callable[[str], bool], timeout: float) -> str:
        if self._reading:
            raise RuntimeError(
                "read() called while another coroutine is already "
                "waiting for incoming data"
            )
        self._reading = True
        self.read_in_flight.set()
        try:
            return await self._responses.get()
        finally:
            self._reading = False


class TestConcurrentTransactionsSerialize:
    """A shared connection must serialise overlapping request/response cycles.

    Regression for the HA report: ``media_player.volume_mute`` fired while the
    coordinator's 30s status poll was mid-read raised ``CommandError: An
    unexpected error occurred during command execution: read() called while
    another coroutine is already waiting for incoming data``.
    """

    @pytest.mark.asyncio
    async def test_harness_reproduces_single_waiter_guard(self) -> None:
        """Sanity: the fake reproduces the concurrent-read guard.

        Without this, the serialisation test below could pass vacuously — a
        fake that never rejects overlap would prove nothing.
        """
        conn = _SingleReaderConnection()
        first = asyncio.create_task(conn.read_until(lambda _line: True, timeout=5))
        await conn.read_in_flight.wait()

        with pytest.raises(RuntimeError, match="already waiting for incoming data"):
            await conn.read_until(lambda _line: True, timeout=5)

        conn.feed_response("[SUCCESS]\r\n")
        await first

    @pytest.mark.asyncio
    async def test_status_poll_and_mute_do_not_collide(self) -> None:
        """A mute fired mid-poll waits its turn instead of racing the reader."""
        conn = _SingleReaderConnection()
        device = DMP168(host="192.0.2.100", connection=conn)
        device._connected = True

        status_text = _STATUS_FIXTURE.read_bytes().decode("utf-8")

        # The coordinator's poll, left parked mid-read.
        poll = asyncio.create_task(device.get_status())
        await conn.read_in_flight.wait()

        # The user mute, fired while the poll holds the reader (the reported
        # scenario). It must queue behind the poll, not enter the reader.
        mute = asyncio.create_task(device.set_output_mute(1, True))
        await asyncio.sleep(0)

        # Release the poll, then the mute — order is deterministic because the
        # mute is serialised behind the poll.
        conn.feed_response(status_text)
        status = await poll

        conn.feed_response("[SUCCESS]\r\n")
        await mute  # pre-fix: raises the wrapped single-waiter CommandError

        assert isinstance(status, SystemStatus)
        # Both transactions reached the wire, in order: STATUS then the mute.
        assert len(conn.sent) == 2
        assert conn.sent[0].startswith(b"STATUS")
