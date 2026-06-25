"""Generated wire-protocol formatters for the dmp168.

DO NOT EDIT. Regenerate with: python -m spec.codegen.emit_python
Source: spec/protocol.yaml
Spec hash: 45fac3c9db9e5834
Device: Blustream dmp168
Firmware baseline: 1.5.0
"""

from blustream.base.exceptions import ValidationError

DEFAULT_PORT = 8000
ALTERNATIVE_PORT = 23
TERMINATOR = '\r\n'


def format_status() -> str:
    """Get system status and port status."""
    return 'STATUS'


def format_uptime() -> str:
    """Get system uptime."""
    return 'UPTIME'


def format_temp() -> str:
    """Get system temperature."""
    return 'TEMP'


def format_help() -> str:
    """Print the device help / command listing."""
    return 'HELP'


def format_power_on() -> str:
    """Power on, system run on normal state."""
    return 'PON'


def format_power_off() -> str:
    """Power off, system run on power save state."""
    return 'POFF'


def format_standby(mode: int) -> str:
    """Set device standby mode (0=Sleep, 1=Standby)."""
    if mode not in [0, 1]:
        raise ValidationError(f"Invalid standby mode '{mode}'. Valid options are: 0 (Sleep) or 1 (Standby). Please choose a valid mode.")
    cmd = ""
    cmd += 'STANDBY '
    cmd += str(mode)
    return cmd


def format_disable_auto_standby() -> str:
    """Disable the auto-standby timer (persists across reboots)."""
    return 'AUTO STB 0'


def format_reboot() -> str:
    """Reboot system."""
    return 'REBOOT'


def format_output_volume(output: int, level, unit: str = 'percent', channel: str = 'LR') -> str:
    """Set output volume."""
    if output < 0 or output > 8:
        raise ValidationError(f"Invalid output channel '{output}'. Output must be between 0-8 (0=All outputs). Please choose a valid output.")
    if channel not in ['L', 'R', 'LR']:
        raise ValidationError(f"Invalid channel '{channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    if unit not in ['percent', 'dB']:
        raise ValidationError(f"Invalid unit '{unit}'. Valid options are: 'percent' or 'dB'. Please choose a valid unit.")
    cmd = ""
    cmd += 'OUT '
    cmd += str(output)
    if channel != 'LR':
        cmd += ' ' + str(channel)
    cmd += ' VOL'
    if channel != 'LR':
        cmd += ' ' + str(channel)
    cmd += ' '
    cmd += str(level)
    if unit == 'dB' and level not in ['+', '-']:
        cmd += ' dB'
    return cmd


def format_output_mute(output: int, mute: bool, channel: str = 'LR') -> str:
    """Set output mute on or off."""
    if output < 0 or output > 8:
        raise ValidationError(f"Invalid output channel '{output}'. Output must be between 0-8 (0=All outputs). Please choose a valid output.")
    if channel not in ['L', 'R', 'LR']:
        raise ValidationError(f"Invalid channel '{channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    cmd = ""
    cmd += 'OUT '
    cmd += str(output)
    if channel != 'LR':
        cmd += ' ' + str(channel)
    cmd += ' MUTE'
    if channel != 'LR':
        cmd += ' ' + str(channel)
    if mute:
        cmd += ' ON'
    if not mute:
        cmd += ' OFF'
    return cmd


def format_output_channel_lock(output: int, lock: bool, channel: str = 'LR') -> str:
    """Set output channel lock on or off."""
    if output < 0 or output > 8:
        raise ValidationError(f"Invalid output channel '{output}'. Output must be between 0-8 (0=All outputs). Please choose a valid output.")
    if channel not in ['L', 'R', 'LR']:
        raise ValidationError(f"Invalid channel '{channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    cmd = ""
    cmd += 'OUT '
    cmd += str(output)
    cmd += ' CH LOCK'
    if channel != 'LR':
        cmd += ' ' + str(channel)
    if lock:
        cmd += ' ON'
    if not lock:
        cmd += ' OFF'
    return cmd


def format_output_delay(output: int, delay_ms: int, channel: str = 'LR') -> str:
    """Set output delay time."""
    if output < 0 or output > 8:
        raise ValidationError(f"Invalid output channel '{output}'. Output must be between 0-8 (0=All outputs). Please choose a valid output.")
    if delay_ms < 0 or delay_ms > 500:
        raise ValidationError(f"Invalid delay value '{delay_ms}'. Delay must be between 0-500 milliseconds. Please choose a valid delay.")
    if channel not in ['L', 'R', 'LR']:
        raise ValidationError(f"Invalid channel '{channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    cmd = ""
    cmd += 'OUT '
    cmd += str(output)
    if channel != 'LR':
        cmd += ' ' + str(channel)
    cmd += ' DELAY '
    cmd += str(delay_ms)
    return cmd


def format_output_mix(output: int, mode: int) -> str:
    """Set output mixing mode."""
    if output < 0 or output > 8:
        raise ValidationError(f"Invalid output channel '{output}'. Output must be between 0-8 (0=All outputs). Please choose a valid output.")
    if mode < 0 or mode > 6:
        raise ValidationError(f"Invalid mix mode '{mode}'. Mix mode must be between 0-6. Please choose a valid mode.")
    cmd = ""
    cmd += 'OUT '
    cmd += str(output)
    cmd += ' MIX '
    cmd += str(mode)
    return cmd


def format_output_master_volume(level, unit: str = 'percent', channel: str = 'LR') -> str:
    """Set output master volume."""
    if channel not in ['L', 'R', 'LR']:
        raise ValidationError(f"Invalid channel '{channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    if unit not in ['percent', 'dB']:
        raise ValidationError(f"Invalid unit '{unit}'. Valid options are: 'percent' or 'dB'. Please choose a valid unit.")
    cmd = ""
    cmd += 'OUT MASTER VOL'
    if channel != 'LR':
        cmd += ' ' + str(channel)
    cmd += ' '
    cmd += str(level)
    if unit == 'dB' and level not in ['+', '-']:
        cmd += ' dB'
    return cmd


def format_output_master_mute(mute: bool, channel: str = 'LR') -> str:
    """Set output master mute on or off."""
    if channel not in ['L', 'R', 'LR']:
        raise ValidationError(f"Invalid channel '{channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    cmd = ""
    cmd += 'OUT MASTER MUTE'
    if channel != 'LR':
        cmd += ' ' + str(channel)
    if mute:
        cmd += ' ON'
    if not mute:
        cmd += ' OFF'
    return cmd


def format_route(output: int, input_ch: int, output_channel: str = 'LR', input_channel: str = 'LR') -> str:
    """Route input to output."""
    if output < 0 or output > 8:
        raise ValidationError(f"Invalid output channel '{output}'. Output must be between 0-8 (0=All outputs). Please choose a valid output.")
    if input_ch < 1 or input_ch > 24:
        raise ValidationError(f"Invalid input channel '{input_ch}'. Input must be between 1-24. Please choose a valid input.")
    if output_channel not in ['L', 'R', 'LR']:
        raise ValidationError(f"Invalid output channel '{output_channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    if input_channel not in ['L', 'R', 'LR']:
        raise ValidationError(f"Invalid input channel '{input_channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    cmd = ""
    cmd += 'OUT '
    cmd += str(output)
    if output_channel != 'LR':
        cmd += ' ' + str(output_channel)
    cmd += ' FR '
    cmd += str(input_ch)
    if input_channel != 'LR':
        cmd += ' ' + str(input_channel)
    return cmd


def format_output_remove(output: int, input_ch: int, output_channel: str = 'LR', input_channel: str = 'LR') -> str:
    """Remove input from output."""
    if output < 0 or output > 8:
        raise ValidationError(f"Invalid output channel '{output}'. Output must be between 0-8 (0=All outputs). Please choose a valid output.")
    if input_ch < 1 or input_ch > 24:
        raise ValidationError(f"Invalid input channel '{input_ch}'. Input must be between 1-24. Please choose a valid input.")
    if output_channel not in ['L', 'R', 'LR']:
        raise ValidationError(f"Invalid output channel '{output_channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    if input_channel not in ['L', 'R', 'LR']:
        raise ValidationError(f"Invalid input channel '{input_channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    cmd = ""
    cmd += 'OUT '
    cmd += str(output)
    if output_channel != 'LR':
        cmd += ' ' + str(output_channel)
    cmd += ' REM '
    cmd += str(input_ch)
    if input_channel != 'LR':
        cmd += ' ' + str(input_channel)
    return cmd


def format_input_gain(input_ch: int, gain, channel: str = 'LR', unit: str = None) -> str:
    """Set input gain."""
    if input_ch < 0 or input_ch > 16:
        raise ValidationError(f"Invalid input channel '{input_ch}'. Input must be between 0-16 (0=All inputs). Please choose a valid input.")
    if channel not in ['L', 'R', 'LR']:
        raise ValidationError(f"Invalid channel '{channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    cmd = ""
    cmd += 'IN '
    cmd += str(input_ch)
    if channel != 'LR':
        cmd += ' ' + str(channel)
    cmd += ' GAIN'
    cmd += ' '
    cmd += str(gain)
    if unit == 'dB' and gain not in ['+', '-']:
        cmd += ' dB'
    return cmd


def format_input_mute(input_ch: int, mute: bool, channel: str = 'LR') -> str:
    """Set input mute on or off."""
    if input_ch < 0 or input_ch > 16:
        raise ValidationError(f"Invalid input channel '{input_ch}'. Input must be between 0-16 (0=All inputs). Please choose a valid input.")
    if channel not in ['L', 'R', 'LR']:
        raise ValidationError(f"Invalid channel '{channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    cmd = ""
    cmd += 'IN '
    cmd += str(input_ch)
    if channel != 'LR':
        cmd += ' ' + str(channel)
    cmd += ' MUTE'
    if channel != 'LR':
        cmd += ' ' + str(channel)
    if mute:
        cmd += ' ON'
    if not mute:
        cmd += ' OFF'
    return cmd


def format_preset_save(preset: int) -> str:
    """Save current config to preset."""
    if preset < 1 or preset > 8:
        raise ValidationError(f"Invalid preset number '{preset}'. Preset must be between 1-8. Please choose a valid preset.")
    cmd = ""
    cmd += 'PRESET '
    cmd += str(preset)
    cmd += ' SAVE'
    return cmd


def format_preset_recall(preset: int) -> str:
    """Recall preset config to current setting."""
    if preset < 1 or preset > 8:
        raise ValidationError(f"Invalid preset number '{preset}'. Preset must be between 1-8. Please choose a valid preset.")
    cmd = ""
    cmd += 'PRESET '
    cmd += str(preset)
    cmd += ' APPLY'
    return cmd


def format_preset_delete(preset: int) -> str:
    """Delete preset from system."""
    if preset < 1 or preset > 8:
        raise ValidationError(f"Invalid preset number '{preset}'. Preset must be between 1-8. Please choose a valid preset.")
    cmd = ""
    cmd += 'PRESET '
    cmd += str(preset)
    cmd += ' DELETE'
    return cmd


def format_preset_status(preset: int) -> str:
    """Get preset configuration status."""
    if preset < 1 or preset > 8:
        raise ValidationError(f"Invalid preset number '{preset}'. Preset must be between 1-8. Please choose a valid preset.")
    cmd = ""
    cmd += 'PRESET '
    cmd += str(preset)
    cmd += ' STATUS'
    return cmd


def format_group_volume(group: int, level, unit: str = 'percent', channel: str = 'LR') -> str:
    """Set group volume."""
    if group < 0 or group > 4:
        raise ValidationError(f"Invalid group number '{group}'. Group must be between 0-4 (0=All groups). Please choose a valid group.")
    if channel not in ['L', 'R', 'LR']:
        raise ValidationError(f"Invalid channel '{channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    if unit not in ['percent', 'dB']:
        raise ValidationError(f"Invalid unit '{unit}'. Valid options are: 'percent' or 'dB'. Please choose a valid unit.")
    cmd = ""
    cmd += 'GROUP '
    cmd += str(group)
    cmd += ' VOL'
    if channel != 'LR':
        cmd += ' ' + str(channel)
    cmd += ' '
    cmd += str(level)
    if unit == 'dB' and level not in ['+', '-']:
        cmd += ' dB'
    return cmd


def format_group_mute(group: int, mute: bool, channel: str = 'LR') -> str:
    """Set group mute on or off."""
    if group < 0 or group > 4:
        raise ValidationError(f"Invalid group number '{group}'. Group must be between 0-4 (0=All groups). Please choose a valid group.")
    if channel not in ['L', 'R', 'LR']:
        raise ValidationError(f"Invalid channel '{channel}'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    cmd = ""
    cmd += 'GROUP '
    cmd += str(group)
    cmd += ' MUTE'
    if channel != 'LR':
        cmd += ' ' + str(channel)
    if mute:
        cmd += ' ON'
    if not mute:
        cmd += ' OFF'
    return cmd
