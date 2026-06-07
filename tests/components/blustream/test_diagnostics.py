"""Tests for diagnostics.py (config-entry diagnostics with redaction)."""

from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.components.diagnostics import REDACTED  # noqa: E402
from homeassistant.const import (  # noqa: E402
    ATTR_CONNECTIONS,
    ATTR_IDENTIFIERS,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from blustream import __version__ as LIBRARY_VERSION  # noqa: E402, N812
from blustream.devices.dmp168.models import (  # noqa: E402
    InputSettings,
    OutputRouting,
    OutputSource,
    SystemStatus,
)
from custom_components.blustream.const import DOMAIN  # noqa: E402
from custom_components.blustream.diagnostics import (  # noqa: E402
    async_get_config_entry_diagnostics,
)

HOST = "192.0.2.10"
MAC = "34:d0:b8:21:22:33"
UPTIME_RAW = "0003:02:01:00"


def _make_status() -> SystemStatus:
    return SystemStatus(
        power="On",
        baud=9600,
        level_unit="dB",
        auto_standby_time=0,
        dsp_usage=12.5,
        fade=True,
        temperature=42.0,
        uptime=UPTIME_RAW,
        firmware_version="1.2.3",
        inputs=[
            InputSettings(
                port=1, lock=True, gain_l=50, gain_r=50, mute_l=False, mute_r=False
            )
        ],
        routing=[
            OutputRouting(output=1, channel="L", source=OutputSource.for_input(1))
        ],
    )


def _patched_device() -> MagicMock:
    device = MagicMock()
    device.connect = AsyncMock()
    device.disconnect = AsyncMock()
    device.is_connected = True
    device.get_uptime = AsyncMock(return_value=timedelta(days=3, hours=2, minutes=1))
    device.get_uptime_raw = AsyncMock(return_value=UPTIME_RAW)
    device.get_status = AsyncMock(return_value=_make_status())
    return device


async def _setup_entry(hass: HomeAssistant, device: MagicMock) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=HOST,  # DHCP/manual-no-name entries surface the host IP as the title
        data={
            CONF_HOST: HOST,
            CONF_PORT: 23,
            CONF_NAME: "Test DMP168",
            CONF_MAC: MAC,
        },
        unique_id=MAC,
    )
    entry.add_to_hass(hass)
    with patch("custom_components.blustream.DMP168", return_value=device):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_diagnostics_returns_expected_shape(hass: HomeAssistant) -> None:
    """Top-level shape is {config_entry, device, data} with all expected fields."""
    device = _patched_device()
    entry = await _setup_entry(hass, device)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert set(result) == {"config_entry", "device", "data"}

    config_entry = result["config_entry"]
    assert config_entry["domain"] == DOMAIN
    assert config_entry["data"][CONF_HOST] == REDACTED
    assert config_entry["data"][CONF_MAC] == REDACTED
    assert config_entry["data"][CONF_PORT] == 23
    assert config_entry[CONF_UNIQUE_ID] == REDACTED
    assert config_entry["title"] == REDACTED

    device_dict = result["device"]
    assert device_dict is not None
    assert device_dict[ATTR_CONNECTIONS] == REDACTED
    assert device_dict[ATTR_IDENTIFIERS] == REDACTED
    assert device_dict["manufacturer"] == "Blustream"
    assert device_dict["model"] == "DMP168"

    data = result["data"]
    assert data["coordinator"]["last_update_success"] is True
    assert data["coordinator"]["update_interval_seconds"] == 30.0
    assert data["coordinator"]["last_uptime_seconds"] == timedelta(
        days=3, hours=2, minutes=1
    ).total_seconds()

    assert data["status"] == _make_status().to_dict()
    assert data["uptime_raw"] == UPTIME_RAW
    assert data["integration_version"] == "0.1.0"
    assert data["library_version"] == LIBRARY_VERSION


async def test_diagnostics_redacts_host_mac_unique_id(hass: HomeAssistant) -> None:
    """No host IP, MAC, or unique_id appears unredacted anywhere in the payload."""
    device = _patched_device()
    entry = await _setup_entry(hass, device)

    result = await async_get_config_entry_diagnostics(hass, entry)
    serialized = json.dumps(result, default=str)

    assert HOST not in serialized
    assert MAC not in serialized
    # The dashed/uppercase MAC variants would also be leaks.
    assert MAC.upper() not in serialized
    assert MAC.replace(":", "") not in serialized
    assert MAC.replace(":", "-") not in serialized


async def test_diagnostics_freshly_polls_status_and_uptime(
    hass: HomeAssistant,
) -> None:
    """``get_status`` / ``get_uptime_raw`` are awaited on each diagnostics call."""
    device = _patched_device()
    entry = await _setup_entry(hass, device)

    device.get_status.reset_mock()
    device.get_uptime_raw.reset_mock()

    await async_get_config_entry_diagnostics(hass, entry)

    device.get_status.assert_awaited_once()
    device.get_uptime_raw.assert_awaited_once()
