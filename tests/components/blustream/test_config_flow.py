"""Tests for the Blustream config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries  # noqa: E402
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_PORT  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
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


def _patched_device(uptime_side_effect=None) -> MagicMock:
    device = MagicMock()
    device.connect = AsyncMock()
    device.disconnect = AsyncMock()
    device.get_uptime = AsyncMock(
        return_value=None if uptime_side_effect else __import__(
            "datetime"
        ).timedelta(seconds=120),
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
