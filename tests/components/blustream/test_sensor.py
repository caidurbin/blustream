"""Tests for the sensor entities (uptime, temperature, DSP usage)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.components.sensor import (  # noqa: E402
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (  # noqa: E402
    CONF_HOST,
    CONF_MAC,
    CONF_PORT,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.helpers import (  # noqa: E402
    device_registry as dr,
)
from homeassistant.helpers import (  # noqa: E402
    entity_registry as er,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.blustream.const import DOMAIN  # noqa: E402

from . import make_status  # noqa: E402

ENTRY_DATA = {
    CONF_HOST: "192.0.2.10",
    CONF_PORT: 23,
    CONF_MAC: "34:d0:b8:21:22:33",
}

UID = "34:d0:b8:21:22:33"


def _setup_device(uptime_value=timedelta(days=3, hours=2, minutes=1), **status_kwargs):
    device = MagicMock()
    device.connect = AsyncMock()
    device.disconnect = AsyncMock()
    device.is_connected = True
    device.get_status = AsyncMock(
        return_value=make_status(uptime=uptime_value, **status_kwargs)
    )
    return device


async def _install(hass: HomeAssistant, device) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, unique_id=UID)
    entry.add_to_hass(hass)
    with patch("custom_components.blustream.DMP168", return_value=device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def _entity_id(hass: HomeAssistant, unique_id_suffix: str) -> str:
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{UID}_{unique_id_suffix}"
    )
    assert entity_id is not None, f"no sensor for suffix {unique_id_suffix!r}"
    return entity_id


async def test_uptime_state_is_a_datetime_close_to_now_minus_uptime(
    hass: HomeAssistant,
) -> None:
    uptime = timedelta(days=3, hours=2, minutes=1)
    device = _setup_device(uptime_value=uptime)
    await _install(hass, device)

    state = hass.states.get(_entity_id(hass, "uptime"))
    assert state.state not in (STATE_UNAVAILABLE, "unknown")

    boot_time = datetime.fromisoformat(state.state)
    if boot_time.tzinfo is None:
        boot_time = boot_time.replace(tzinfo=timezone.utc)
    delta_seconds = abs(
        (datetime.now(timezone.utc) - uptime - boot_time).total_seconds()
    )
    assert delta_seconds < 10


async def test_temperature_sensor_reports_celsius(hass: HomeAssistant) -> None:
    device = _setup_device(temperature=42.0)
    await _install(hass, device)

    state = hass.states.get(_entity_id(hass, "temperature"))
    assert float(state.state) == 42.0
    assert state.attributes["device_class"] == SensorDeviceClass.TEMPERATURE
    assert (
        state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS
    )
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT


async def test_dsp_usage_sensor_reports_percent(hass: HomeAssistant) -> None:
    device = _setup_device(dsp_usage=12.5)
    await _install(hass, device)

    state = hass.states.get(_entity_id(hass, "dsp_usage"))
    assert float(state.state) == 12.5
    assert state.attributes["unit_of_measurement"] == PERCENTAGE
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT
    assert "device_class" not in state.attributes


async def test_firmware_version_on_device_sw_version(hass: HomeAssistant) -> None:
    device = _setup_device(firmware_version="1.2.3")
    entry = await _install(hass, device)

    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert len(devices) == 1
    assert devices[0].sw_version == "1.2.3"


async def test_sensors_unavailable_when_coordinator_data_unavailable(
    hass: HomeAssistant,
) -> None:
    device = _setup_device()
    entry = await _install(hass, device)

    sensor_ids = [
        s.entity_id
        for s in hass.states.async_all()
        if s.domain == "sensor"
    ]
    assert len(sensor_ids) == 3

    coordinator = entry.runtime_data
    coordinator.last_update_success = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    for entity_id in sensor_ids:
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_sensors_register_device_and_entities(
    hass: HomeAssistant,
) -> None:
    device = _setup_device()
    entry = await _install(hass, device)

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert len(devices) == 1
    assert devices[0].manufacturer == "Blustream"
    assert devices[0].model == "DMP168"
    assert (DOMAIN, UID) in devices[0].identifiers
    assert (dr.CONNECTION_NETWORK_MAC, UID) in devices[0].connections

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    sensor_uids = {e.unique_id for e in entries if e.domain == "sensor"}
    assert sensor_uids == {
        f"{UID}_uptime",
        f"{UID}_temperature",
        f"{UID}_dsp_usage",
    }
