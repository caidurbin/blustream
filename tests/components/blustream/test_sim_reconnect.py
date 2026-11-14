"""The integration against the simulated DMP168, not a mocked device."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import ConfigEntryState  # noqa: E402
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.blustream.const import DOMAIN  # noqa: E402
from custom_components.blustream.coordinator import BlustreamCoordinator  # noqa: E402
from tests.sim import SimulatedMatrix  # noqa: E402

MAC = "34:d0:b8:21:22:33"


@pytest.fixture
async def sim_setup(
    hass: HomeAssistant, socket_enabled: None
) -> AsyncGenerator[tuple[SimulatedMatrix, BlustreamCoordinator]]:
    """A loaded config entry polling the simulator; yields (sim, coordinator)."""
    async with SimulatedMatrix() as sim:
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: sim.host, CONF_PORT: sim.raw_port, CONF_MAC: MAC},
            unique_id=MAC,
        )
        entry.add_to_hass(hass)
        try:
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
            assert entry.state is ConfigEntryState.LOADED
            yield sim, entry.runtime_data
        finally:
            await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()


async def test_coordinator_reconnects_after_link_drop(
    sim_setup: tuple[SimulatedMatrix, BlustreamCoordinator],
) -> None:
    sim, coordinator = sim_setup

    await sim.drop_connections()
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False

    # The simulator is still listening, so the next poll can reconnect.
    await coordinator.async_refresh()
    assert coordinator.last_update_success


async def test_coordinator_recovers_once_unreachable_device_is_back(
    sim_setup: tuple[SimulatedMatrix, BlustreamCoordinator],
) -> None:
    sim, coordinator = sim_setup

    # The device drops the link and stops listening: the poll that finds the
    # dead link fails, and so does the reconnect after it.
    await sim.stop()
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False

    # The device is back on the same port.
    await sim.start()
    await coordinator.async_refresh()
    assert coordinator.last_update_success
