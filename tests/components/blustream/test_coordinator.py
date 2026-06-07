"""Tests for BlustreamCoordinator."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import ConfigEntryState  # noqa: E402
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from blustream.base.exceptions import (  # noqa: E402
    CommandError as BlustreamCommandError,
)
from blustream.base.exceptions import (  # noqa: E402
    ConnectionError as BlustreamConnectionError,
)
from blustream.base.exceptions import (  # noqa: E402
    ParseError as BlustreamParseError,
)
from blustream.base.exceptions import (  # noqa: E402
    TimeoutError as BlustreamTimeoutError,
)
from custom_components.blustream.const import DOMAIN  # noqa: E402

from . import make_status  # noqa: E402

ENTRY_DATA = {
    CONF_HOST: "192.0.2.10",
    CONF_PORT: 23,
    CONF_MAC: "34:d0:b8:21:22:33",
}


def _setup_device(uptime_value=None, status_side_effect=None):
    device = MagicMock()
    device.connect = AsyncMock()
    device.disconnect = AsyncMock()
    device.is_connected = True
    device.get_status = AsyncMock(
        return_value=make_status(uptime=uptime_value or timedelta(days=1, seconds=42)),
        side_effect=status_side_effect,
    )
    return device


async def _setup_with_device(hass: HomeAssistant, device) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        unique_id="34:d0:b8:21:22:33",
    )
    entry.add_to_hass(hass)
    with patch("custom_components.blustream.DMP168", return_value=device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_coordinator_happy_path_loads_entry(hass: HomeAssistant) -> None:
    device = _setup_device(uptime_value=timedelta(days=3, hours=4))
    entry = await _setup_with_device(hass, device)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.last_update_success
    # coordinator.data is now the full SystemStatus poll (issue #64).
    assert entry.runtime_data.data == make_status(uptime=timedelta(days=3, hours=4))


async def test_coordinator_connection_error_raises_config_entry_not_ready_on_first_refresh(
    hass: HomeAssistant,
) -> None:
    device = _setup_device(
        status_side_effect=BlustreamConnectionError("offline")
    )
    entry = await _setup_with_device(hass, device)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_timeout_error_raises_config_entry_not_ready_on_first_refresh(
    hass: HomeAssistant,
) -> None:
    device = _setup_device(status_side_effect=BlustreamTimeoutError("slow"))
    entry = await _setup_with_device(hass, device)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_parse_error_raises_config_entry_not_ready_on_first_refresh(
    hass: HomeAssistant,
) -> None:
    device = _setup_device(status_side_effect=BlustreamParseError("bad"))
    entry = await _setup_with_device(hass, device)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_command_error_raises_config_entry_not_ready_on_first_refresh(
    hass: HomeAssistant,
) -> None:
    device = _setup_device(status_side_effect=BlustreamCommandError("err"))
    entry = await _setup_with_device(hass, device)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_unexpected_exception_retries_setup(
    hass: HomeAssistant,
) -> None:
    """An unexpected (non-Blustream) exception on the first refresh is not
    distinguished from a connection failure: HA's DataUpdateCoordinator
    catches it, marks the update unsuccessful, and
    ``async_config_entry_first_refresh`` raises ``ConfigEntryNotReady`` --
    so the entry lands in SETUP_RETRY, same as the expected error paths
    above. (The coordinator does not force a hard SETUP_ERROR; a transient
    bug should still be retried rather than wedging the entry.)"""
    device = _setup_device(status_side_effect=RuntimeError("surprise"))
    entry = MockConfigEntry(
        domain=DOMAIN, data=ENTRY_DATA, unique_id="34:d0:b8:21:22:33"
    )
    entry.add_to_hass(hass)
    with patch("custom_components.blustream.DMP168", return_value=device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_recovery_after_transient_failure(
    hass: HomeAssistant,
) -> None:
    """After a successful first refresh, a later UpdateFailed should mark
    the coordinator unsuccessful without crashing the entry."""
    device = _setup_device(uptime_value=timedelta(seconds=10))
    entry = await _setup_with_device(hass, device)
    assert entry.runtime_data.last_update_success

    device.get_status.side_effect = BlustreamConnectionError("flapped")
    await entry.runtime_data.async_refresh()
    assert entry.runtime_data.last_update_success is False
