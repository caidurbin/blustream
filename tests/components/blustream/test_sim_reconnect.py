"""The integration against the simulated DMP168, not a mocked device."""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import ConfigEntryState  # noqa: E402
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.blustream.const import DOMAIN  # noqa: E402
from tests.sim import SimulatedMatrix  # noqa: E402

MAC = "34:d0:b8:21:22:33"


@pytest.mark.xfail(
    strict=True,
    reason="B2: after the device drops the link the coordinator keeps "
    "polling the dead socket and never reconnects",
)
async def test_coordinator_reconnects_after_link_drop(
    hass: HomeAssistant, socket_enabled: None
) -> None:
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
            coordinator = entry.runtime_data

            await sim.drop_connections()
            await coordinator.async_refresh()
            assert coordinator.last_update_success is False

            # The simulator is still listening, so the next poll can reconnect.
            await coordinator.async_refresh()
            assert coordinator.last_update_success
        finally:
            await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()
