"""Tests for the output-routing media_player entities (issue #64)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.components.media_player import (  # noqa: E402
    MediaPlayerDeviceClass,
    MediaPlayerEntityFeature,
)
from homeassistant.const import (  # noqa: E402
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.helpers import device_registry as dr  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from blustream.devices.dmp168.models import OutputRouting, OutputSource  # noqa: E402
from custom_components.blustream.const import DOMAIN  # noqa: E402
from custom_components.blustream.media_player import (  # noqa: E402
    SOURCE_LIST,
    label_to_source,
    source_to_label,
)

from . import make_status  # noqa: E402

MAC = "34:d0:b8:21:22:33"
ENTRY_DATA = {
    CONF_HOST: "192.0.2.10",
    CONF_PORT: 23,
    CONF_NAME: "Test DMP168",
    CONF_MAC: MAC,
}


def _setup_device(routing=None) -> MagicMock:
    device = MagicMock()
    device.connect = AsyncMock()
    device.disconnect = AsyncMock()
    device.is_connected = True
    device.get_status = AsyncMock(return_value=make_status(routing=routing))
    device.set_output_source = AsyncMock()
    return device


async def _install(hass: HomeAssistant, device: MagicMock) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, unique_id=MAC)
    entry.add_to_hass(hass)
    with patch("custom_components.blustream.DMP168", return_value=device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def _entity_id(hass: HomeAssistant, output: int) -> str:
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "media_player", DOMAIN, f"{MAC}_output_{output}"
    )
    assert entity_id is not None
    return entity_id


# ---------------------------------------------------------------------------
# Pure-function source-label mapping
# ---------------------------------------------------------------------------


def test_source_list_is_none_plus_16_inputs_plus_8_buses() -> None:
    assert SOURCE_LIST[0] == "None"
    assert SOURCE_LIST.count("None") == 1
    assert "Input 1" in SOURCE_LIST and "Input 16" in SOURCE_LIST
    assert "Bus 1" in SOURCE_LIST and "Bus 8" in SOURCE_LIST
    assert "Input 17" not in SOURCE_LIST
    assert "Bus 9" not in SOURCE_LIST
    assert len(SOURCE_LIST) == 1 + 16 + 8


def test_label_source_round_trip() -> None:
    assert label_to_source("None") is None
    assert label_to_source("Input 5") == OutputSource.for_input(5)
    assert label_to_source("Bus 3") == OutputSource.for_bus(3)
    assert source_to_label(None) == "None"
    assert source_to_label(OutputSource.for_input(5)) == "Input 5"
    assert source_to_label(OutputSource.for_bus(3)) == "Bus 3"


def test_label_to_source_rejects_unknown_label() -> None:
    with pytest.raises(ValueError):
        label_to_source("Output 1")


# ---------------------------------------------------------------------------
# Entity surface
# ---------------------------------------------------------------------------


async def test_eight_media_players_under_one_device(hass: HomeAssistant) -> None:
    device = _setup_device()
    entry = await _install(hass, device)

    states = [
        s for s in hass.states.async_all() if s.domain == "media_player"
    ]
    assert len(states) == 8

    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert len(devices) == 1

    for output in range(1, 9):
        state = hass.states.get(_entity_id(hass, output))
        assert state.state == "on"
        assert (
            state.attributes["device_class"] == MediaPlayerDeviceClass.RECEIVER
        )
        assert (
            state.attributes["supported_features"]
            & MediaPlayerEntityFeature.SELECT_SOURCE
        )


async def test_source_list_exposed_on_state(hass: HomeAssistant) -> None:
    device = _setup_device()
    await _install(hass, device)
    state = hass.states.get(_entity_id(hass, 1))
    assert state.attributes["source_list"] == SOURCE_LIST


async def test_source_reflects_live_routing(hass: HomeAssistant) -> None:
    routing = [
        OutputRouting(output=out, channel=channel, source=None)
        for out in range(1, 9)
        for channel in ("L", "R")
    ]
    # Output 3 is fed by input 7; output 5 by bus 2.
    routing[(3 - 1) * 2] = OutputRouting(
        output=3, channel="L", source=OutputSource.for_input(7)
    )
    routing[(5 - 1) * 2] = OutputRouting(
        output=5, channel="L", source=OutputSource.for_bus(2)
    )
    device = _setup_device(routing=routing)
    await _install(hass, device)

    assert hass.states.get(_entity_id(hass, 3)).attributes["source"] == "Input 7"
    assert hass.states.get(_entity_id(hass, 5)).attributes["source"] == "Bus 2"
    assert hass.states.get(_entity_id(hass, 1)).attributes["source"] == "None"


async def test_select_source_routes_input(hass: HomeAssistant) -> None:
    device = _setup_device()
    await _install(hass, device)

    await hass.services.async_call(
        "media_player",
        "select_source",
        {"entity_id": _entity_id(hass, 2), "source": "Input 9"},
        blocking=True,
    )
    device.set_output_source.assert_awaited_once_with(2, OutputSource.for_input(9))


async def test_select_source_routes_bus(hass: HomeAssistant) -> None:
    device = _setup_device()
    await _install(hass, device)

    await hass.services.async_call(
        "media_player",
        "select_source",
        {"entity_id": _entity_id(hass, 4), "source": "Bus 6"},
        blocking=True,
    )
    device.set_output_source.assert_awaited_once_with(4, OutputSource.for_bus(6))


async def test_select_source_none_clears_route(hass: HomeAssistant) -> None:
    device = _setup_device()
    await _install(hass, device)

    await hass.services.async_call(
        "media_player",
        "select_source",
        {"entity_id": _entity_id(hass, 7), "source": "None"},
        blocking=True,
    )
    device.set_output_source.assert_awaited_once_with(7, None)


async def test_select_source_targets_many_outputs_in_one_call(
    hass: HomeAssistant,
) -> None:
    device = _setup_device()
    await _install(hass, device)

    targets = [_entity_id(hass, o) for o in (1, 2, 3)]
    await hass.services.async_call(
        "media_player",
        "select_source",
        {"entity_id": targets, "source": "Input 5"},
        blocking=True,
    )

    assert device.set_output_source.await_count == 3
    routed_outputs = {
        call.args[0] for call in device.set_output_source.await_args_list
    }
    assert routed_outputs == {1, 2, 3}
    for call in device.set_output_source.await_args_list:
        assert call.args[1] == OutputSource.for_input(5)


async def test_media_player_unavailable_when_coordinator_fails(
    hass: HomeAssistant,
) -> None:
    device = _setup_device()
    entry = await _install(hass, device)
    entity_id = _entity_id(hass, 1)

    coordinator = entry.runtime_data
    coordinator.last_update_success = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
