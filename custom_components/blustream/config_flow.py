"""Config flow for the Blustream integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_PORT
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from blustream import DMP168
from blustream.base.exceptions import (
    ConnectionError as BlustreamConnectionError,
)
from blustream.base.exceptions import (
    TimeoutError as BlustreamTimeoutError,
)

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_NAME): str,
        vol.Optional(CONF_MAC): str,
    }
)


def _is_valid_mac(value: str) -> bool:
    """True if ``value`` normalizes to a 48-bit MAC.

    ``format_mac`` collapses any non-hex separator and lowercases. A
    well-formed input leaves exactly 12 hex digits behind once the
    colons are dropped.
    """
    normalized = format_mac(value).replace(":", "")
    if len(normalized) != 12:
        return False
    return all(ch in "0123456789abcdef" for ch in normalized)


async def _validate_connectivity(host: str, port: int) -> None:
    """Connect, fetch uptime, disconnect — raise on any failure."""
    device = DMP168(host=host, port=port)
    try:
        await device.connect()
        await device.get_uptime()
    finally:
        await device.disconnect()


class BlustreamConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Blustream config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    _discovered_host: str | None = None
    _discovered_mac: str | None = None

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a DHCP discovery.

        ``registered_devices: true`` in the manifest dispatches DHCP
        callbacks for already-configured entries too -- that is the
        IP-change path: ``_abort_if_unique_id_configured(updates={...})``
        updates the stored host silently and schedules a reload, with no
        user prompt and no loss of entity history. For brand-new devices
        the user lands on the discovery confirmation step.
        """
        mac = format_mac(discovery_info.macaddress)
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})

        self._discovered_host = discovery_info.ip
        self._discovered_mac = mac
        self.context["title_placeholders"] = {"host": discovery_info.ip, "mac": mac}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a DHCP-discovered device before creating its entry."""
        assert self._discovered_host is not None
        assert self._discovered_mac is not None

        if user_input is not None:
            data = {
                CONF_HOST: self._discovered_host,
                CONF_PORT: DEFAULT_PORT,
                CONF_MAC: self._discovered_mac,
            }
            return self.async_create_entry(title=self._discovered_host, data=data)

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "host": self._discovered_host,
                "mac": self._discovered_mac,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the manual setup step.

        Asks for host, port, optional name, and an optional MAC. The MAC
        gates the entry's identity: if supplied and well-formed, the
        ``unique_id`` is ``format_mac(mac)`` (and a second entry with the
        same MAC aborts as ``already_configured``); if omitted, the entry
        is created without a ``unique_id`` and ``__init__.async_setup_entry``
        falls back to the entry-id tier (ADR 0010).
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            mac_raw = user_input.get(CONF_MAC)
            mac_normalized: str | None = None

            if mac_raw:
                if not _is_valid_mac(mac_raw):
                    errors["base"] = "invalid_mac"
                else:
                    mac_normalized = format_mac(mac_raw)

            if not errors and mac_normalized is not None:
                await self.async_set_unique_id(mac_normalized)
                self._abort_if_unique_id_configured()

            if not errors:
                try:
                    await _validate_connectivity(
                        user_input[CONF_HOST], user_input[CONF_PORT]
                    )
                except (BlustreamConnectionError, BlustreamTimeoutError):
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error validating Blustream device")
                    errors["base"] = "unknown"
                else:
                    data = dict(user_input)
                    if mac_normalized is not None:
                        data[CONF_MAC] = mac_normalized
                    else:
                        data.pop(CONF_MAC, None)
                    title = data.get(CONF_NAME) or data[CONF_HOST]
                    return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
