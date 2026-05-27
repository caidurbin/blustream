"""DMP168 device implementation."""

import logging
import re
from typing import Any, Dict, List, Optional, Union

from blustream.base.commands import Command, CommandRegistry
from blustream.base.connection import Connection
from blustream.base.device import BlustreamDevice
from blustream.base.exceptions import CommandError, ValidationError
from blustream.base.validator import validate
from blustream.connection.tcp import TCPConnection
from blustream.devices.dmp168 import commands as cmd_module
from blustream.devices.dmp168.commands import _is_relative_adjustment
from blustream.devices.dmp168.models import PresetStatus, SystemStatus
from blustream.devices.dmp168.parser import DMP168Parser

logger = logging.getLogger(__name__)


class DMP168(BlustreamDevice):
    """DMP168 digital audio matrix processor device."""

    commands: CommandRegistry = CommandRegistry()

    def __init__(
        self,
        host: str,
        port: int = 23,
        connection: Optional[Connection] = None,
        timeout: float = 5.0,
        command_log_path: Optional[str] = None,
    ):
        """Initialize DMP168 device.

        Args:
            host: Device hostname or IP address
            port: TCP port (default 23)
            connection: Optional connection instance (creates TCPConnection if not provided)
            timeout: Connection timeout in seconds
            command_log_path: Optional path to a text file for timestamped
                command logging (see BlustreamDevice).
        """
        if connection is None:
            connection = TCPConnection(host=host, port=port, timeout=timeout)
        super().__init__(connection, command_log_path=command_log_path)
        self.host = host
        self.port = port
        self._parser = DMP168Parser()
        self._registry = self.__class__.commands

    def get_commands(self) -> List[str]:
        """Get list of available command names.

        Returns:
            List of command names
        """
        return self._registry.list_commands()

    def get_command(self, name: str) -> Optional[Command]:
        """Get command metadata by name.

        Args:
            name: Command name

        Returns:
            Command metadata or None if not found
        """
        return self._registry.get(name)

    def command_requires_confirmation(self, name: str) -> bool:
        """Check if a command requires confirmation before execution.

        Args:
            name: Command name

        Returns:
            True if command requires confirmation, False otherwise
        """
        command = self._registry.get(name)
        if not command:
            return False
        return command.requires_confirmation

    async def execute_command(self, name: str, **kwargs: Any) -> Any:
        """Execute a command by name.

        Args:
            name: Command name
            **kwargs: Command parameters

        Returns:
            Command result (type depends on command)

        Raises:
            CommandError: If command execution fails
            ValidationError: If parameters are invalid
        """
        validate(self._registry, name, kwargs)
        command = self._registry.get(name)

        # Build command string
        try:
            cmd_str = command.handler(**kwargs)
        except ValidationError:
            # Re-raise ValidationError as-is
            raise
        except (TypeError, ValueError, AttributeError) as e:
            raise CommandError(
                f"Unable to build command '{name}': {str(e)}. Please check the command parameters and try again."
            ) from e
        except Exception as e:
            raise CommandError(
                f"An unexpected error occurred while building command '{name}': {str(e)}. Please try again."
            ) from e

        # Send command and get response
        response = await self.send_command(cmd_str)

        # Parse response based on command type
        if name == "status":
            return self._parser.parse_status(response)
        elif name == "preset_status":
            # Pass preset number to parser if available
            preset_number = kwargs.get("preset")
            return self._parser.parse_preset_status(response, preset_number=preset_number)
        elif name in ["uptime", "temp"]:
            # Extract value from uptime/temp command responses
            # Common formats:
            # - "[SUCCESS]The temperature of the system is 47.4C"
            # - "[SUCCESS]The uptime of the system is 0000:08:57:01"
            # - "47.4C" or "0000:08:57:01" (direct value)

            # Try [SUCCESS] pattern first
            success_match = re.search(r"\[SUCCESS\].*?is\s+([^\s]+)", response, re.IGNORECASE)
            if success_match:
                return success_match.group(1).strip().rstrip(".,;: \r\n")

            # Try direct value patterns
            if name == "uptime":
                # Uptime format: DDDD:HH:MM:SS (4 colon-separated parts)
                uptime_match = re.search(r"(\d{4}:\d{2}:\d{2}:\d{2})", response)
                if uptime_match:
                    return uptime_match.group(1)
            elif name == "temp":
                # Temperature format: number followed by C
                temp_match = re.search(r"([\d.]+)\s*C", response, re.IGNORECASE)
                if temp_match:
                    return temp_match.group(1) + "C"

            # Fallback to simple response parser
            cleaned = self._parser.parse_simple_response(response)
            if cleaned and len(cleaned) >= 3:
                return cleaned

            # Last resort: return stripped response
            return response.strip()
        else:
            return self._parser.parse_simple_response(response)

    async def get_status(self) -> SystemStatus:
        """Get device status.

        Returns:
            SystemStatus object
        """
        return await self.execute_command("status")

    # High-level API methods
    async def power_on(self) -> None:
        """Power on the device."""
        await self.execute_command("power_on")

    async def power_off(self) -> None:
        """Power off the device."""
        await self.execute_command("power_off")

    async def set_output_volume(
        self,
        output: int,
        level: Union[int, str],
        unit: str = "percent",
        channel: str = "LR",
    ) -> None:
        """Set output volume.

        Args:
            output: Output channel (0-8, 0=All)
            level: Volume level (0-100 for percent, -76 to +24 for dB, or "+"/"-" for relative)
            unit: Unit type ("percent" or "dB")
            channel: Channel ("L", "R", or "LR")
        """
        kwargs: Dict[str, Any] = {
            "output": output,
            "level": level,
            "channel": channel,
        }
        if not _is_relative_adjustment(level):
            kwargs["unit"] = unit
        await self.execute_command("output_volume", **kwargs)

    async def set_output_mute(self, output: int, mute: bool, channel: str = "LR") -> None:
        """Set output mute.

        Args:
            output: Output channel (0-8, 0=All)
            mute: True to mute, False to unmute
            channel: Channel ("L", "R", or "LR")
        """
        await self.execute_command("output_mute", output=output, mute=mute, channel=channel)

    async def route_input_to_output(
        self,
        input_ch: int,
        output: int,
        output_channel: str = "LR",
        input_channel: str = "LR",
    ) -> None:
        """Route input to output.

        Args:
            input_ch: Input channel (1-24)
            output: Output channel (0-8, 0=All)
            output_channel: Output channel selector ("L", "R", or "LR")
            input_channel: Input channel selector ("L", "R", or "LR")
        """
        await self.execute_command(
            "route",
            input=input_ch,
            output=output,
            output_channel=output_channel,
            input_channel=input_channel,
        )

    async def save_preset(self, preset: int) -> None:
        """Save current configuration to preset.

        Args:
            preset: Preset number (1-8)
        """
        await self.execute_command("preset_save", preset=preset)

    async def recall_preset(self, preset: int) -> None:
        """Recall preset configuration.

        Args:
            preset: Preset number (1-8)
        """
        await self.execute_command("preset_recall", preset=preset)

    async def set_input_gain(
        self,
        input_ch: int,
        gain: Union[int, str],
        channel: str = "LR",
        unit: Optional[str] = None,
    ) -> None:
        """Set input gain.

        Args:
            input_ch: Input channel (0-16, 0=All)
            gain: Gain value (0-100 for percent, -76 to +24 for dB, or "+"/"-" for relative)
            channel: Channel ("L", "R", or "LR")
            unit: Unit type ("percent" or "dB"), None for percent
        """
        kwargs: Dict[str, Any] = {
            "input": input_ch,
            "gain": gain,
            "channel": channel,
        }
        if not _is_relative_adjustment(gain):
            kwargs["unit"] = unit
        await self.execute_command("input_gain", **kwargs)

    async def set_input_mute(self, input_ch: int, mute: bool, channel: str = "LR") -> None:
        """Set input mute.

        Args:
            input_ch: Input channel (0-16, 0=All)
            mute: True to mute, False to unmute
            channel: Channel ("L", "R", or "LR")
        """
        await self.execute_command("input_mute", input=input_ch, mute=mute, channel=channel)

    async def get_preset_status(self, preset: int) -> PresetStatus:
        """Get preset status.

        Args:
            preset: Preset number (1-8)

        Returns:
            PresetStatus object
        """
        return await self.execute_command("preset_status", preset=preset)

    async def remove_input_from_output(
        self,
        output: int,
        input_ch: int,
        output_channel: str = "LR",
        input_channel: str = "LR",
    ) -> None:
        """Remove input from output.

        Args:
            output: Output channel (0-8, 0=All)
            input_ch: Input channel (1-24)
            output_channel: Output channel selector ("L", "R", or "LR")
            input_channel: Input channel selector ("L", "R", or "LR")
        """
        await self.execute_command(
            "output_remove",
            output=output,
            input=input_ch,
            output_channel=output_channel,
            input_channel=input_channel,
        )

    async def set_output_delay(self, output: int, delay_ms: int, channel: str = "LR") -> None:
        """Set output delay.

        Args:
            output: Output channel (0-8, 0=All)
            delay_ms: Delay time in milliseconds (0-500)
            channel: Channel ("L", "R", or "LR")
        """
        await self.execute_command("output_delay", output=output, delay_ms=delay_ms, channel=channel)

    async def set_output_mix(self, output: int, mode: int) -> None:
        """Set output mixing mode.

        Args:
            output: Output channel (0-8, 0=All)
            mode: Mixing mode (0=None, 1=Swap, 2=Mono L+R, 3=Mono All L, 4=Mono All R, 5=Mono L-R, 6=Mono R-L)
        """
        await self.execute_command("output_mix", output=output, mode=mode)

    async def set_output_master_volume(
        self,
        level: Union[int, str],
        unit: str = "percent",
        channel: str = "LR",
    ) -> None:
        """Set output master volume.

        Args:
            level: Volume level (0-100 for percent, -76 to +24 for dB, or "+"/"-" for relative)
            unit: Unit type ("percent" or "dB")
            channel: Channel ("L", "R", or "LR")
        """
        kwargs: Dict[str, Any] = {"level": level, "channel": channel}
        if not _is_relative_adjustment(level):
            kwargs["unit"] = unit
        await self.execute_command("output_master_volume", **kwargs)

    async def set_output_master_mute(self, mute: bool, channel: str = "LR") -> None:
        """Set output master mute.

        Args:
            mute: True to mute, False to unmute
            channel: Channel ("L", "R", or "LR")
        """
        await self.execute_command("output_master_mute", mute=mute, channel=channel)

    async def set_output_channel_lock(self, output: int, lock: bool, channel: str = "LR") -> None:
        """Set output channel lock.

        Args:
            output: Output channel (0-8, 0=All)
            lock: True to lock, False to unlock
            channel: Channel ("L", "R", or "LR")
        """
        await self.execute_command("output_channel_lock", output=output, lock=lock, channel=channel)

    async def get_uptime(self) -> str:
        """Get system uptime.

        Returns:
            Uptime string
        """
        return await self.execute_command("uptime")

    async def get_temperature(self) -> str:
        """Get system temperature.

        Returns:
            Temperature string
        """
        return await self.execute_command("temp")

    async def reboot(self) -> None:
        """Reboot the device."""
        await self.execute_command("reboot")

    async def set_group_volume(
        self,
        group: int,
        level: Union[int, str],
        unit: str = "percent",
        channel: str = "LR",
    ) -> None:
        """Set group volume.

        Args:
            group: Group number (0-4, 0=All)
            level: Volume level (0-100 for percent, -76 to +24 for dB, or "+"/"-" for relative)
            unit: Unit type ("percent" or "dB")
            channel: Channel ("L", "R", or "LR")
        """
        kwargs: Dict[str, Any] = {
            "group": group,
            "level": level,
            "channel": channel,
        }
        if not _is_relative_adjustment(level):
            kwargs["unit"] = unit
        await self.execute_command("group_volume", **kwargs)

    async def set_group_mute(self, group: int, mute: bool, channel: str = "LR") -> None:
        """Set group mute.

        Args:
            group: Group number (0-4, 0=All)
            mute: True to mute, False to unmute
            channel: Channel ("L", "R", or "LR")
        """
        await self.execute_command("group_mute", group=group, mute=mute, channel=channel)


cmd_module._register_commands(DMP168.commands)

