"""Button platform for the Blustream integration — device reboot.

A single ``button`` that reboots the DMP168. It inherits coordinator
availability and so greys out when the device is unreachable — honest,
because reboot travels over the same TCP channel that dies in the documented
"problem state", whose only recovery is a physical power-cycle
(``docs/dmp168-known-issues.md``). There is deliberately no out-of-band
reboot path, so the button has no ``always_available`` override.
"""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import CONF_MAC, CONF_NAME, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from blustream.base.exceptions import ConnectionError as BlustreamConnectionError

from .const import DOMAIN
from .coordinator import BlustreamConfigEntry, BlustreamCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlustreamConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Blustream button platform (the reboot button)."""
    async_add_entities([BlustreamRebootButton(entry.runtime_data, entry)])


class BlustreamRebootButton(CoordinatorEntity[BlustreamCoordinator], ButtonEntity):
    """Reboots the DMP168 over its TCP control channel."""

    _attr_has_entity_name = True
    _attr_translation_key = "reboot"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: BlustreamCoordinator,
        entry: BlustreamConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_reboot"

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

    async def async_press(self) -> None:
        """Reboot the device.

        On the library's connection error the device is, by definition, off
        the TCP channel reboot would use; mark the coordinator failed (so
        every entity greys out) and surface a translated
        :class:`HomeAssistantError` rather than letting the raw library
        exception propagate.
        """
        try:
            await self.coordinator.device.reboot()
        except BlustreamConnectionError as err:
            self.coordinator.last_update_success = False
            self.coordinator.async_update_listeners()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="reboot_failed",
            ) from err
