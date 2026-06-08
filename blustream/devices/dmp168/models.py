"""Data models for DMP168 device."""

from dataclasses import dataclass, field
from typing import Any, Optional

# Source kind discriminants. The DMP168 addresses inputs and buses through a
# single 1-24 column space on the wire (1-16 = inputs, 17-24 = buses); that
# encoding stays inside the library (ADR 0011), so callers see a typed
# (kind, number) pair instead.
SOURCE_INPUT = "input"
SOURCE_BUS = "bus"

# Buses occupy columns 17-24 in the device's unified routing addressing.
_BUS_COLUMN_OFFSET = 16


@dataclass(frozen=True)
class OutputSource:
    """A signal source that can feed an output: one input or one bus.

    ``kind`` is :data:`SOURCE_INPUT` (number 1-16) or :data:`SOURCE_BUS`
    (number 1-8). ``None`` is *not* an ``OutputSource`` — an unrouted output
    is modelled as ``OutputRouting.source is None`` (the device's own "None"
    routing target; see CONTEXT.md "Source").
    """

    kind: str
    number: int

    def __post_init__(self) -> None:
        if self.kind not in (SOURCE_INPUT, SOURCE_BUS):
            raise ValueError(
                f"Invalid source kind '{self.kind}'. "
                f"Expected '{SOURCE_INPUT}' or '{SOURCE_BUS}'."
            )

    @classmethod
    def for_input(cls, number: int) -> "OutputSource":
        """Build an input source (input ``number``, 1-16)."""
        return cls(kind=SOURCE_INPUT, number=number)

    @classmethod
    def for_bus(cls, number: int) -> "OutputSource":
        """Build a bus source (bus ``number``, 1-8)."""
        return cls(kind=SOURCE_BUS, number=number)

    @property
    def column(self) -> int:
        """The unified 1-24 column address used by the wire route command."""
        if self.kind == SOURCE_BUS:
            return _BUS_COLUMN_OFFSET + self.number
        return self.number


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
    """Output routing configuration for one output channel.

    ``source`` is the single source feeding this output channel, or ``None``
    when the output is unrouted (the device reports ``Out1 L  None``). Per
    ADR 0014 each output is single-source.
    """

    output: int
    channel: str  # "L" or "R"
    source: Optional[OutputSource] = None


@dataclass
class OutputSettings:
    """Per-output settings parsed from the ``Output Settings Status`` section."""

    output: int
    volume_pct_l: int  # Output volume left channel (%)
    volume_pct_r: int  # Output volume right channel (%)
    mute_l: bool  # Mute left channel
    mute_r: bool  # Mute right channel
    lock: bool  # True if L/R channels locked


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
    output_settings: list[OutputSettings] = field(default_factory=list)

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
                    "source": (
                        {"kind": r.source.kind, "number": r.source.number}
                        if r.source is not None
                        else None
                    ),
                }
                for r in self.routing
            ],
            "output_settings": [
                {
                    "output": o.output,
                    "volume_pct_l": o.volume_pct_l,
                    "volume_pct_r": o.volume_pct_r,
                    "mute_l": o.mute_l,
                    "mute_r": o.mute_r,
                    "lock": o.lock,
                }
                for o in self.output_settings
            ],
        }


@dataclass
class PresetStatus:
    """Preset configuration status."""

    preset_number: int
    exists: bool
    description: Optional[str] = None
