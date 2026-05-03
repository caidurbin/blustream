"""Command builders for DMP168 device."""

from typing import Any, Optional, Union

from bluestream.base.commands import Command, CommandRegistry, Dependency, Parameter
from bluestream.base.exceptions import ValidationError
from bluestream.devices.dmp168.formatters import format_preset_status, format_status
from bluestream.devices.dmp168.models import PresetStatus, SystemStatus


def _is_relative_adjustment(value: Any) -> bool:
    return isinstance(value, str) and value in ("+", "-")


def build_status_command() -> str:
    """Build STATUS command.

    Returns:
        Command string
    """
    return "STATUS"


def build_power_on_command() -> str:
    """Build PON (Power On) command.

    Returns:
        Command string
    """
    return "PON"


def build_power_off_command() -> str:
    """Build POFF (Power Off) command.

    Returns:
        Command string
    """
    return "POFF"


def build_standby_command(mode: int) -> str:
    """Build STANDBY command.

    Args:
        mode: Standby mode (0=Sleep, 1=Standby)

    Returns:
        Command string
    """
    if mode not in [0, 1]:
        raise ValidationError(
            f"Invalid standby mode '{mode}'. Valid options are: 0 (Sleep) or 1 (Standby). Please choose a valid mode."
        )
    return f"STANDBY {mode}"


def build_output_volume_command(
    output: int,
    level: Union[int, str],
    unit: str = "percent",
    channel: str = "LR",
) -> str:
    """Build OUT xx VOL command.

    Args:
        output: Output channel (0-8, 0=All)
        level: Volume level (0-100 for percent, -76 to +24 for dB, or "+"/"-" for relative)
        unit: Unit type ("percent" or "dB")
        channel: Channel ("L", "R", or "LR")

    Returns:
        Command string
    """
    if output < 0 or output > 8:
        raise ValidationError(
            f"Invalid output channel '{output}'. Output must be between 0-8 (0=All outputs). Please choose a valid output."
        )
    if channel not in ["L", "R", "LR"]:
        raise ValidationError(
            f"Invalid channel '{channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel."
        )
    if unit not in ["percent", "dB"]:
        raise ValidationError(
            f"Invalid unit '{unit}'. Valid options are: 'percent' or 'dB'. Please choose a valid unit."
        )

    cmd = f"OUT {output}"
    if channel != "LR":
        cmd += f" {channel}"
    cmd += " VOL"
    if channel != "LR":
        cmd += f" {channel}"

    # Handle level
    if isinstance(level, str) and level in ["+", "-"]:
        cmd += f" {level}"
    else:
        cmd += f" {level}"
        if unit == "dB":
            cmd += " dB"

    return cmd


def build_output_mute_command(output: int, mute: bool, channel: str = "LR") -> str:
    """Build OUT xx MUTE command.

    Args:
        output: Output channel (0-8, 0=All)
        mute: True to mute, False to unmute
        channel: Channel ("L", "R", or "LR")

    Returns:
        Command string
    """
    if output < 0 or output > 8:
        raise ValidationError(
            f"Invalid output channel '{output}'. Output must be between 0-8 (0=All outputs). Please choose a valid output."
        )
    if channel not in ["L", "R", "LR"]:
        raise ValidationError(
            f"Invalid channel '{channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel."
        )

    cmd = f"OUT {output}"
    if channel != "LR":
        cmd += f" {channel}"
    cmd += " MUTE"
    if channel != "LR":
        cmd += f" {channel}"
    cmd += " ON" if mute else " OFF"
    return cmd


def build_route_command(
    output: int, input_ch: int, output_channel: str = "LR", input_channel: str = "LR"
) -> str:
    """Build OUT xx FR (From) command to route input to output.

    Args:
        output: Output channel (0-8, 0=All)
        input_ch: Input channel (1-24)
        output_channel: Output channel selector ("L", "R", or "LR")
        input_channel: Input channel selector ("L", "R", or "LR")

    Returns:
        Command string
    """
    if output < 0 or output > 8:
        raise ValidationError(
            f"Invalid output channel '{output}'. Output must be between 0-8 (0=All outputs). Please choose a valid output."
        )
    if input_ch < 1 or input_ch > 24:
        raise ValidationError(
            f"Invalid input channel '{input_ch}'. Input must be between 1-24. Please choose a valid input."
        )
    if output_channel not in ["L", "R", "LR"]:
        raise ValidationError(
            f"Invalid output channel '{output_channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel."
        )
    if input_channel not in ["L", "R", "LR"]:
        raise ValidationError(
            f"Invalid input channel '{input_channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel."
        )

    cmd = f"OUT {output}"
    if output_channel != "LR":
        cmd += f" {output_channel}"
    cmd += f" FR {input_ch}"
    if input_channel != "LR":
        cmd += f" {input_channel}"
    return cmd


def build_input_gain_command(
    input_ch: int,
    gain: Union[int, str],
    channel: str = "LR",
    unit: Optional[str] = None,
) -> str:
    """Build IN xx GAIN command.

    Args:
        input_ch: Input channel (0-16, 0=All)
        gain: Gain value (0-100 for percent, -76 to +24 for dB, or "+"/"-" for relative)
        channel: Channel ("L", "R", or "LR")
        unit: Unit type ("percent" or "dB"), None for percent

    Returns:
        Command string
    """
    if input_ch < 0 or input_ch > 16:
        raise ValidationError(
            f"Invalid input channel '{input_ch}'. Input must be between 0-16 (0=All inputs). Please choose a valid input."
        )
    if channel not in ["L", "R", "LR"]:
        raise ValidationError(
            f"Invalid channel '{channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel."
        )

    cmd = f"IN {input_ch}"
    if channel != "LR":
        cmd += f" {channel}"
    cmd += " GAIN"

    # Handle gain value
    if isinstance(gain, str) and gain in ["+", "-"]:
        cmd += f" {gain}"
    else:
        cmd += f" {gain}"
        if unit == "dB":
            cmd += " dB"

    return cmd


def build_input_mute_command(input_ch: int, mute: bool, channel: str = "LR") -> str:
    """Build IN xx MUTE command.

    Args:
        input_ch: Input channel (0-16, 0=All)
        mute: True to mute, False to unmute
        channel: Channel ("L", "R", or "LR")

    Returns:
        Command string
    """
    if input_ch < 0 or input_ch > 16:
        raise ValidationError(
            f"Invalid input channel '{input_ch}'. Input must be between 0-16 (0=All inputs). Please choose a valid input."
        )
    if channel not in ["L", "R", "LR"]:
        raise ValidationError(
            f"Invalid channel '{channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel."
        )

    cmd = f"IN {input_ch}"
    if channel != "LR":
        cmd += f" {channel}"
    cmd += " MUTE"
    if channel != "LR":
        cmd += f" {channel}"
    cmd += " ON" if mute else " OFF"
    return cmd


def build_preset_save_command(preset: int) -> str:
    """Build PRESET xx SAVE command.

    Args:
        preset: Preset number (1-8)

    Returns:
        Command string
    """
    if preset < 1 or preset > 8:
        raise ValidationError(
            f"Invalid preset number '{preset}'. Preset must be between 1-8. Please choose a valid preset."
        )
    return f"PRESET {preset} SAVE"


def build_preset_recall_command(preset: int) -> str:
    """Build PRESET xx APPLY command.

    Args:
        preset: Preset number (1-8)

    Returns:
        Command string
    """
    if preset < 1 or preset > 8:
        raise ValidationError(
            f"Invalid preset number '{preset}'. Preset must be between 1-8. Please choose a valid preset."
        )
    return f"PRESET {preset} APPLY"


def build_preset_delete_command(preset: int) -> str:
    """Build PRESET xx DELETE command.

    Args:
        preset: Preset number (1-8)

    Returns:
        Command string
    """
    if preset < 1 or preset > 8:
        raise ValidationError(
            f"Invalid preset number '{preset}'. Preset must be between 1-8. Please choose a valid preset."
        )
    return f"PRESET {preset} DELETE"


def build_preset_status_command(preset: int) -> str:
    """Build PRESET xx STATUS command.

    Args:
        preset: Preset number (1-8)

    Returns:
        Command string
    """
    if preset < 1 or preset > 8:
        raise ValidationError(
            f"Invalid preset number '{preset}'. Preset must be between 1-8. Please choose a valid preset."
        )
    return f"PRESET {preset} STATUS"


def build_output_remove_command(
    output: int, input_ch: int, output_channel: str = "LR", input_channel: str = "LR"
) -> str:
    """Build OUT xx REM (Remove) command to remove input from output.

    Args:
        output: Output channel (0-8, 0=All)
        input_ch: Input channel (1-24)
        output_channel: Output channel selector ("L", "R", or "LR")
        input_channel: Input channel selector ("L", "R", or "LR")

    Returns:
        Command string
    """
    if output < 0 or output > 8:
        raise ValidationError(
            f"Invalid output channel '{output}'. Output must be between 0-8 (0=All outputs). Please choose a valid output."
        )
    if input_ch < 1 or input_ch > 24:
        raise ValidationError(
            f"Invalid input channel '{input_ch}'. Input must be between 1-24. Please choose a valid input."
        )
    if output_channel not in ["L", "R", "LR"]:
        raise ValidationError(
            f"Invalid output channel '{output_channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel."
        )
    if input_channel not in ["L", "R", "LR"]:
        raise ValidationError(
            f"Invalid input channel '{input_channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel."
        )

    cmd = f"OUT {output}"
    if output_channel != "LR":
        cmd += f" {output_channel}"
    cmd += f" REM {input_ch}"
    if input_channel != "LR":
        cmd += f" {input_channel}"
    return cmd


def build_output_delay_command(output: int, delay_ms: int, channel: str = "LR") -> str:
    """Build OUT xx DELAY command.

    Args:
        output: Output channel (0-8, 0=All)
        delay_ms: Delay time in milliseconds (0-500)
        channel: Channel ("L", "R", or "LR")

    Returns:
        Command string
    """
    if output < 0 or output > 8:
        raise ValidationError(
            f"Invalid output channel '{output}'. Output must be between 0-8 (0=All outputs). Please choose a valid output."
        )
    if delay_ms < 0 or delay_ms > 500:
        raise ValidationError(
            f"Invalid delay value '{delay_ms}'. Delay must be between 0-500 milliseconds. Please choose a valid delay."
        )
    if channel not in ["L", "R", "LR"]:
        raise ValidationError(
            f"Invalid channel '{channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel."
        )

    cmd = f"OUT {output}"
    if channel != "LR":
        cmd += f" {channel}"
    cmd += f" DELAY {delay_ms}"
    return cmd


def build_output_mix_command(output: int, mode: int) -> str:
    """Build OUT xx MIX command.

    Args:
        output: Output channel (0-8, 0=All)
        mode: Mixing mode (0=None, 1=Swap, 2=Mono L+R, 3=Mono All L, 4=Mono All R, 5=Mono L-R, 6=Mono R-L)

    Returns:
        Command string
    """
    if output < 0 or output > 8:
        raise ValidationError(
            f"Invalid output channel '{output}'. Output must be between 0-8 (0=All outputs). Please choose a valid output."
        )
    if mode < 0 or mode > 6:
        raise ValidationError(
            f"Invalid mix mode '{mode}'. Mix mode must be between 0-6. Please choose a valid mode."
        )
    return f"OUT {output} MIX {mode}"


def build_output_master_volume_command(
    level: Union[int, str], unit: str = "percent", channel: str = "LR"
) -> str:
    """Build OUT MASTER VOL command.

    Args:
        level: Volume level (0-100 for percent, -76 to +24 for dB, or "+"/"-" for relative)
        unit: Unit type ("percent" or "dB")
        channel: Channel ("L", "R", or "LR")

    Returns:
        Command string
    """
    if channel not in ["L", "R", "LR"]:
        raise ValidationError(
            f"Invalid channel '{channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel."
        )
    if unit not in ["percent", "dB"]:
        raise ValidationError(
            f"Invalid unit '{unit}'. Valid options are: 'percent' or 'dB'. Please choose a valid unit."
        )

    cmd = "OUT MASTER VOL"
    if channel != "LR":
        cmd += f" {channel}"

    # Handle level
    if isinstance(level, str) and level in ["+", "-"]:
        cmd += f" {level}"
    else:
        cmd += f" {level}"
        if unit == "dB":
            cmd += " dB"

    return cmd


def build_output_master_mute_command(mute: bool, channel: str = "LR") -> str:
    """Build OUT MASTER MUTE command.

    Args:
        mute: True to mute, False to unmute
        channel: Channel ("L", "R", or "LR")

    Returns:
        Command string
    """
    if channel not in ["L", "R", "LR"]:
        raise ValidationError(
            f"Invalid channel '{channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel."
        )

    cmd = "OUT MASTER MUTE"
    if channel != "LR":
        cmd += f" {channel}"
    cmd += " ON" if mute else " OFF"
    return cmd


def build_output_channel_lock_command(output: int, lock: bool, channel: str = "LR") -> str:
    """Build OUT xx CH LOCK command.

    Args:
        output: Output channel (0-8, 0=All)
        lock: True to lock, False to unlock
        channel: Channel ("L", "R", or "LR")

    Returns:
        Command string
    """
    if output < 0 or output > 8:
        raise ValidationError(
            f"Invalid output channel '{output}'. Output must be between 0-8 (0=All outputs). Please choose a valid output."
        )
    if channel not in ["L", "R", "LR"]:
        raise ValidationError(
            f"Invalid channel '{channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel."
        )

    cmd = f"OUT {output} CH LOCK"
    if channel != "LR":
        cmd += f" {channel}"
    cmd += " ON" if lock else " OFF"
    return cmd


def build_uptime_command() -> str:
    """Build UPTIME command.

    Returns:
        Command string
    """
    return "UPTIME"


def build_temp_command() -> str:
    """Build TEMP command.

    Returns:
        Command string
    """
    return "TEMP"


def build_reboot_command() -> str:
    """Build REBOOT command.

    Returns:
        Command string
    """
    return "REBOOT"


def build_group_volume_command(
    group: int,
    level: Union[int, str],
    unit: str = "percent",
    channel: str = "LR",
) -> str:
    """Build GROUP xx VOL command.

    Args:
        group: Group number (0-4, 0=All)
        level: Volume level (0-100 for percent, -76 to +24 for dB, or "+"/"-" for relative)
        unit: Unit type ("percent" or "dB")
        channel: Channel ("L", "R", or "LR")

    Returns:
        Command string
    """
    if group < 0 or group > 4:
        raise ValidationError(
            f"Invalid group number '{group}'. Group must be between 0-4 (0=All groups). Please choose a valid group."
        )
    if channel not in ["L", "R", "LR"]:
        raise ValidationError(
            f"Invalid channel '{channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel."
        )
    if unit not in ["percent", "dB"]:
        raise ValidationError(
            f"Invalid unit '{unit}'. Valid options are: 'percent' or 'dB'. Please choose a valid unit."
        )

    cmd = f"GROUP {group} VOL"
    if channel != "LR":
        cmd += f" {channel}"

    # Handle level
    if isinstance(level, str) and level in ["+", "-"]:
        cmd += f" {level}"
    else:
        cmd += f" {level}"
        if unit == "dB":
            cmd += " dB"

    return cmd


def build_group_mute_command(group: int, mute: bool, channel: str = "LR") -> str:
    """Build GROUP xx MUTE command.

    Args:
        group: Group number (0-4, 0=All)
        mute: True to mute, False to unmute
        channel: Channel ("L", "R", or "LR")

    Returns:
        Command string
    """
    if group < 0 or group > 4:
        raise ValidationError(
            f"Invalid group number '{group}'. Group must be between 0-4 (0=All groups). Please choose a valid group."
        )
    if channel not in ["L", "R", "LR"]:
        raise ValidationError(
            f"Invalid channel '{channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel."
        )

    cmd = f"GROUP {group} MUTE"
    if channel != "LR":
        cmd += f" {channel}"
    cmd += " ON" if mute else " OFF"
    return cmd


def _register_commands(registry: CommandRegistry) -> None:
    """Register all DMP168 commands with metadata."""

    # Status command
    registry.register(
        Command(
            name="status",
            description="Get system status and port status",
            parameters=[],
            handler=lambda **kwargs: build_status_command(),
            return_type=SystemStatus,
            format_result=format_status,
        )
    )

    # Power commands
    registry.register(
        Command(
            name="power_on",
            description="Power on, system run on normal state",
            parameters=[],
            handler=lambda **kwargs: build_power_on_command(),
        )
    )

    registry.register(
        Command(
            name="power_off",
            description="Power off, system run on power save state",
            parameters=[],
            handler=lambda **kwargs: build_power_off_command(),
        )
    )

    # Output volume
    registry.register(
        Command(
            name="output_volume",
            description="Set output volume",
            parameters=[
                Parameter("output", int, required=True, choices=list(range(9)), help_text="Output channel (0-8, 0=All)"),
                Parameter("level", Any, required=True, help_text="Volume level (0-100 for percent, -76 to +24 for dB, or +/- for relative)", supports_relative=True),
                Parameter("unit", str, required=False, default="percent", choices=["percent", "dB"], help_text="Volume unit", depends_on=Dependency(on="level", when=_is_relative_adjustment)),
                Parameter("channel", str, required=False, default="LR", choices=["L", "R", "LR"], help_text="Channel to adjust"),
            ],
            handler=lambda **kwargs: build_output_volume_command(**kwargs),
        )
    )

    # Output mute
    registry.register(
        Command(
            name="output_mute",
            description="Set output mute on or off",
            parameters=[
                Parameter("output", int, required=True, choices=list(range(9)), help_text="Output channel (0-8, 0=All)"),
                Parameter("mute", bool, required=True, help_text="True to mute, False to unmute"),
                Parameter("channel", str, required=False, default="LR", choices=["L", "R", "LR"], help_text="Channel to adjust"),
            ],
            handler=lambda **kwargs: build_output_mute_command(**kwargs),
        )
    )

    # Route command
    registry.register(
        Command(
            name="route",
            description="Route input to output",
            parameters=[
                Parameter("output", int, required=True, choices=list(range(9)), help_text="Output channel (0-8, 0=All)"),
                Parameter("input", int, required=True, choices=list(range(1, 25)), help_text="Input channel (1-24)"),
                Parameter("output_channel", str, required=False, default="LR", choices=["L", "R", "LR"], help_text="Output channel selector"),
                Parameter("input_channel", str, required=False, default="LR", choices=["L", "R", "LR"], help_text="Input channel selector"),
            ],
            handler=lambda **kwargs: build_route_command(
                output=kwargs["output"],
                input_ch=kwargs["input"],
                output_channel=kwargs.get("output_channel", "LR"),
                input_channel=kwargs.get("input_channel", "LR"),
            ),
        )
    )

    # Preset commands
    registry.register(
        Command(
            name="preset_save",
            description="Save current config to preset",
            parameters=[
                Parameter("preset", int, required=True, choices=list(range(1, 9)), help_text="Preset number (1-8)"),
            ],
            handler=lambda **kwargs: build_preset_save_command(**kwargs),
        )
    )

    registry.register(
        Command(
            name="preset_recall",
            description="Recall preset config to current setting",
            parameters=[
                Parameter("preset", int, required=True, choices=list(range(1, 9)), help_text="Preset number (1-8)"),
            ],
            handler=lambda **kwargs: build_preset_recall_command(**kwargs),
        )
    )

    # Input gain
    registry.register(
        Command(
            name="input_gain",
            description="Set input gain",
            parameters=[
                Parameter("input", int, required=True, choices=list(range(17)), help_text="Input channel (0-16, 0=All)"),
                Parameter("gain", Any, required=True, help_text="Gain value (0-100 for percent, -76 to +24 for dB, or +/- for relative)", supports_relative=True),
                Parameter("channel", str, required=False, default="LR", choices=["L", "R", "LR"], help_text="Channel to adjust"),
                Parameter("unit", str, required=False, default=None, choices=["percent", "dB"], help_text="Gain unit (None for percent)", depends_on=Dependency(on="gain", when=_is_relative_adjustment)),
            ],
            handler=lambda **kwargs: build_input_gain_command(
                input_ch=kwargs["input"],
                gain=kwargs["gain"],
                channel=kwargs.get("channel", "LR"),
                unit=kwargs.get("unit"),
            ),
        )
    )

    # Input mute
    registry.register(
        Command(
            name="input_mute",
            description="Set input mute on or off",
            parameters=[
                Parameter("input", int, required=True, choices=list(range(17)), help_text="Input channel (0-16, 0=All)"),
                Parameter("mute", bool, required=True, help_text="True to mute, False to unmute"),
                Parameter("channel", str, required=False, default="LR", choices=["L", "R", "LR"], help_text="Channel to adjust"),
            ],
            handler=lambda **kwargs: build_input_mute_command(
                input_ch=kwargs["input"],
                mute=kwargs["mute"],
                channel=kwargs.get("channel", "LR"),
            ),
        )
    )

    # Preset delete
    registry.register(
        Command(
            name="preset_delete",
            description="Delete preset from system",
            parameters=[
                Parameter("preset", int, required=True, choices=list(range(1, 9)), help_text="Preset number (1-8)"),
            ],
            handler=lambda **kwargs: build_preset_delete_command(**kwargs),
            requires_confirmation=True,
            confirmation_message=lambda kwargs: f"Delete preset {kwargs['preset']}?",
        )
    )

    # Preset status
    registry.register(
        Command(
            name="preset_status",
            description="Get preset configuration status",
            parameters=[
                Parameter("preset", int, required=True, choices=list(range(1, 9)), help_text="Preset number (1-8)"),
            ],
            handler=lambda **kwargs: build_preset_status_command(**kwargs),
            return_type=PresetStatus,
            format_result=format_preset_status,
        )
    )

    # Output remove
    registry.register(
        Command(
            name="output_remove",
            description="Remove input from output",
            parameters=[
                Parameter("output", int, required=True, choices=list(range(9)), help_text="Output channel (0-8, 0=All)"),
                Parameter("input", int, required=True, choices=list(range(1, 25)), help_text="Input channel (1-24)"),
                Parameter("output_channel", str, required=False, default="LR", choices=["L", "R", "LR"], help_text="Output channel selector"),
                Parameter("input_channel", str, required=False, default="LR", choices=["L", "R", "LR"], help_text="Input channel selector"),
            ],
            handler=lambda **kwargs: build_output_remove_command(
                output=kwargs["output"],
                input_ch=kwargs["input"],
                output_channel=kwargs.get("output_channel", "LR"),
                input_channel=kwargs.get("input_channel", "LR"),
            ),
            requires_confirmation=True,
            confirmation_message=lambda kwargs: f"Remove input {kwargs['input']} from output {kwargs['output']}?",
        )
    )

    # Output delay
    registry.register(
        Command(
            name="output_delay",
            description="Set output delay time",
            parameters=[
                Parameter("output", int, required=True, choices=list(range(9)), help_text="Output channel (0-8, 0=All)"),
                Parameter(
                    "delay_ms",
                    int,
                    required=True,
                    help_text="Delay time in milliseconds (0-500)",
                    validation=lambda v: (
                        f"Delay must be between 0-500 milliseconds, got {v}"
                        if not isinstance(v, int) or v < 0 or v > 500
                        else None
                    ),
                ),
                Parameter("channel", str, required=False, default="LR", choices=["L", "R", "LR"], help_text="Channel to adjust"),
            ],
            handler=lambda **kwargs: build_output_delay_command(**kwargs),
        )
    )

    # Output mix
    registry.register(
        Command(
            name="output_mix",
            description="Set output mixing mode",
            parameters=[
                Parameter("output", int, required=True, choices=list(range(9)), help_text="Output channel (0-8, 0=All)"),
                Parameter("mode", int, required=True, choices=list(range(7)), help_text="Mix mode (0=None, 1=Swap, 2=Mono L+R, 3=Mono All L, 4=Mono All R, 5=Mono L-R, 6=Mono R-L)"),
            ],
            handler=lambda **kwargs: build_output_mix_command(**kwargs),
        )
    )

    # Output master volume
    registry.register(
        Command(
            name="output_master_volume",
            description="Set output master volume",
            parameters=[
                Parameter("level", Any, required=True, help_text="Volume level (0-100 for percent, -76 to +24 for dB, or +/- for relative)", supports_relative=True),
                Parameter("unit", str, required=False, default="percent", choices=["percent", "dB"], help_text="Volume unit", depends_on=Dependency(on="level", when=_is_relative_adjustment)),
                Parameter("channel", str, required=False, default="LR", choices=["L", "R", "LR"], help_text="Channel to adjust"),
            ],
            handler=lambda **kwargs: build_output_master_volume_command(**kwargs),
        )
    )

    # Output master mute
    registry.register(
        Command(
            name="output_master_mute",
            description="Set output master mute on or off",
            parameters=[
                Parameter("mute", bool, required=True, help_text="True to mute, False to unmute"),
                Parameter("channel", str, required=False, default="LR", choices=["L", "R", "LR"], help_text="Channel to adjust"),
            ],
            handler=lambda **kwargs: build_output_master_mute_command(**kwargs),
        )
    )

    # Output channel lock
    registry.register(
        Command(
            name="output_channel_lock",
            description="Set output channel lock on or off",
            parameters=[
                Parameter("output", int, required=True, choices=list(range(9)), help_text="Output channel (0-8, 0=All)"),
                Parameter("lock", bool, required=True, help_text="True to lock, False to unlock"),
                Parameter("channel", str, required=False, default="LR", choices=["L", "R", "LR"], help_text="Channel to adjust"),
            ],
            handler=lambda **kwargs: build_output_channel_lock_command(**kwargs),
        )
    )

    # Uptime
    registry.register(
        Command(
            name="uptime",
            description="Get system uptime",
            parameters=[],
            handler=lambda **kwargs: build_uptime_command(),
            return_type=str,
        )
    )

    # Temperature
    registry.register(
        Command(
            name="temp",
            description="Get system temperature",
            parameters=[],
            handler=lambda **kwargs: build_temp_command(),
            return_type=str,
        )
    )

    # Reboot
    registry.register(
        Command(
            name="reboot",
            description="Reboot system",
            parameters=[],
            handler=lambda **kwargs: build_reboot_command(),
            requires_confirmation=True,
            confirmation_message="Reboot the device?",
        )
    )

    # Group volume
    registry.register(
        Command(
            name="group_volume",
            description="Set group volume",
            parameters=[
                Parameter("group", int, required=True, choices=list(range(5)), help_text="Group number (0-4, 0=All)"),
                Parameter("level", Any, required=True, help_text="Volume level (0-100 for percent, -76 to +24 for dB, or +/- for relative)", supports_relative=True),
                Parameter("unit", str, required=False, default="percent", choices=["percent", "dB"], help_text="Volume unit", depends_on=Dependency(on="level", when=_is_relative_adjustment)),
                Parameter("channel", str, required=False, default="LR", choices=["L", "R", "LR"], help_text="Channel to adjust"),
            ],
            handler=lambda **kwargs: build_group_volume_command(**kwargs),
        )
    )

    # Group mute
    registry.register(
        Command(
            name="group_mute",
            description="Set group mute on or off",
            parameters=[
                Parameter("group", int, required=True, choices=list(range(5)), help_text="Group number (0-4, 0=All)"),
                Parameter("mute", bool, required=True, help_text="True to mute, False to unmute"),
                Parameter("channel", str, required=False, default="LR", choices=["L", "R", "LR"], help_text="Channel to adjust"),
            ],
            handler=lambda **kwargs: build_group_mute_command(**kwargs),
        )
    )

