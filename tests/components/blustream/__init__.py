"""Tests for the Blustream Home Assistant integration."""

from __future__ import annotations

from datetime import timedelta

from blustream.devices.dmp168.models import (
    InputSettings,
    OutputRouting,
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
) -> SystemStatus:
    """Build a SystemStatus for the coordinator's ``get_status()`` poll.

    ``routing`` defaults to all 8 outputs unrouted (``source=None``); pass a
    custom list to exercise specific routes.
    """
    if routing is None:
        routing = [
            OutputRouting(output=out, channel=channel, source=None)
            for out in range(1, 9)
            for channel in ("L", "R")
        ]
    return SystemStatus(
        power="On",
        baud=9600,
        level_unit="dB",
        auto_standby_time=0,
        dsp_usage=12.5,
        fade=True,
        temperature=42.0,
        uptime=uptime_to_raw(uptime),
        firmware_version="1.2.3",
        inputs=[
            InputSettings(
                port=1, lock=True, gain_l=50, gain_r=50, mute_l=False, mute_r=False
            )
        ],
        routing=routing,
    )


__all__ = ["OutputSource", "OutputRouting", "make_status", "uptime_to_raw"]
