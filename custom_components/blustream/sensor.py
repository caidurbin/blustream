"""Sensor platform for the Blustream integration."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import BlustreamConfigEntry, BlustreamCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlustreamConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Blustream sensor platform."""
    async_add_entities([BlustreamUptimeSensor(entry.runtime_data, entry)])


class BlustreamUptimeSensor(CoordinatorEntity[BlustreamCoordinator], SensorEntity):
    """Reports the device's last-boot time as a UPTIME-class sensor.

    Per-poll clock drift is absorbed by HA's
    ``SensorEntity._normalize_uptime`` (default tolerance 60 s for
    ``SensorDeviceClass.UPTIME``), so we emit a fresh
    ``utcnow() - timedelta`` every poll and let HA quantize.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "uptime"
    _attr_device_class = SensorDeviceClass.UPTIME

    def __init__(
        self,
        coordinator: BlustreamCoordinator,
        entry: BlustreamConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_uptime"

        connections: set[tuple[str, str]] = set()
        if mac := entry.data.get(CONF_MAC):
            connections.add((CONNECTION_NETWORK_MAC, mac))

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            connections=connections,
            manufacturer="Blustream",
            model="DMP168",
            name=entry.data.get(CONF_NAME) or entry.title,
        )

    @property
    def native_value(self) -> datetime | None:
        if self.coordinator.data is None:
            return None
        return dt_util.utcnow() - self.coordinator.data
