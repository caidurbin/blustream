"""Tests for the device power switch entity (issue #66)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.const import (  # noqa: E402
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.blustream.const import DOMAIN  # noqa: E402

from . import make_status  # noqa: E402

MAC = "34:d0:b8:21:22:33"
ENTRY_DATA = {
    CONF_HOST: "192.0.2.10",
    CONF_PORT: 23,
    CONF_NAME: "Test DMP168",
    CONF_MAC: MAC,
}


def _setup_device(power: str = "On") -> MagicMock:
    device = MagicMock()
    device.connect = AsyncMock()
    device.disconnect = AsyncMock()
    device.is_connected = True
    device.get_status = AsyncMock(return_value=make_status(power=power))
    device.power_on = AsyncMock()
    device.power_off = AsyncMock()
    return device


async def _install(hass: HomeAssistant, device: MagicMock) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, unique_id=MAC)
    entry.add_to_hass(hass)
    with patch("custom_components.blustream.DMP168", return_value=device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def _entity_id(hass: HomeAssistant) -> str:
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("switch", DOMAIN, f"{MAC}_power")
    assert entity_id is not None
    return entity_id


async def test_switch_on_when_power_on(hass: HomeAssistant) -> None:
    device = _setup_device(power="On")
    await _install(hass, device)
    assert hass.states.get(_entity_id(hass)).state == STATE_ON


async def test_switch_off_when_standby(hass: HomeAssistant) -> None:
    device = _setup_device(power="Off(Standby)")
    await _install(hass, device)
    assert hass.states.get(_entity_id(hass)).state == STATE_OFF


async def test_switch_has_no_device_class_or_entity_category(
    hass: HomeAssistant,
) -> None:
    device = _setup_device()
    entry = await _install(hass, device)
    state = hass.states.get(_entity_id(hass))
    assert state.attributes.get("device_class") is None

    registry = er.async_get(hass)
    rentry = registry.async_get(_entity_id(hass))
    assert rentry.entity_category is None
    assert rentry.config_entry_id == entry.entry_id


async def test_turn_on_calls_power_on(hass: HomeAssistant) -> None:
    device = _setup_device(power="Off(Standby)")
    await _install(hass, device)
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": _entity_id(hass)},
        blocking=True,
    )
    device.power_on.assert_awaited_once_with()


async def test_turn_off_calls_power_off(hass: HomeAssistant) -> None:
    device = _setup_device(power="On")
    await _install(hass, device)
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": _entity_id(hass)},
        blocking=True,
    )
    device.power_off.assert_awaited_once_with()


async def test_switch_unavailable_when_coordinator_fails(
    hass: HomeAssistant,
) -> None:
    device = _setup_device()
    entry = await _install(hass, device)
    entity_id = _entity_id(hass)

    coordinator = entry.runtime_data
    coordinator.last_update_success = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
