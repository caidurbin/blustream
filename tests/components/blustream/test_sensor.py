"""Tests for the uptime sensor entity."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.const import (  # noqa: E402
    CONF_HOST,
    CONF_MAC,
    CONF_PORT,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.helpers import (  # noqa: E402
    device_registry as dr,
)
from homeassistant.helpers import (  # noqa: E402
    entity_registry as er,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.blustream.const import DOMAIN  # noqa: E402

from . import make_status  # noqa: E402

ENTRY_DATA = {
    CONF_HOST: "192.0.2.10",
    CONF_PORT: 23,
    CONF_MAC: "34:d0:b8:21:22:33",
}


def _setup_device(uptime_value=timedelta(days=3, hours=2, minutes=1)):
    device = MagicMock()
    device.connect = AsyncMock()
    device.disconnect = AsyncMock()
    device.is_connected = True
    device.get_status = AsyncMock(return_value=make_status(uptime=uptime_value))
    return device


async def _install(hass: HomeAssistant, device) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, data=ENTRY_DATA, unique_id="34:d0:b8:21:22:33"
    )
    entry.add_to_hass(hass)
    with patch("custom_components.blustream.DMP168", return_value=device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_sensor_state_is_a_datetime_close_to_now_minus_uptime(
    hass: HomeAssistant,
) -> None:
    uptime = timedelta(days=3, hours=2, minutes=1)
    device = _setup_device(uptime_value=uptime)
    await _install(hass, device)

    states = [
        state for state in hass.states.async_all() if state.domain == "sensor"
    ]
    assert len(states) == 1
    state = states[0]
    assert state.state not in (STATE_UNAVAILABLE, "unknown")

    boot_time = datetime.fromisoformat(state.state)
    if boot_time.tzinfo is None:
        boot_time = boot_time.replace(tzinfo=timezone.utc)
    delta_seconds = abs(
        (datetime.now(timezone.utc) - uptime - boot_time).total_seconds()
    )
    assert delta_seconds < 10


async def test_sensor_unavailable_when_coordinator_data_unavailable(
    hass: HomeAssistant,
) -> None:
    device = _setup_device()
    entry = await _install(hass, device)

    device.get_status.side_effect = Exception("nope, but caught upstream")

    states = [
        state for state in hass.states.async_all() if state.domain == "sensor"
    ]
    assert len(states) == 1
    entity_id = states[0].entity_id

    coordinator = entry.runtime_data
    coordinator.last_update_success = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_sensor_registers_device_and_entity(
    hass: HomeAssistant,
) -> None:
    device = _setup_device()
    entry = await _install(hass, device)

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert len(devices) == 1
    assert devices[0].manufacturer == "Blustream"
    assert devices[0].model == "DMP168"
    assert (DOMAIN, "34:d0:b8:21:22:33") in devices[0].identifiers
    assert (
        dr.CONNECTION_NETWORK_MAC,
        "34:d0:b8:21:22:33",
    ) in devices[0].connections

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    sensor_entries = [e for e in entries if e.domain == "sensor"]
    assert len(sensor_entries) == 1
    assert sensor_entries[0].unique_id == "34:d0:b8:21:22:33_uptime"
    assert sensor_entries[0].device_class is None
