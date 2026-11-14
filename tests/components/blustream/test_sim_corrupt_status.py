"""A corrupted STATUS dump from the simulated DMP168 is a failed poll (#110)."""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import ConfigEntryState  # noqa: E402
from homeassistant.const import (  # noqa: E402
    CONF_HOST,
    CONF_MAC,
    CONF_PORT,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.blustream.const import DOMAIN  # noqa: E402
from tests.sim import SimulatedMatrix  # noqa: E402

MAC = "34:d0:b8:21:22:33"


@pytest.mark.parametrize("port", ["telnet", "raw"])
async def test_corrupted_status_fails_the_poll_and_keeps_last_data(
    hass: HomeAssistant, socket_enabled: None, port: str
) -> None:
    async with SimulatedMatrix() as sim:
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: sim.host,
                CONF_PORT: sim.telnet_port if port == "telnet" else sim.raw_port,
                CONF_MAC: MAC,
            },
            unique_id=MAC,
        )
        entry.add_to_hass(hass)
        try:
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
            assert entry.state is ConfigEntryState.LOADED
            coordinator = entry.runtime_data
            last_good = coordinator.data
            entity_ids = hass.states.async_entity_ids()
            assert entity_ids

            sim.corrupt_next_status()
            await coordinator.async_refresh()
            await hass.async_block_till_done()

            assert coordinator.last_update_success is False
            assert coordinator.data is last_good
            assert entry.state is ConfigEntryState.LOADED
            for entity_id in entity_ids:
                assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

            # The next poll gets a clean dump and the entities come back.
            await coordinator.async_refresh()
            await hass.async_block_till_done()

            assert coordinator.last_update_success
            for entity_id in entity_ids:
                assert hass.states.get(entity_id).state != STATE_UNAVAILABLE
        finally:
            await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()
