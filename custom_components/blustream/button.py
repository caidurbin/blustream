"""Button platform for the Blustream integration — device reboot.

A single ``button`` that reboots the DMP168. The press succeeds only when
the library confirms the restart: ``DMP168.reboot()`` sends REBOOT, waits
for the device to answer again and checks that its uptime reset. Firmware
MCU V1.5.0 acknowledges REBOOT on the TCP control channel and keeps
running; the press then fails with a message saying so, and the entities
stay available because the device is still up.

The button inherits coordinator availability and so greys out when the
device is unreachable — honest, because on older firmware (Web_GUI ≤
V1.4.0) the device can wedge into a state where every control surface
(Telnet, raw TCP, web CGI) dies together and only a physical power-cycle
recovers it. Reboot travels over that same TCP channel, so there is
deliberately no out-of-band reboot path and the button has no
``always_available`` override.
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
from blustream.base.exceptions import RebootNotConfirmedError
from blustream.base.exceptions import TimeoutError as BlustreamTimeoutError

from .const import DOMAIN
from .coordinator import BlustreamConfigEntry, BlustreamCoordinator
from .device import command_errors


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
        """Reboot the device and confirm that it restarted.

        Every failure surfaces as a translated :class:`HomeAssistantError`
        rather than the raw library exception:

        * The device acknowledged REBOOT but its uptime did not reset: it is
          still up, so the entities stay available.
        * The device is not connected, or went offline after REBOOT and did
          not come back in time: it is off the TCP channel, so the
          coordinator is marked failed and every entity greys out.
        * The device rejected REBOOT: the error carries the device's message.

        After a confirmed restart the coordinator refreshes, so the entities
        recover without waiting for the next poll.
        """
        # RebootNotConfirmedError is a CommandError, so it is caught here
        # before command_errors() turns it into the generic command_failed.
        with command_errors():
            try:
                await self.coordinator.device.reboot()
            except RebootNotConfirmedError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="reboot_not_restarted",
                ) from err
            except (BlustreamConnectionError, BlustreamTimeoutError) as err:
                self.coordinator.async_set_update_error(err)
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key=(
                        "reboot_no_return"
                        if isinstance(err, BlustreamTimeoutError)
                        else "reboot_failed"
                    ),
                ) from err
        await self.coordinator.async_request_refresh()
