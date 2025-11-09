"""Main CLI entry point."""

import argparse
import asyncio
import json
import logging
import sys
from typing import Any, Optional

from bluestream import DMP168
from bluestream.base.exceptions import BluestreamError, ConnectionError


def suppress_telnetlib3_errors(loop, context):
    """Suppress harmless telnetlib3 'feed_data after feed_eof' errors."""
    exception = context.get('exception')
    if exception and isinstance(exception, AssertionError):
        if "feed_data after feed_eof" in str(exception):
            # Suppress this harmless error
            return
    # Use default handler for other exceptions
    loop.default_exception_handler(context)


def get_internal_command_name(cli_command: str, action: Optional[str] = None) -> Optional[str]:
    """Map CLI command name to internal command name.

    Args:
        cli_command: CLI command name (e.g., "power", "preset")
        action: Optional action for commands that have sub-actions (e.g., "save", "recall")

    Returns:
        Internal command name or None if not found
    """
    # Map CLI commands to internal command names
    command_map = {
        "status": "status",
        "power": "power_on" if action == "on" else "power_off" if action == "off" else None,
        "volume": "output_volume",
        "mute": "output_mute",
        "route": "route",
        "input-gain": "input_gain",
        "input-mute": "input_mute",
        "preset": {
            "save": "preset_save",
            "recall": "preset_recall",
            "delete": "preset_delete",
            "status": "preset_status",
        }.get(action) if action else None,
        "unroute": "output_remove",
        "delay": "output_delay",
        "mix": "output_mix",
        "master-volume": "output_master_volume",
        "master-mute": "output_master_mute",
        "output-lock": "output_channel_lock",
        "uptime": "uptime",
        "temp": "temp",
        "reboot": "reboot",
        "group-volume": "group_volume",
        "group-mute": "group_mute",
    }

    if cli_command == "preset" and action:
        return command_map.get("preset", {}).get(action) if isinstance(command_map.get("preset"), dict) else None
    elif cli_command == "power" and action:
        return command_map.get("power")
    else:
        result = command_map.get(cli_command)
        return result if isinstance(result, str) else None


def check_and_confirm_command(
    device: Any, cli_command: str, action: Optional[str] = None, yes: bool = False, preset: Optional[int] = None
) -> bool:
    """Check if command requires confirmation and prompt user if needed.

    Args:
        device: Device instance with command_requires_confirmation method
        cli_command: CLI command name
        action: Optional action for commands with sub-actions
        yes: If True, skip confirmation
        preset: Optional preset number for preset commands

    Returns:
        True if command should proceed, False if cancelled
    """
    internal_name = get_internal_command_name(cli_command, action)
    if not internal_name:
        # If we can't map the command, proceed (for read-only commands)
        return True

    if not device.command_requires_confirmation(internal_name):
        return True

    if yes:
        return True

    # Build confirmation message
    if cli_command == "preset" and action == "save":
        preset_str = f" {preset}" if preset else ""
        confirm_msg = f"Save current configuration to preset{preset_str}? (yes/no): "
    elif cli_command == "preset" and action == "delete":
        preset_str = f" {preset}" if preset else ""
        confirm_msg = f"Delete preset{preset_str}? (yes/no): "
    elif cli_command == "reboot":
        confirm_msg = "Reboot the device? (yes/no): "
    else:
        confirm_msg = f"Execute {cli_command}? (yes/no): "

    confirm = input(confirm_msg)
    if confirm.lower() not in ["yes", "y"]:
        print("Cancelled")
        return False

    return True


def setup_logging(verbose: bool = False, debug: bool = False) -> None:
    """Setup logging configuration.

    Args:
        verbose: Enable INFO level logging
        debug: Enable DEBUG level logging
    """
    level = logging.WARNING
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def format_status(status: Any, json_output: bool = False) -> str:
    """Format status output.

    Args:
        status: SystemStatus object
        json_output: Output as JSON

    Returns:
        Formatted string
    """
    if json_output:
        return json.dumps(
            {
                "power": status.power,
                "baud": status.baud,
                "level_unit": status.level_unit,
                "auto_standby_time": status.auto_standby_time,
                "dsp_usage": status.dsp_usage,
                "fade": status.fade,
                "temperature": status.temperature,
                "uptime": status.uptime,
                "firmware_version": status.firmware_version,
                "inputs": [
                    {
                        "port": inp.port,
                        "lock": inp.lock,
                        "gain_l": inp.gain_l,
                        "gain_r": inp.gain_r,
                        "mute_l": inp.mute_l,
                        "mute_r": inp.mute_r,
                    }
                    for inp in status.inputs
                ],
                "routing": [
                    {
                        "output": r.output,
                        "channel": r.channel,
                        "from_input": r.from_input,
                    }
                    for r in status.routing
                ],
            },
            indent=2,
        )
    else:
        lines = [
            f"Power: {status.power}",
            f"Baud: {status.baud}",
            f"Level Unit: {status.level_unit}",
            f"Auto Standby: {status.auto_standby_time} mins",
            f"DSP Usage: {status.dsp_usage}%",
            f"Fade: {'On' if status.fade else 'Off'}",
            f"Temperature: {status.temperature}°C",
            f"Uptime: {status.uptime}",
            f"Firmware: {status.firmware_version}",
            "",
            "Input Settings:",
        ]
        for inp in status.inputs:
            lines.append(
                f"  In{inp.port}: Gain L={inp.gain_l} R={inp.gain_r}, "
                f"Mute L={'On' if inp.mute_l else 'Off'} R={'On' if inp.mute_r else 'Off'}, "
                f"Lock={'On' if inp.lock else 'Off'}"
            )
        lines.append("")
        lines.append("Output Routing:")
        for r in status.routing:
            if r.from_input:
                lines.append(f"  Out{r.output} {r.channel}: From In{r.from_input}")
            else:
                lines.append(f"  Out{r.output} {r.channel}: Not routed")
        return "\n".join(lines)


def add_global_options(parser: argparse.ArgumentParser) -> None:
    """Add global options to a parser (for use with subparsers).

    Args:
        parser: ArgumentParser to add options to
    """
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmations",
    )


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser.

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="Bluestream device control CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Global options
    parser.add_argument(
        "--device",
        choices=["dmp168"],
        default="dmp168",
        help="Device type (default: dmp168)",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Device hostname or IP address (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=23,
        help="TCP port (default: 23)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Connection timeout in seconds (default: 5.0)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmations",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Status command
    status_parser = subparsers.add_parser("status", help="Get device status")
    add_global_options(status_parser)

    # Power commands
    power_parser = subparsers.add_parser("power", help="Power control")
    add_global_options(power_parser)
    power_parser.add_argument(
        "state",
        choices=["on", "off"],
        help="Power state",
    )

    # Volume command
    volume_parser = subparsers.add_parser("volume", help="Set output volume")
    add_global_options(volume_parser)
    volume_parser.add_argument(
        "--output",
        "-o",
        type=int,
        required=True,
        choices=range(9),
        help="Output channel (0-8, 0=All)",
    )
    volume_parser.add_argument(
        "--level",
        "-l",
        type=int,
        required=True,
        help="Volume level (0-100 for percent, -76 to +24 for dB)",
    )
    volume_parser.add_argument(
        "--unit",
        "-u",
        choices=["percent", "dB"],
        default="percent",
        help="Volume unit (default: percent)",
    )
    volume_parser.add_argument(
        "--channel",
        "-c",
        choices=["L", "R", "LR"],
        default="LR",
        help="Channel to adjust (default: LR)",
    )

    # Mute command
    mute_parser = subparsers.add_parser("mute", help="Set output mute")
    add_global_options(mute_parser)
    mute_parser.add_argument(
        "--output",
        "-o",
        type=int,
        required=True,
        choices=range(9),
        help="Output channel (0-8, 0=All)",
    )
    mute_parser.add_argument(
        "state",
        choices=["on", "off"],
        help="Mute state",
    )
    mute_parser.add_argument(
        "--channel",
        "-c",
        choices=["L", "R", "LR"],
        default="LR",
        help="Channel to adjust (default: LR)",
    )

    # Route command
    route_parser = subparsers.add_parser("route", help="Route input to output")
    add_global_options(route_parser)
    route_parser.add_argument(
        "--output",
        "-o",
        type=int,
        required=True,
        choices=range(9),
        help="Output channel (0-8, 0=All)",
    )
    route_parser.add_argument(
        "--input",
        "-i",
        type=int,
        required=True,
        choices=range(1, 25),
        help="Input channel (1-24)",
    )
    route_parser.add_argument(
        "--output-channel",
        choices=["L", "R", "LR"],
        default="LR",
        help="Output channel selector (default: LR)",
    )
    route_parser.add_argument(
        "--input-channel",
        choices=["L", "R", "LR"],
        default="LR",
        help="Input channel selector (default: LR)",
    )

    # Input gain command
    input_gain_parser = subparsers.add_parser("input-gain", help="Set input gain")
    add_global_options(input_gain_parser)
    input_gain_parser.add_argument(
        "--input",
        "-i",
        type=int,
        required=True,
        choices=range(17),
        help="Input channel (0-16, 0=All)",
    )
    input_gain_parser.add_argument(
        "--gain",
        "-g",
        type=int,
        required=True,
        help="Gain value (0-100 for percent, -76 to +24 for dB)",
    )
    input_gain_parser.add_argument(
        "--unit",
        "-u",
        choices=["percent", "dB"],
        default="percent",
        help="Gain unit (default: percent)",
    )
    input_gain_parser.add_argument(
        "--channel",
        "-c",
        choices=["L", "R", "LR"],
        default="LR",
        help="Channel to adjust (default: LR)",
    )

    # Input mute command
    input_mute_parser = subparsers.add_parser("input-mute", help="Set input mute")
    add_global_options(input_mute_parser)
    input_mute_parser.add_argument(
        "--input",
        "-i",
        type=int,
        required=True,
        choices=range(17),
        help="Input channel (0-16, 0=All)",
    )
    input_mute_parser.add_argument(
        "state",
        choices=["on", "off"],
        help="Mute state",
    )
    input_mute_parser.add_argument(
        "--channel",
        "-c",
        choices=["L", "R", "LR"],
        default="LR",
        help="Channel to adjust (default: LR)",
    )

    # Preset commands
    preset_parser = subparsers.add_parser("preset", help="Preset management")
    add_global_options(preset_parser)
    preset_parser.add_argument(
        "action",
        choices=["save", "recall", "delete", "status"],
        help="Preset action",
    )
    preset_parser.add_argument(
        "--preset",
        "-p",
        type=int,
        required=True,
        choices=range(1, 9),
        help="Preset number (1-8)",
    )

    # Unroute command (remove input from output)
    unroute_parser = subparsers.add_parser("unroute", help="Remove input from output")
    add_global_options(unroute_parser)
    unroute_parser.add_argument(
        "--output",
        "-o",
        type=int,
        required=True,
        choices=range(9),
        help="Output channel (0-8, 0=All)",
    )
    unroute_parser.add_argument(
        "--input",
        "-i",
        type=int,
        required=True,
        choices=range(1, 25),
        help="Input channel (1-24)",
    )
    unroute_parser.add_argument(
        "--output-channel",
        choices=["L", "R", "LR"],
        default="LR",
        help="Output channel selector (default: LR)",
    )
    unroute_parser.add_argument(
        "--input-channel",
        choices=["L", "R", "LR"],
        default="LR",
        help="Input channel selector (default: LR)",
    )

    # Delay command
    delay_parser = subparsers.add_parser("delay", help="Set output delay")
    add_global_options(delay_parser)
    delay_parser.add_argument(
        "--output",
        "-o",
        type=int,
        required=True,
        choices=range(9),
        help="Output channel (0-8, 0=All)",
    )
    delay_parser.add_argument(
        "--delay",
        "-d",
        type=int,
        required=True,
        help="Delay time in milliseconds (0-500)",
    )
    delay_parser.add_argument(
        "--channel",
        "-c",
        choices=["L", "R", "LR"],
        default="LR",
        help="Channel to adjust (default: LR)",
    )

    # Mix command
    mix_parser = subparsers.add_parser("mix", help="Set output mixing mode")
    add_global_options(mix_parser)
    mix_parser.add_argument(
        "--output",
        "-o",
        type=int,
        required=True,
        choices=range(9),
        help="Output channel (0-8, 0=All)",
    )
    mix_parser.add_argument(
        "--mode",
        "-m",
        type=int,
        required=True,
        choices=range(7),
        help="Mix mode (0=None, 1=Swap, 2=Mono L+R, 3=Mono All L, 4=Mono All R, 5=Mono L-R, 6=Mono R-L)",
    )

    # Master volume command
    master_volume_parser = subparsers.add_parser("master-volume", help="Set output master volume")
    add_global_options(master_volume_parser)
    master_volume_parser.add_argument(
        "--level",
        "-l",
        type=int,
        required=True,
        help="Volume level (0-100 for percent, -76 to +24 for dB)",
    )
    master_volume_parser.add_argument(
        "--unit",
        "-u",
        choices=["percent", "dB"],
        default="percent",
        help="Volume unit (default: percent)",
    )
    master_volume_parser.add_argument(
        "--channel",
        "-c",
        choices=["L", "R", "LR"],
        default="LR",
        help="Channel to adjust (default: LR)",
    )

    # Master mute command
    master_mute_parser = subparsers.add_parser("master-mute", help="Set output master mute")
    add_global_options(master_mute_parser)
    master_mute_parser.add_argument(
        "state",
        choices=["on", "off"],
        help="Mute state",
    )
    master_mute_parser.add_argument(
        "--channel",
        "-c",
        choices=["L", "R", "LR"],
        default="LR",
        help="Channel to adjust (default: LR)",
    )

    # Output lock command
    output_lock_parser = subparsers.add_parser("output-lock", help="Set output channel lock")
    add_global_options(output_lock_parser)
    output_lock_parser.add_argument(
        "--output",
        "-o",
        type=int,
        required=True,
        choices=range(9),
        help="Output channel (0-8, 0=All)",
    )
    output_lock_parser.add_argument(
        "state",
        choices=["on", "off"],
        help="Lock state",
    )
    output_lock_parser.add_argument(
        "--channel",
        "-c",
        choices=["L", "R", "LR"],
        default="LR",
        help="Channel to adjust (default: LR)",
    )

    # Uptime command
    uptime_parser = subparsers.add_parser("uptime", help="Get system uptime")
    add_global_options(uptime_parser)

    # Temperature command
    temp_parser = subparsers.add_parser("temp", help="Get system temperature")
    add_global_options(temp_parser)

    # Reboot command
    reboot_parser = subparsers.add_parser("reboot", help="Reboot system")
    add_global_options(reboot_parser)

    # Group volume command
    group_volume_parser = subparsers.add_parser("group-volume", help="Set group volume")
    add_global_options(group_volume_parser)
    group_volume_parser.add_argument(
        "--group",
        "-g",
        type=int,
        required=True,
        choices=range(5),
        help="Group number (0-4, 0=All)",
    )
    group_volume_parser.add_argument(
        "--level",
        "-l",
        type=int,
        required=True,
        help="Volume level (0-100 for percent, -76 to +24 for dB)",
    )
    group_volume_parser.add_argument(
        "--unit",
        "-u",
        choices=["percent", "dB"],
        default="percent",
        help="Volume unit (default: percent)",
    )
    group_volume_parser.add_argument(
        "--channel",
        "-c",
        choices=["L", "R", "LR"],
        default="LR",
        help="Channel to adjust (default: LR)",
    )

    # Group mute command
    group_mute_parser = subparsers.add_parser("group-mute", help="Set group mute")
    add_global_options(group_mute_parser)
    group_mute_parser.add_argument(
        "--group",
        "-g",
        type=int,
        required=True,
        choices=range(5),
        help="Group number (0-4, 0=All)",
    )
    group_mute_parser.add_argument(
        "state",
        choices=["on", "off"],
        help="Mute state",
    )
    group_mute_parser.add_argument(
        "--channel",
        "-c",
        choices=["L", "R", "LR"],
        default="LR",
        help="Channel to adjust (default: LR)",
    )

    # List commands
    list_commands_parser = subparsers.add_parser("list-commands", help="List available commands")
    add_global_options(list_commands_parser)

    return parser


async def main_async() -> int:
    """Main CLI entry point (async).

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    setup_logging(verbose=args.verbose, debug=args.debug)

    # Set exception handler to suppress harmless telnetlib3 errors
    try:
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(suppress_telnetlib3_errors)
    except RuntimeError:
        # No running loop yet, will be set when loop is created
        pass

    try:
        # Create device
        device = DMP168(host=args.host, port=args.port, timeout=args.timeout)

        # Connect
        try:
            await device.connect()
        except ConnectionError as e:
            print(f"Error: Failed to connect to {args.host}:{args.port}: {e}", file=sys.stderr)
            return 1

        try:
            # Handle commands
            if args.command == "status":
                status = await device.get_status()
                print(format_status(status, json_output=args.json))

            elif args.command == "power":
                if args.state == "on":
                    await device.power_on()
                    print("Power on")
                else:
                    await device.power_off()
                    print("Power off")

            elif args.command == "volume":
                await device.set_output_volume(
                    output=args.output,
                    level=args.level,
                    unit=args.unit,
                    channel=args.channel,
                )
                print(f"Set output {args.output} volume to {args.level} {args.unit}")

            elif args.command == "mute":
                await device.set_output_mute(
                    output=args.output,
                    mute=(args.state == "on"),
                    channel=args.channel,
                )
                print(f"Output {args.output} mute: {args.state}")

            elif args.command == "route":
                await device.execute_command(
                    "route",
                    output=args.output,
                    input=args.input,
                    output_channel=args.output_channel,
                    input_channel=args.input_channel,
                )
                print(f"Routed input {args.input} to output {args.output}")

            elif args.command == "input-gain":
                await device.execute_command(
                    "input_gain",
                    input_ch=args.input,
                    gain=args.gain,
                    unit=args.unit,
                    channel=args.channel,
                )
                print(f"Set input {args.input} gain to {args.gain} {args.unit}")

            elif args.command == "input-mute":
                await device.execute_command(
                    "input_mute",
                    input_ch=args.input,
                    mute=(args.state == "on"),
                    channel=args.channel,
                )
                print(f"Input {args.input} mute: {args.state}")

            elif args.command == "preset":
                if args.action == "save":
                    if not check_and_confirm_command(device, "preset", "save", args.yes, args.preset):
                        return 0
                    await device.save_preset(args.preset)
                    print(f"Saved configuration to preset {args.preset}")
                elif args.action == "recall":
                    # Recall doesn't require confirmation, but check anyway for consistency
                    if not check_and_confirm_command(device, "preset", "recall", args.yes):
                        return 0
                    await device.recall_preset(args.preset)
                    print(f"Recalled preset {args.preset}")
                elif args.action == "delete":
                    if not check_and_confirm_command(device, "preset", "delete", args.yes, args.preset):
                        return 0
                    await device.execute_command("preset_delete", preset=args.preset)
                    print(f"Deleted preset {args.preset}")
                elif args.action == "status":
                    preset_status = await device.get_preset_status(args.preset)
                    if args.json:
                        print(json.dumps({
                            "preset_number": preset_status.preset_number,
                            "exists": preset_status.exists,
                            "description": preset_status.description,
                        }, indent=2))
                    else:
                        print(f"Preset {preset_status.preset_number}: {'Exists' if preset_status.exists else 'Not found'}")
                        if preset_status.description:
                            print(f"Description: {preset_status.description}")

            elif args.command == "unroute":
                await device.remove_input_from_output(
                    output=args.output,
                    input_ch=args.input,
                    output_channel=args.output_channel,
                    input_channel=args.input_channel,
                )
                print(f"Removed input {args.input} from output {args.output}")

            elif args.command == "delay":
                await device.set_output_delay(
                    output=args.output,
                    delay_ms=args.delay,
                    channel=args.channel,
                )
                print(f"Set output {args.output} delay to {args.delay}ms")

            elif args.command == "mix":
                await device.set_output_mix(output=args.output, mode=args.mode)
                mode_names = ["None", "Swap", "Mono L+R", "Mono All L", "Mono All R", "Mono L-R", "Mono R-L"]
                print(f"Set output {args.output} mix mode to {args.mode} ({mode_names[args.mode]})")

            elif args.command == "master-volume":
                await device.set_output_master_volume(
                    level=args.level,
                    unit=args.unit,
                    channel=args.channel,
                )
                print(f"Set master volume to {args.level} {args.unit}")

            elif args.command == "master-mute":
                await device.set_output_master_mute(
                    mute=(args.state == "on"),
                    channel=args.channel,
                )
                print(f"Master mute: {args.state}")

            elif args.command == "output-lock":
                await device.set_output_channel_lock(
                    output=args.output,
                    lock=(args.state == "on"),
                    channel=args.channel,
                )
                print(f"Output {args.output} channel lock: {args.state}")

            elif args.command == "uptime":
                uptime = await device.get_uptime()
                if args.json:
                    print(json.dumps({"uptime": uptime}, indent=2))
                else:
                    print(f"Uptime: {uptime}")

            elif args.command == "temp":
                temp = await device.get_temperature()
                if args.json:
                    print(json.dumps({"temperature": temp}, indent=2))
                else:
                    print(f"Temperature: {temp}")

            elif args.command == "reboot":
                if not check_and_confirm_command(device, "reboot", None, args.yes):
                    return 0
                await device.reboot()
                print("Rebooting device...")

            elif args.command == "group-volume":
                await device.set_group_volume(
                    group=args.group,
                    level=args.level,
                    unit=args.unit,
                    channel=args.channel,
                )
                print(f"Set group {args.group} volume to {args.level} {args.unit}")

            elif args.command == "group-mute":
                await device.set_group_mute(
                    group=args.group,
                    mute=(args.state == "on"),
                    channel=args.channel,
                )
                print(f"Group {args.group} mute: {args.state}")

            elif args.command == "list-commands":
                # Map internal command names to CLI subcommand names
                command_map = {
                    "status": "status",
                    "power_on": "power on",
                    "power_off": "power off",
                    "output_volume": "volume",
                    "output_mute": "mute",
                    "input_gain": "input-gain",
                    "input_mute": "input-mute",
                    "route": "route",
                    "preset_save": "preset save",
                    "preset_recall": "preset recall",
                    "preset_delete": "preset delete",
                    "preset_status": "preset status",
                    "output_remove": "unroute",
                    "output_delay": "delay",
                    "output_mix": "mix",
                    "output_master_volume": "master-volume",
                    "output_master_mute": "master-mute",
                    "output_channel_lock": "output-lock",
                    "uptime": "uptime",
                    "temp": "temp",
                    "reboot": "reboot",
                    "group_volume": "group-volume",
                    "group_mute": "group-mute",
                }

                internal_commands = device.get_commands()
                print("Available CLI commands:")
                print()

                # Show CLI subcommands grouped by category
                cli_commands = []
                for cmd_name in sorted(internal_commands):
                    if cmd_name in command_map:
                        cli_commands.append(command_map[cmd_name])
                    else:
                        # Fallback: show internal name with note
                        cli_commands.append(f"{cmd_name} (use execute_command)")

                for cmd in sorted(set(cli_commands)):
                    print(f"  {cmd}")

            return 0

        finally:
            await device.disconnect()

    except BluestreamError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def main() -> int:
    """Main CLI entry point (synchronous wrapper).

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    # Create new event loop with custom exception handler
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_exception_handler(suppress_telnetlib3_errors)

    try:
        return loop.run_until_complete(main_async())
    finally:
        loop.close()


if __name__ == "__main__":
    sys.exit(main())

