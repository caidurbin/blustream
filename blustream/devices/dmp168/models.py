"""Data models for DMP168 device."""

from dataclasses import dataclass
from typing import Any, Optional


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
    inputs: list[InputSettings]  # Input settings
    routing: list[OutputRouting]  # Output routing

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the primitives dict used by the CLI ``--json`` surface.

        This is the single source of the hand-built JSON shape that
        :func:`blustream.devices.dmp168.formatters.format_status` emits. Built
        by hand rather than via :func:`dataclasses.asdict` so the serialized
        shape stays pinned to the Lua-parity contract instead of tracking the
        dataclass field layout (ADR 0011).
        """
        return {
            "power": self.power,
            "baud": self.baud,
            "level_unit": self.level_unit,
            "auto_standby_time": self.auto_standby_time,
            "dsp_usage": self.dsp_usage,
            "fade": self.fade,
            "temperature": self.temperature,
            "uptime": self.uptime,
            "firmware_version": self.firmware_version,
            "inputs": [
                {
                    "port": inp.port,
                    "lock": inp.lock,
                    "gain_l": inp.gain_l,
                    "gain_r": inp.gain_r,
                    "mute_l": inp.mute_l,
                    "mute_r": inp.mute_r,
                }
                for inp in self.inputs
            ],
            "routing": [
                {
                    "output": r.output,
                    "channel": r.channel,
                    "from_input": r.from_input,
                }
                for r in self.routing
            ],
        }


@dataclass
class PresetStatus:
    """Preset configuration status."""

    preset_number: int
    exists: bool
    description: Optional[str] = None

