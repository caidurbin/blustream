"""Switch platform for the Blustream integration — device soft power.

The DMP168 has a single device-wide soft-power state (On vs Off(Standby));
there is no per-output power concept, so this is the one "asleep" signal
(issue #66, PRD #62). It is the device's primary control, so it carries no
device class and no entity category.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import BlustreamConfigEntry, BlustreamCoordinator
from .device import build_device_info

# The device reports power as one of these tokens in ``get_status()``; "On"
# is the only awake value, everything else (i.e. "Off(Standby)") is asleep.
_POWER_ON = "On"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlustreamConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Blustream switch platform (the device power switch)."""
    async_add_entities([BlustreamPowerSwitch(entry.runtime_data, entry)])


class BlustreamPowerSwitch(CoordinatorEntity[BlustreamCoordinator], SwitchEntity):
    """Device-wide soft power (standby/wake).

    Reads the power field from the coordinator's polled status; ``turn_on``
    wakes the device and ``turn_off`` puts it into standby. Goes unavailable
    with the coordinator so it never shows a stale power state.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "power"

    def __init__(
        self,
        coordinator: BlustreamCoordinator,
        entry: BlustreamConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_power"
        self._attr_device_info = build_device_info(entry, coordinator)

    @property
    def is_on(self) -> bool | None:
        """True when the device reports power On, False in standby."""
        status = self.coordinator.data
        if status is None:
            return None
        return status.power == _POWER_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Wake the device from standby."""
        await self.coordinator.device.power_on()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Put the device into standby."""
        await self.coordinator.device.power_off()
        await self.coordinator.async_request_refresh()
