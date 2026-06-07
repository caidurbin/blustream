"""Shared assertion helpers for the live-device integration suite."""

from __future__ import annotations

from blustream.devices.dmp168.models import SOURCE_INPUT, OutputRouting, SystemStatus


def output_l_input(status: SystemStatus, output: int) -> int | None:
    """Return the input currently routed to ``output``'s L channel, or None.

    The driver treats the L row as canonical for the channel-locked proxy
    (see ``polling_coordinator.lua``); test assertions follow the same
    convention so they stay comparable across Python and Lua surfaces. Only
    input sources resolve to a number; a bus-routed or unrouted output is
    reported as ``None`` (these routing round-trips only exercise inputs).
    """
    for row in status.routing:
        if (
            isinstance(row, OutputRouting)
            and row.output == output
            and row.channel == "L"
        ):
            if row.source is not None and row.source.kind == SOURCE_INPUT:
                return row.source.number
            return None
    return None
