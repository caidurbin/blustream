"""Tests for the Blustream config flow."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries  # noqa: E402
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_PORT  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from blustream.base.exceptions import (  # noqa: E402
    ConnectionError as BlustreamConnectionError,
)
from blustream.base.exceptions import (  # noqa: E402
    TimeoutError as BlustreamTimeoutError,
)
from custom_components.blustream.const import DOMAIN  # noqa: E402

USER_INPUT_WITH_MAC = {
    CONF_HOST: "192.0.2.10",
    CONF_PORT: 23,
    CONF_NAME: "Test DMP168",
    CONF_MAC: "34:D0:B8:21:22:33",
}

USER_INPUT_NO_MAC = {
    CONF_HOST: "192.0.2.11",
    CONF_PORT: 23,
}

DHCP_DISCOVERY = DhcpServiceInfo(
    ip="192.0.2.50",
    hostname="dmp168",
    macaddress="34d0b8212233",
)

DHCP_DISCOVERY_SECOND_UNIT = DhcpServiceInfo(
    ip="192.0.2.51",
    hostname="dmp168",
    macaddress="34d0b8aabbcc",
)


def _patched_device(uptime_side_effect=None) -> MagicMock:
    device = MagicMock()
    device.connect = AsyncMock()
    device.disconnect = AsyncMock()
    device.get_uptime = AsyncMock(
        return_value=timedelta(seconds=120),
        side_effect=uptime_side_effect,
    )
    return device


async def test_user_step_form_initial(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_step_happy_path_with_mac(hass: HomeAssistant) -> None:
    device = _patched_device()
    with patch(
        "custom_components.blustream.config_flow.DMP168", return_value=device
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT_WITH_MAC
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test DMP168"
    assert result["data"][CONF_HOST] == "192.0.2.10"
    assert result["data"][CONF_PORT] == 23
    assert result["data"][CONF_MAC] == "34:d0:b8:21:22:33"
    assert result["result"].unique_id == "34:d0:b8:21:22:33"
    device.connect.assert_awaited_once()
    device.get_uptime.assert_awaited_once()
    device.disconnect.assert_awaited_once()


async def test_user_step_happy_path_no_mac_uses_no_unique_id_yet(
    hass: HomeAssistant,
) -> None:
    device = _patched_device()
    with patch(
        "custom_components.blustream.config_flow.DMP168", return_value=device
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT_NO_MAC
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.0.2.11"
    assert CONF_MAC not in result["data"]
    assert result["result"].unique_id is None


async def test_user_step_invalid_mac(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**USER_INPUT_WITH_MAC, CONF_MAC: "not-a-mac"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_mac"}


async def test_user_step_cannot_connect(hass: HomeAssistant) -> None:
    device = _patched_device(
        uptime_side_effect=BlustreamConnectionError("nope")
    )
    with patch(
        "custom_components.blustream.config_flow.DMP168", return_value=device
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT_WITH_MAC
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    device.disconnect.assert_awaited()


async def test_user_step_cannot_connect_timeout(hass: HomeAssistant) -> None:
    device = _patched_device(
        uptime_side_effect=BlustreamTimeoutError("timeout")
    )
    with patch(
        "custom_components.blustream.config_flow.DMP168", return_value=device
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT_WITH_MAC
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_step_unknown_error(hass: HomeAssistant) -> None:
    device = _patched_device(uptime_side_effect=RuntimeError("boom"))
    with patch(
        "custom_components.blustream.config_flow.DMP168", return_value=device
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT_WITH_MAC
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_user_step_already_configured(hass: HomeAssistant) -> None:
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.99",
            CONF_PORT: 23,
            CONF_MAC: "34:d0:b8:21:22:33",
        },
        unique_id="34:d0:b8:21:22:33",
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT_WITH_MAC
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_discovery_creates_entry_with_mac_unique_id(
    hass: HomeAssistant,
) -> None:
    """Confirming a DHCP discovery creates an entry with format_mac(mac)
    as ``unique_id`` and the discovered IP as ``CONF_HOST``."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.0.2.50"
    assert result["data"][CONF_MAC] == "34:d0:b8:21:22:33"
    assert result["result"].unique_id == "34:d0:b8:21:22:33"


async def test_dhcp_discovery_normalizes_mac_to_format_mac(
    hass: HomeAssistant,
) -> None:
    """The DHCP-source MAC arrives unseparated and lowercase; the entry's
    unique_id must be the format_mac-normalized colon-and-lowercase form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.0.2.60", hostname="dmp168", macaddress="34D0B8AABBCC"
        ),
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "34:d0:b8:aa:bb:cc"


async def test_dhcp_discovery_for_already_configured_updates_host_silently(
    hass: HomeAssistant,
) -> None:
    """A DHCP-reported IP change for an existing MAC-anchored entry must
    update CONF_HOST silently via _abort_if_unique_id_configured(updates=)
    -- the flow aborts as already_configured but the stored host follows
    the new IP and the entry id (and entity history) survives."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 23,
            CONF_MAC: "34:d0:b8:21:22:33",
        },
        unique_id="34:d0:b8:21:22:33",
    )
    existing.add_to_hass(hass)
    original_entry_id = existing.entry_id

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert existing.data[CONF_HOST] == "192.0.2.50"
    assert existing.entry_id == original_entry_id
    assert existing.unique_id == "34:d0:b8:21:22:33"


async def test_dhcp_already_configured_with_same_ip_is_noop_abort(
    hass: HomeAssistant,
) -> None:
    """Re-discovery of an already-configured device at its current IP
    aborts as already_configured without touching the stored host."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.50",
            CONF_PORT: 23,
            CONF_MAC: "34:d0:b8:21:22:33",
        },
        unique_id="34:d0:b8:21:22:33",
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert existing.data[CONF_HOST] == "192.0.2.50"


async def test_dhcp_two_units_on_one_lan_get_independent_identities(
    hass: HomeAssistant,
) -> None:
    """Two DMP168s discovered concurrently must end up as two separate
    entries -- each MAC-anchored to its own unique_id, neither one
    overwriting the other's CONF_HOST."""
    first = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )
    first = await hass.config_entries.flow.async_configure(first["flow_id"], {})
    assert first["type"] is FlowResultType.CREATE_ENTRY

    second = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DHCP_DISCOVERY_SECOND_UNIT,
    )
    second = await hass.config_entries.flow.async_configure(second["flow_id"], {})
    assert second["type"] is FlowResultType.CREATE_ENTRY

    assert first["result"].unique_id == "34:d0:b8:21:22:33"
    assert second["result"].unique_id == "34:d0:b8:aa:bb:cc"
    assert first["result"].data[CONF_HOST] == "192.0.2.50"
    assert second["result"].data[CONF_HOST] == "192.0.2.51"
    assert first["result"].entry_id != second["result"].entry_id


async def test_handoff_validation_connect_disconnect_is_isolated_from_coordinator(
    hass: HomeAssistant,
) -> None:
    """Regression: the config-flow's validation connect+disconnect must not
    destabilize the coordinator's subsequent persistent connection. Two
    distinct DMP168 instances must be constructed -- one for the flow's
    throwaway connect, one for the coordinator's lifetime connection."""

    constructed: list[MagicMock] = []

    def _factory(*args, **kwargs):  # noqa: ARG001
        d = _patched_device()
        constructed.append(d)
        return d

    with (
        patch("custom_components.blustream.config_flow.DMP168", side_effect=_factory),
        patch("custom_components.blustream.DMP168", side_effect=_factory),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT_WITH_MAC
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()

    assert len(constructed) >= 2, (
        "expected separate DMP168 instances for the validation connect "
        "and the coordinator's persistent connection"
    )
    flow_device = constructed[0]
    coordinator_device = constructed[1]
    flow_device.disconnect.assert_awaited()
    coordinator_device.get_uptime.assert_awaited()
    coordinator_device.disconnect.assert_not_called()
