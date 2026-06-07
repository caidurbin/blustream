"""Tests for the Blustream Home Assistant integration."""

from __future__ import annotations

from datetime import timedelta

from blustream.devices.dmp168.models import (
    InputSettings,
    OutputRouting,
    OutputSettings,
    OutputSource,
    SystemStatus,
)


def uptime_to_raw(value: timedelta) -> str:
    """Render a timedelta as the device's ``DDDD:HH:MM:SS`` uptime string."""
    total = int(value.total_seconds())
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{days:04d}:{hours:02d}:{minutes:02d}:{seconds:02d}"


def make_status(
    *,
    uptime: timedelta = timedelta(days=3, hours=2, minutes=1),
    routing: list[OutputRouting] | None = None,
    output_settings: list[OutputSettings] | None = None,
    power: str = "On",
    dsp_usage: float = 12.5,
    temperature: float = 42.0,
    firmware_version: str = "1.2.3",
) -> SystemStatus:
    """Build a SystemStatus for the coordinator's ``get_status()`` poll.

    ``routing`` defaults to all 8 outputs unrouted (``source=None``); pass a
    custom list to exercise specific routes. ``output_settings`` defaults to
    all 8 outputs at full volume, unmuted, unlocked. ``power`` is the device
    power field (``"On"`` or ``"Off(Standby)"``). ``dsp_usage``,
    ``temperature``, and ``firmware_version`` back the device-health sensors
    (issue #68).
    """
    if routing is None:
        routing = [
            OutputRouting(output=out, channel=channel, source=None)
            for out in range(1, 9)
            for channel in ("L", "R")
        ]
    if output_settings is None:
        output_settings = [
            OutputSettings(
                output=out,
                volume_pct_l=100,
                volume_pct_r=100,
                mute_l=False,
                mute_r=False,
                lock=True,
            )
            for out in range(1, 9)
        ]
    return SystemStatus(
        power=power,
        baud=9600,
        level_unit="dB",
        auto_standby_time=0,
        dsp_usage=dsp_usage,
        fade=True,
        temperature=temperature,
        uptime=uptime_to_raw(uptime),
        firmware_version=firmware_version,
        inputs=[
            InputSettings(
                port=1, lock=True, gain_l=50, gain_r=50, mute_l=False, mute_r=False
            )
        ],
        routing=routing,
        output_settings=output_settings,
    )


__all__ = [
    "OutputRouting",
    "OutputSettings",
    "OutputSource",
    "make_status",
    "uptime_to_raw",
]
