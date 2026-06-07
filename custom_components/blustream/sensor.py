"""Sensor platform for the Blustream integration."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from blustream.base.exceptions import ParseError
from blustream.devices.dmp168.uptime_parser import parse as parse_uptime

from .coordinator import BlustreamConfigEntry, BlustreamCoordinator
from .device import build_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlustreamConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Blustream sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            BlustreamUptimeSensor(coordinator, entry),
            BlustreamTemperatureSensor(coordinator, entry),
            BlustreamDspUsageSensor(coordinator, entry),
        ]
    )


class BlustreamUptimeSensor(CoordinatorEntity[BlustreamCoordinator], SensorEntity):
    """Reports the device's last-boot time as a UPTIME-class sensor.

    The uptime duration is read from the coordinator's
    :class:`~blustream.devices.dmp168.models.SystemStatus` (issue #64) and
    converted to a boot-time instant. Per-poll clock drift is absorbed by
    HA's ``SensorEntity._normalize_uptime`` (default tolerance 60 s for
    ``SensorDeviceClass.UPTIME``), so we emit a fresh ``utcnow() - timedelta``
    every poll and let HA quantize.
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
        self._attr_device_info = build_device_info(entry, coordinator)

    @property
    def native_value(self) -> datetime | None:
        status = self.coordinator.data
        if status is None:
            return None
        try:
            uptime = parse_uptime(status.uptime)
        except ParseError:
            return None
        return dt_util.utcnow() - uptime


class BlustreamTemperatureSensor(CoordinatorEntity[BlustreamCoordinator], SensorEntity):
    """Reports the DMP168's internal temperature in °C (issue #68)."""

    _attr_has_entity_name = True
    _attr_translation_key = "temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: BlustreamCoordinator,
        entry: BlustreamConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_temperature"
        self._attr_device_info = build_device_info(entry, coordinator)

    @property
    def native_value(self) -> float | None:
        status = self.coordinator.data
        if status is None:
            return None
        return status.temperature


class BlustreamDspUsageSensor(CoordinatorEntity[BlustreamCoordinator], SensorEntity):
    """Reports DSP utilization as a percentage (issue #68).

    Useful for diagnosing the documented ~3 h idle "problem state".
    """

    _attr_has_entity_name = True
    _attr_translation_key = "dsp_usage"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        coordinator: BlustreamCoordinator,
        entry: BlustreamConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_dsp_usage"
        self._attr_device_info = build_device_info(entry, coordinator)

    @property
    def native_value(self) -> float | None:
        status = self.coordinator.data
        if status is None:
            return None
        return status.dsp_usage
