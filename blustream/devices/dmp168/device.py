"""DMP168 device implementation."""

import asyncio
import logging
import re
from datetime import timedelta
from typing import Any, Callable, Optional, Union

from blustream.base.commands import Command, CommandRegistry
from blustream.base.connection import Connection
from blustream.base.device import BlustreamDevice
from blustream.base.exceptions import (
    CommandError,
    ConnectionError,
    ParseError,
    RebootNotConfirmedError,
    TimeoutError,
    ValidationError,
)
from blustream.base.validator import validate
from blustream.connection.tcp import TCPConnection
from blustream.devices.dmp168 import commands as cmd_module
from blustream.devices.dmp168.commands import _is_relative_adjustment
from blustream.devices.dmp168.models import OutputSource, PresetStatus, SystemStatus
from blustream.devices.dmp168.parser import DMP168Parser
from blustream.devices.dmp168.uptime_parser import parse as parse_uptime

logger = logging.getLogger(__name__)

STATUS_RESPONSE_TIMEOUT = 5.0
STATUS_FOOTER_MIN_WIDTH = 16

# How long ``reboot()`` waits for the device to answer again after REBOOT.
# No restart of a real DMP168 has been timed. 60 s leaves room for an
# embedded boot and bounds the wait when the device does not come back.
REBOOT_CONFIRM_TIMEOUT = 60.0
# Pause before each check while ``reboot()`` waits.
REBOOT_POLL_INTERVAL = 2.0
# How long after REBOOT an unreset uptime still means "not down yet" rather
# than "did not restart". It gives a device that acknowledges first and
# restarts a moment later time to go down, and keeps the failure early when
# the device ignores REBOOT.
REBOOT_GRACE = 6.0


def _status_terminator() -> Callable[[str], bool]:
    """Stateful predicate that fires on the STATUS footer ``=``-only line.

    The footer is unambiguous only AFTER the system header (the
    ``Power … Baud …`` line) has come through — that header appears
    exactly once in a STATUS reply and never in any other server-side
    stream the device emits (welcome banner, command echo, error
    response). Counting raw ``=`` lines was the previous heuristic and
    misfired whenever the welcome banner — itself bracketed by two
    ``=``-only sentinels — leaked into the response window via the
    device's broadcast-on-peer-connect quirk on port 23.
    """
    saw_header = False

    def predicate(line: str) -> bool:
        nonlocal saw_header
        if not saw_header:
            if "Power" in line and "Baud" in line:
                saw_header = True
            return False
        stripped = line.rstrip("\r\n")
        return (
            bool(stripped)
            and len(stripped) >= STATUS_FOOTER_MIN_WIDTH
            and set(stripped) == {"="}
        )

    return predicate


def _help_terminator() -> Callable[[str], bool]:
    """Stateful predicate that fires on the ``=``-only footer of HELP.

    ``HELP`` (``?/HELP`` in the protocol) streams a multi-section command
    listing with no ``[SUCCESS]``/``[ERROR]`` marker; it ends with a
    ``=``-only rule before the trailing DSP-utilisation prose. The
    section headers (``======= System Control Command``) carry text, so
    they are never ``=``-only — only the closing rule is. As with
    ``_status_terminator``, arm only AFTER the help header is seen so a
    welcome-banner ``=``-only sentinel (the device re-broadcasts the
    banner to every port-23 client on peer connect) can't end the read
    before the listing has even started.
    """
    armed = False

    def predicate(line: str) -> bool:
        nonlocal armed
        if not armed:
            if "Help Info" in line or "Print Help Information" in line:
                armed = True
            return False
        stripped = line.rstrip("\r\n")
        return (
            bool(stripped)
            and len(stripped) >= STATUS_FOOTER_MIN_WIDTH
            and set(stripped) == {"="}
        )

    return predicate


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

    def get_commands(self) -> list[str]:
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
            CommandError: If command execution fails, or the device answers
                with an ``[ERROR]`` line (the message carries its text)
            ParseError: If a STATUS or PRESET STATUS reply can't be parsed
            ValidationError: If parameters are invalid
        """
        validate(self._registry, name, kwargs)
        if name == "reboot":
            # The acknowledgement alone does not show that the device
            # restarted, so the command confirms it (see ``reboot()``).
            await self.reboot()
            return None
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

        # Send command and get response. STATUS streams a long multi-section
        # reply ending in a "===" footer line; everything else terminates on a
        # single [SUCCESS]/[ERROR] marker line, which is the default.
        if name == "status":
            response = await self.send_command(
                cmd_str,
                terminator=_status_terminator(),
                timeout=STATUS_RESPONSE_TIMEOUT,
            )
            return self._parser.parse_status(response)

        if name == "help":
            # HELP has no [SUCCESS] marker; frame on its =-only footer and
            # return the raw listing verbatim (no parsing).
            return (
                await self.send_command(
                    cmd_str,
                    terminator=_help_terminator(),
                    timeout=STATUS_RESPONSE_TIMEOUT,
                )
            ).strip("\r\n")

        response = await self.send_command(cmd_str)

        if name == "preset_status":
            # Pass preset number to parser if available
            preset_number = kwargs.get("preset")
            return self._parser.parse_preset_status(
                response, preset_number=preset_number
            )
        elif name in ["uptime", "temp"]:
            # Extract value from uptime/temp command responses
            # Common formats:
            # - "[SUCCESS]The temperature of the system is 47.4C"
            # - "[SUCCESS]The uptime of the system is 0000:08:57:01"
            # - "47.4C" or "0000:08:57:01" (direct value)

            # Try [SUCCESS] pattern first
            success_match = re.search(
                r"\[SUCCESS\].*?is\s+([^\s]+)", response, re.IGNORECASE
            )
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

        Raises:
            CommandError: If the command fails or the link drops
            ParseError: If the STATUS dump is corrupted or malformed, so the
                caller can retry on its next poll
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
        kwargs: dict[str, Any] = {
            "output": output,
            "level": level,
            "channel": channel,
        }
        if not _is_relative_adjustment(level):
            kwargs["unit"] = unit
        await self.execute_command("output_volume", **kwargs)

    async def set_output_mute(
        self, output: int, mute: bool, channel: str = "LR"
    ) -> None:
        """Set output mute.

        Args:
            output: Output channel (0-8, 0=All)
            mute: True to mute, False to unmute
            channel: Channel ("L", "R", or "LR")
        """
        await self.execute_command(
            "output_mute", output=output, mute=mute, channel=channel
        )

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

    async def set_output_source(
        self, output: int, source: Optional[OutputSource]
    ) -> None:
        """Set the single source feeding an output, or clear it.

        Per ADR 0014 each output is fed by exactly one source. Routing an input
        or bus maps to the ``route`` wire command (the source's unified 1-24
        column address stays inside the library); ``source=None`` clears the
        route via ``output_remove`` — the device's "None" routing target.

        Because the device's REM command removes a *specific* source, clearing
        first reads status to find the source presently feeding ``output``
        (the L channel is canonical), then removes it. It is a no-op when the
        output is already unrouted.

        Args:
            output: Output channel (1-8).
            source: The input or bus to route, or None to clear the route.
        """
        if source is not None:
            await self.execute_command("route", output=output, input=source.column)
            return

        current = await self._current_output_source(output)
        if current is None:
            return
        await self.execute_command("output_remove", output=output, input=current.column)

    async def _current_output_source(self, output: int) -> Optional[OutputSource]:
        """Return the source currently routed to ``output`` (L channel), or None."""
        status = await self.get_status()
        for row in status.routing:
            if row.output == output and row.channel == "L":
                return row.source
        return None

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
        kwargs: dict[str, Any] = {
            "input": input_ch,
            "gain": gain,
            "channel": channel,
        }
        if not _is_relative_adjustment(gain):
            kwargs["unit"] = unit
        await self.execute_command("input_gain", **kwargs)

    async def set_input_mute(
        self, input_ch: int, mute: bool, channel: str = "LR"
    ) -> None:
        """Set input mute.

        Args:
            input_ch: Input channel (0-16, 0=All)
            mute: True to mute, False to unmute
            channel: Channel ("L", "R", or "LR")
        """
        await self.execute_command(
            "input_mute", input=input_ch, mute=mute, channel=channel
        )

    async def get_preset_status(self, preset: int) -> PresetStatus:
        """Get preset status.

        Args:
            preset: Preset number (1-8)

        Returns:
            PresetStatus object

        Raises:
            CommandError: If the device answers with an ``[ERROR]`` line. An
                empty preset is answered that way
                (``[ERROR]Preset 1 config status null.``).
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

    async def set_output_delay(
        self, output: int, delay_ms: int, channel: str = "LR"
    ) -> None:
        """Set output delay.

        Args:
            output: Output channel (0-8, 0=All)
            delay_ms: Delay time in milliseconds (0-500)
            channel: Channel ("L", "R", or "LR")
        """
        await self.execute_command(
            "output_delay", output=output, delay_ms=delay_ms, channel=channel
        )

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
        kwargs: dict[str, Any] = {"level": level, "channel": channel}
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

    async def set_output_channel_lock(
        self, output: int, lock: bool, channel: str = "LR"
    ) -> None:
        """Set output channel lock.

        Args:
            output: Output channel (0-8, 0=All)
            lock: True to lock, False to unlock
            channel: Channel ("L", "R", or "LR")
        """
        await self.execute_command(
            "output_channel_lock", output=output, lock=lock, channel=channel
        )

    async def get_uptime_raw(self) -> str:
        """Get the raw system uptime-duration string.

        Returns:
            The raw ``DDDD:HH:MM:SS`` uptime-duration string, exactly as the
            device reports it (see CONTEXT.md "Uptime").
        """
        return await self.execute_command("uptime")

    async def get_uptime(self) -> timedelta:
        """Get system uptime as a duration.

        Returns:
            The system uptime parsed into a :class:`datetime.timedelta`.

        Raises:
            ParseError: If the device reply can't be parsed into a duration
                (see :func:`blustream.devices.dmp168.uptime_parser.parse`).
        """
        return parse_uptime(await self.get_uptime_raw())

    async def get_temperature(self) -> str:
        """Get system temperature.

        Returns:
            Temperature string
        """
        return await self.execute_command("temp")

    async def get_help(self) -> str:
        """Return the device's raw ``?/HELP`` command listing.

        A read-only diagnostic: the device's own authoritative record of the
        commands its firmware supports (the published API doc and user manual
        have been observed to drift from it). Returned verbatim.
        """
        return await self.execute_command("help")

    async def reboot(
        self, *, confirm: bool = True, timeout: float = REBOOT_CONFIRM_TIMEOUT
    ) -> None:
        """Reboot the device and confirm that it restarted.

        Reads the uptime, sends REBOOT, then checks every
        ``REBOOT_POLL_INTERVAL`` seconds. Each check reconnects if the device
        dropped the link, then reads the uptime. An uptime lower than before
        means the device restarted, and this returns. An uptime that is not
        lower once ``REBOOT_GRACE`` seconds have passed means it did not
        restart, and this raises then instead of waiting out ``timeout``.
        Firmware MCU V1.5.0 acknowledges REBOOT on the TCP control channel
        and keeps running, so the acknowledgement alone is no proof of a
        restart.

        Args:
            confirm: False sends REBOOT and returns once the device
                acknowledges it, without checking that it restarted.
            timeout: Seconds to keep checking for the device after REBOOT.
                A check that starts before the deadline runs to the end, so
                the call can overrun it by one connect and one command.

        Raises:
            RebootNotConfirmedError: The device answered after REBOOT and
                its uptime had not reset.
            TimeoutError: The device did not report its uptime within
                ``timeout``.
            CommandError: The device rejected REBOOT, or the uptime read
                before it failed.
            ConnectionError: The device is not connected.
        """
        if not confirm:
            await self._send_reboot()
            return

        before = await self.get_uptime()
        try:
            await self._send_reboot()
        except CommandError as err:
            if not isinstance(err.__cause__, (ConnectionError, TimeoutError)):
                raise
            # The link dropped or went quiet before the acknowledgement,
            # which a restarting device can do. The checks below decide.
            logger.debug("No acknowledgement of REBOOT: %s", err)

        loop = asyncio.get_running_loop()
        sent_at = loop.time()
        deadline = sent_at + timeout
        while True:
            await asyncio.sleep(REBOOT_POLL_INTERVAL)
            after = await self._uptime_if_answering()
            now = loop.time()
            if after is not None and after < before:
                logger.info("Device restarted; uptime is now %s", after)
                return
            if after is not None and (now - sent_at >= REBOOT_GRACE or now >= deadline):
                raise RebootNotConfirmedError(
                    "Device acknowledged REBOOT but did not restart: its uptime "
                    f"went from {before} to {after} without a reset."
                )
            if now >= deadline:
                raise TimeoutError(
                    f"Device did not report its uptime within {timeout:g} s of "
                    "REBOOT. It may still be restarting, or it may be unreachable."
                )

    async def _send_reboot(self) -> None:
        """Send REBOOT and wait for the device's acknowledgement."""
        await self.send_command(self._registry.get("reboot").handler())

    async def _uptime_if_answering(self) -> Optional[timedelta]:
        """Reconnect if needed and read the uptime; None while the device is silent."""
        try:
            await self.connect()
            return await self.get_uptime()
        except (ConnectionError, TimeoutError, CommandError, ParseError) as err:
            logger.debug("Device not answering after REBOOT yet: %s", err)
            return None

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
        kwargs: dict[str, Any] = {
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
        await self.execute_command(
            "group_mute", group=group, mute=mute, channel=channel
        )


cmd_module._register_commands(DMP168.commands)
