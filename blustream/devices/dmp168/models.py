"""Data models for DMP168 device."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class InputSettings:
    """Input channel settings."""

    port: int
    lock: bool  # True if L/R channels locked
    gain_l: int  # Gain left channel (0-100 or dB)
    gain_r: int  # Gain right channel (0-100 or dB)
    mute_l: bool  # Mute left channel
    mute_r: bool  # Mute right channel


@dataclass
class OutputRouting:
    """Output routing configuration."""

    output: int
    channel: str  # "L" or "R"
    from_input: Optional[int] = None  # Input number, None if not routed


@dataclass
class SystemStatus:
    """DMP168 system status."""

    power: str  # "On" or "Off(Standby)"
    baud: int  # Baud rate
    level_unit: str  # "dB" or "%"
    auto_standby_time: int  # Minutes, 0 if disabled
    dsp_usage: float  # DSP utilization percentage
    fade: bool  # Volume change fade on/off
    temperature: float  # Temperature in Celsius
    uptime: str  # Uptime string (DDDD:HH:MM:SS)
    firmware_version: str  # Firmware version
    inputs: List[InputSettings]  # Input settings
    routing: List[OutputRouting]  # Output routing


@dataclass
class PresetStatus:
    """Preset configuration status."""

    preset_number: int
    exists: bool
    description: Optional[str] = None

