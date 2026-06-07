"""Tests for the device reboot button (issue #67)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.components.button import ButtonDeviceClass  # noqa: E402
from homeassistant.const import (  # noqa: E402
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    STATE_UNAVAILABLE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.exceptions import HomeAssistantError  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from blustream.base.exceptions import (  # noqa: E402
    ConnectionError as BlustreamConnectionError,
)
from custom_components.blustream.const import DOMAIN  # noqa: E402

from . import make_status  # noqa: E402

MAC = "34:d0:b8:21:22:33"
ENTRY_DATA = {
    CONF_HOST: "192.0.2.10",
    CONF_PORT: 23,
    CONF_NAME: "Test DMP168",
    CONF_MAC: MAC,
}


def _setup_device() -> MagicMock:
    device = MagicMock()
    device.connect = AsyncMock()
    device.disconnect = AsyncMock()
    device.is_connected = True
    device.get_status = AsyncMock(return_value=make_status())
    device.reboot = AsyncMock()
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
    entity_id = registry.async_get_entity_id("button", DOMAIN, f"{MAC}_reboot")
    assert entity_id is not None
    return entity_id


async def _press(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id},
        blocking=True,
    )


async def test_reboot_button_present_with_restart_class_and_config_category(
    hass: HomeAssistant,
) -> None:
    device = _setup_device()
    await _install(hass, device)

    entity_id = _entity_id(hass)
    state = hass.states.get(entity_id)
    assert state.attributes["device_class"] == ButtonDeviceClass.RESTART

    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    assert entry.entity_category == EntityCategory.CONFIG


async def test_press_calls_library_reboot(hass: HomeAssistant) -> None:
    device = _setup_device()
    await _install(hass, device)

    await _press(hass, _entity_id(hass))
    device.reboot.assert_awaited_once_with()


async def test_reboot_failure_raises_translated_error_and_marks_unavailable(
    hass: HomeAssistant,
) -> None:
    device = _setup_device()
    device.reboot = AsyncMock(side_effect=BlustreamConnectionError("dead"))
    entry = await _install(hass, device)
    entity_id = _entity_id(hass)

    with pytest.raises(HomeAssistantError) as exc_info:
        await _press(hass, entity_id)
    assert exc_info.value.translation_key == "reboot_failed"

    coordinator = entry.runtime_data
    assert coordinator.last_update_success is False
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_button_unavailable_when_coordinator_fails(
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
