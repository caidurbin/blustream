"""Concurrent multi-client TCP regression.

The PRD's load-bearing assumption (#9) is that the DMP168 supports
concurrent TCP clients so the Control4 driver, the Python CLI, the matrix
web GUI, and a future Home Assistant integration can coexist. This test
re-verifies that assumption against the live device by opening N parallel
clients, issuing STATUS on each concurrently, and confirming all responses
parse cleanly.

A regression here would invalidate the multi-client design choice
captured in ``docs/control4-driver-plan.md``.
"""

from __future__ import annotations

import asyncio

import pytest

from blustream.devices.dmp168.device import DMP168
from blustream.devices.dmp168.models import SystemStatus

CONCURRENT_CLIENTS = 4


@pytest.mark.asyncio
async def test_multiple_clients_can_query_status_concurrently(
    host: str, port: int
) -> None:
    devices = [DMP168(host=host, port=port) for _ in range(CONCURRENT_CLIENTS)]
    try:
        await asyncio.gather(*(d.connect() for d in devices))

        statuses = await asyncio.gather(
            *(d.execute_command("status") for d in devices)
        )

        assert len(statuses) == CONCURRENT_CLIENTS
        for i, status in enumerate(statuses):
            assert isinstance(status, SystemStatus), (
                f"client {i} returned {type(status).__name__}, expected SystemStatus"
            )
            assert status.power in {"On", "Off(Standby)"}, (
                f"client {i} reported unexpected power state: {status.power!r}"
            )
    finally:
        await asyncio.gather(
            *(d.disconnect() for d in devices),
            return_exceptions=True,
        )
