"""Tests for __init__.py (setup/unload/runtime_data wiring)."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import ConfigEntryState  # noqa: E402
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.blustream.const import DOMAIN  # noqa: E402
from custom_components.blustream.coordinator import BlustreamCoordinator  # noqa: E402


def _setup_device():
    device = MagicMock()
    device.connect = AsyncMock()
    device.disconnect = AsyncMock()
    device.is_connected = True
    device.get_uptime = AsyncMock(return_value=timedelta(days=1))
    return device


async def test_setup_entry_populates_runtime_data(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 23,
            CONF_MAC: "34:d0:b8:21:22:33",
        },
        unique_id="34:d0:b8:21:22:33",
    )
    entry.add_to_hass(hass)
    device = _setup_device()
    with patch("custom_components.blustream.DMP168", return_value=device):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data, BlustreamCoordinator)
    assert hass.data.get(DOMAIN) is None


async def test_setup_entry_assigns_entry_id_when_no_unique_id(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.11", CONF_PORT: 23},
        unique_id=None,
    )
    entry.add_to_hass(hass)
    device = _setup_device()
    with patch("custom_components.blustream.DMP168", return_value=device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.unique_id == entry.entry_id


async def test_unload_entry_disconnects_device(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 23,
            CONF_MAC: "34:d0:b8:21:22:33",
        },
        unique_id="34:d0:b8:21:22:33",
    )
    entry.add_to_hass(hass)
    device = _setup_device()
    with patch("custom_components.blustream.DMP168", return_value=device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    device.disconnect.assert_awaited()
