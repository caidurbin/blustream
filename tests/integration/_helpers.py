"""Shared assertion helpers for the live-device integration suite."""

from __future__ import annotations

from blustream.devices.dmp168.models import OutputRouting, SystemStatus


def output_l_input(status: SystemStatus, output: int) -> int | None:
    """Return the input currently routed to ``output``'s L channel, or None.

    The driver treats the L row as canonical for the channel-locked proxy
    (see ``polling_coordinator.lua``); test assertions follow the same
    convention so they stay comparable across Python and Lua surfaces.
    """
    for row in status.routing:
        if (
            isinstance(row, OutputRouting)
            and row.output == output
            and row.channel == "L"
        ):
            return row.from_input
    return None
