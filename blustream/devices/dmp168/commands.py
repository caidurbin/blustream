"""Command registry for the DMP168.

Wire-format builders and parameter validators are generated from
``spec/protocol.yaml`` and live in ``_generated.py``. This module imports
those generated formatters, exposes them under their historical
``build_<name>_command`` aliases for backward compatibility, and registers
each command's metadata (Parameter dataclass instances, registry entries,
confirmation prompts, result formatters) with a ``CommandRegistry`` for the
device class to consume.
"""

from typing import Any

from blustream.base.commands import Command, CommandRegistry, Dependency, Parameter
from blustream.devices.dmp168 import _generated as gen
from blustream.devices.dmp168.formatters import format_preset_status, format_status
from blustream.devices.dmp168.models import PresetStatus, SystemStatus

# ---------- Generated wire-formatter aliases ----------
# Historical names kept as thin re-exports of the generated formatters so
# external callers (and the test suite) continue to work without per-import
# updates after the codegen refactor.

build_status_command = gen.format_status
build_uptime_command = gen.format_uptime
build_temp_command = gen.format_temp
build_power_on_command = gen.format_power_on
build_power_off_command = gen.format_power_off
build_standby_command = gen.format_standby
build_reboot_command = gen.format_reboot
build_output_volume_command = gen.format_output_volume
build_output_mute_command = gen.format_output_mute
build_output_channel_lock_command = gen.format_output_channel_lock
build_output_delay_command = gen.format_output_delay
build_output_mix_command = gen.format_output_mix
build_output_master_volume_command = gen.format_output_master_volume
build_output_master_mute_command = gen.format_output_master_mute
build_input_gain_command = gen.format_input_gain
build_input_mute_command = gen.format_input_mute
build_preset_save_command = gen.format_preset_save
build_preset_recall_command = gen.format_preset_recall
build_preset_delete_command = gen.format_preset_delete
build_preset_status_command = gen.format_preset_status
build_group_volume_command = gen.format_group_volume
build_group_mute_command = gen.format_group_mute
build_route_command = gen.format_route
build_output_remove_command = gen.format_output_remove


def _is_relative_adjustment(value: Any) -> bool:
    return isinstance(value, str) and value in ("+", "-")


def _register_commands(registry: CommandRegistry) -> None:
    """Register all DMP168 commands with metadata."""

    # Status command
    registry.register(
        Command(
            name="status",
            description="Get system status and port status",
            parameters=[],
            handler=lambda **kwargs: gen.format_status(),
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
            handler=lambda **kwargs: gen.format_power_on(),
        )
    )

    registry.register(
        Command(
            name="power_off",
            description="Power off, system run on power save state",
            parameters=[],
            handler=lambda **kwargs: gen.format_power_off(),
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
            handler=lambda **kwargs: gen.format_output_volume(**kwargs),
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
            handler=lambda **kwargs: gen.format_output_mute(**kwargs),
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
            handler=lambda **kwargs: gen.format_route(
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
            handler=lambda **kwargs: gen.format_preset_save(**kwargs),
        )
    )

    registry.register(
        Command(
            name="preset_recall",
            description="Recall preset config to current setting",
            parameters=[
                Parameter("preset", int, required=True, choices=list(range(1, 9)), help_text="Preset number (1-8)"),
            ],
            handler=lambda **kwargs: gen.format_preset_recall(**kwargs),
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
            handler=lambda **kwargs: gen.format_input_gain(
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
            handler=lambda **kwargs: gen.format_input_mute(
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
            handler=lambda **kwargs: gen.format_preset_delete(**kwargs),
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
            handler=lambda **kwargs: gen.format_preset_status(**kwargs),
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
            handler=lambda **kwargs: gen.format_output_remove(
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
            handler=lambda **kwargs: gen.format_output_delay(**kwargs),
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
            handler=lambda **kwargs: gen.format_output_mix(**kwargs),
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
            handler=lambda **kwargs: gen.format_output_master_volume(**kwargs),
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
            handler=lambda **kwargs: gen.format_output_master_mute(**kwargs),
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
            handler=lambda **kwargs: gen.format_output_channel_lock(**kwargs),
        )
    )

    # Uptime
    registry.register(
        Command(
            name="uptime",
            description="Get system uptime",
            parameters=[],
            handler=lambda **kwargs: gen.format_uptime(),
            return_type=str,
        )
    )

    # Temperature
    registry.register(
        Command(
            name="temp",
            description="Get system temperature",
            parameters=[],
            handler=lambda **kwargs: gen.format_temp(),
            return_type=str,
        )
    )

    # Reboot
    registry.register(
        Command(
            name="reboot",
            description="Reboot system",
            parameters=[],
            handler=lambda **kwargs: gen.format_reboot(),
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
            handler=lambda **kwargs: gen.format_group_volume(**kwargs),
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
            handler=lambda **kwargs: gen.format_group_mute(**kwargs),
        )
    )
