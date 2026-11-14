"""The reboot button against the simulated DMP168, not a mocked device (#78)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import timedelta

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
from homeassistant.exceptions import HomeAssistantError  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from blustream.devices.dmp168 import device as device_module  # noqa: E402
from custom_components.blustream.const import DOMAIN  # noqa: E402
from custom_components.blustream.coordinator import BlustreamCoordinator  # noqa: E402
from tests.sim import SimulatedMatrix  # noqa: E402

MAC = "34:d0:b8:21:22:33"


@pytest.fixture
async def sim_setup(
    hass: HomeAssistant, socket_enabled: None, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[tuple[SimulatedMatrix, BlustreamCoordinator]]:
    """A loaded config entry on the simulator's telnet port.

    The telnet port sends a banner, so a reconnect after the restart does
    not wait out the banner timeout as it would on the raw port.
    """
    monkeypatch.setattr(device_module, "REBOOT_POLL_INTERVAL", 0.01)
    async with SimulatedMatrix() as sim:
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: sim.host, CONF_PORT: sim.telnet_port, CONF_MAC: MAC},
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


def _entity_id(hass: HomeAssistant, domain: str, suffix: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        domain, DOMAIN, f"{MAC}_{suffix}"
    )
    assert entity_id is not None
    return entity_id


async def _press(hass: HomeAssistant) -> None:
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": _entity_id(hass, "button", "reboot")},
        blocking=True,
    )


async def test_ignored_reboot_fails_and_entities_stay_available(
    hass: HomeAssistant,
    sim_setup: tuple[SimulatedMatrix, BlustreamCoordinator],
) -> None:
    sim, coordinator = sim_setup

    with pytest.raises(HomeAssistantError) as exc_info:
        await _press(hass)

    assert exc_info.value.translation_key == "reboot_not_restarted"
    assert sim.received[-3:] == ["UPTIME", "REBOOT", "UPTIME"]
    assert coordinator.last_update_success
    await hass.async_block_till_done()
    assert hass.states.get(_entity_id(hass, "button", "reboot")).state != (
        STATE_UNAVAILABLE
    )
    # The device is still up, so the next poll succeeds too.
    await coordinator.async_refresh()
    assert coordinator.last_update_success


async def test_confirmed_restart_recovers_the_entities(
    hass: HomeAssistant,
    sim_setup: tuple[SimulatedMatrix, BlustreamCoordinator],
) -> None:
    sim, coordinator = sim_setup
    button = _entity_id(hass, "button", "reboot")
    sim.restart_on_reboot(downtime=0.5)

    press = asyncio.create_task(_press(hass))
    while "REBOOT" not in sim.received:
        await asyncio.sleep(0.01)
    await asyncio.sleep(0.05)

    # A poll while the device restarts fails, and the entities grey out.
    # The state is read at once: async_block_till_done() would wait for the
    # press to finish.
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False
    assert hass.states.get(button).state == STATE_UNAVAILABLE

    await press
    await hass.async_block_till_done()

    assert coordinator.last_update_success
    assert hass.states.get(button).state != STATE_UNAVAILABLE
    assert await coordinator.device.get_uptime() < timedelta(seconds=5)
