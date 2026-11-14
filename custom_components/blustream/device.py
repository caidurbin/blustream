"""Shared device-registry metadata for the Blustream integration.

Every Blustream entity (uptime sensor, output media players, power switch,
reboot button) belongs to the same physical DMP168, so they all share one
``DeviceInfo``. Building it in one place keeps the identity, connection, and
firmware ``sw_version`` consistent across every platform rather than copied
per platform.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
)

from blustream.base.exceptions import CommandError as BlustreamCommandError

from .const import DOMAIN
from .coordinator import BlustreamConfigEntry, BlustreamCoordinator


@contextmanager
def command_errors() -> Iterator[None]:
    """Raise a failed device command as a translated ``HomeAssistantError``.

    The library raises ``CommandError`` when the device rejects a command or
    the exchange fails. Inside this context the error reaches the user as a
    failed action that carries the device's message.
    """
    try:
        yield
    except BlustreamCommandError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_failed",
            translation_placeholders={"error": str(err)},
        ) from err


def build_device_info(
    entry: BlustreamConfigEntry, coordinator: BlustreamCoordinator
) -> DeviceInfo:
    """Return the shared :class:`DeviceInfo` for the DMP168 device.

    The firmware version is read from the coordinator's polled
    :class:`~blustream.devices.dmp168.models.SystemStatus` and surfaced as
    ``sw_version`` rather than a separate entity (issue #68).
    """
    connections: set[tuple[str, str]] = set()
    if mac := entry.data.get(CONF_MAC):
        connections.add((CONNECTION_NETWORK_MAC, mac))

    status = coordinator.data
    sw_version = status.firmware_version if status is not None else None

    return DeviceInfo(
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        connections=connections,
        manufacturer="Blustream",
        model="DMP168",
        name=entry.data.get(CONF_NAME) or entry.title,
        sw_version=sw_version,
    )
