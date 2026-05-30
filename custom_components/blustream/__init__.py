"""The Blustream Home Assistant integration."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from blustream import DMP168

from .coordinator import BlustreamConfigEntry, BlustreamCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: BlustreamConfigEntry
) -> bool:
    """Set up Blustream from a config entry."""
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=entry.entry_id)
    device = DMP168(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT])
    coordinator = BlustreamCoordinator(hass, entry, device)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: BlustreamConfigEntry
) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator = entry.runtime_data
        await coordinator.device.disconnect()
    return unloaded
