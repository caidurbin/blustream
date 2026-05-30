"""Diagnostics support for the Blustream integration.

Returns a downloadable ``{config_entry, device, data}`` payload for
one-shot triage. Home-network-identifying fields (host IP, MAC,
hostname, unique_id, device-registry connections / identifiers) are
auto-redacted via :func:`async_redact_data`.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import (
    ATTR_CONNECTIONS,
    ATTR_IDENTIFIERS,
    CONF_HOST,
    CONF_MAC,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.loader import async_get_integration

from blustream import __version__ as BLUSTREAM_LIBRARY_VERSION  # noqa: N812

from .const import DOMAIN
from .coordinator import BlustreamConfigEntry

TO_REDACT_ENTRY = {CONF_HOST, CONF_MAC, "hostname", CONF_UNIQUE_ID}
TO_REDACT_DEVICE = {ATTR_CONNECTIONS, ATTR_IDENTIFIERS}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BlustreamConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    device = coordinator.device

    status = await device.get_status()
    raw_uptime = await device.get_uptime_raw()
    integration = await async_get_integration(hass, DOMAIN)

    device_registry = dr.async_get(hass)
    hass_device = device_registry.async_get_device(
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)}
    )

    update_interval = coordinator.update_interval
    last_data = coordinator.data

    data: dict[str, Any] = {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT_ENTRY),
        "device": (
            async_redact_data(hass_device.dict_repr, TO_REDACT_DEVICE)
            if hass_device is not None
            else None
        ),
        "data": {
            "coordinator": {
                "last_update_success": coordinator.last_update_success,
                "last_uptime_seconds": (
                    last_data.total_seconds() if last_data is not None else None
                ),
                "update_interval_seconds": (
                    update_interval.total_seconds()
                    if update_interval is not None
                    else None
                ),
            },
            "status": status.to_dict(),
            "uptime_raw": raw_uptime,
            "integration_version": integration.version,
            "library_version": BLUSTREAM_LIBRARY_VERSION,
        },
    }
    return data
