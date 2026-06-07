"""Media player platform for the Blustream integration — output routing.

Each of the DMP168's 8 outputs is modelled as a single-source
``media_player`` exposing ``SELECT_SOURCE`` (ADR 0014). ``source_list`` is
the device-native ``None`` target plus the 16 inputs and 8 buses; selecting a
source routes it, and selecting ``None`` clears the route. One input feeds
several outputs by targeting several output entities (or an area/label) in a
single ``media_player.select_source`` action.
"""

from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from blustream.devices.dmp168.models import SOURCE_BUS, SOURCE_INPUT, OutputSource

from .const import BUS_COUNT, DOMAIN, INPUT_COUNT, OUTPUT_COUNT
from .coordinator import BlustreamConfigEntry, BlustreamCoordinator

# The device-native "no source" routing target, surfaced as a first-class
# selectable value rather than a turn_off overload (ADR 0014, CONTEXT.md
# "Source").
SOURCE_NONE = "None"
_INPUT_PREFIX = "Input "
_BUS_PREFIX = "Bus "

SOURCE_LIST: list[str] = (
    [SOURCE_NONE]
    + [f"{_INPUT_PREFIX}{n}" for n in range(1, INPUT_COUNT + 1)]
    + [f"{_BUS_PREFIX}{n}" for n in range(1, BUS_COUNT + 1)]
)


def source_to_label(source: OutputSource | None) -> str:
    """Map a routed :class:`OutputSource` (or ``None``) to its source label."""
    if source is None:
        return SOURCE_NONE
    if source.kind == SOURCE_BUS:
        return f"{_BUS_PREFIX}{source.number}"
    return f"{_INPUT_PREFIX}{source.number}"


def label_to_source(label: str) -> OutputSource | None:
    """Map a source label to an :class:`OutputSource`, or ``None`` to clear.

    Raises:
        ValueError: If ``label`` is not a known source-list entry.
    """
    if label == SOURCE_NONE:
        return None
    if label.startswith(_INPUT_PREFIX):
        return OutputSource(kind=SOURCE_INPUT, number=int(label[len(_INPUT_PREFIX) :]))
    if label.startswith(_BUS_PREFIX):
        return OutputSource(kind=SOURCE_BUS, number=int(label[len(_BUS_PREFIX) :]))
    raise ValueError(f"Unknown source '{label}'")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlustreamConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Blustream media_player platform (one entity per output)."""
    coordinator = entry.runtime_data
    async_add_entities(
        BlustreamOutputMediaPlayer(coordinator, entry, output)
        for output in range(1, OUTPUT_COUNT + 1)
    )


class BlustreamOutputMediaPlayer(
    CoordinatorEntity[BlustreamCoordinator], MediaPlayerEntity
):
    """A single DMP168 output, routed via ``media_player.select_source``."""

    _attr_has_entity_name = True
    _attr_translation_key = "output"
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = MediaPlayerEntityFeature.SELECT_SOURCE
    _attr_source_list = SOURCE_LIST

    def __init__(
        self,
        coordinator: BlustreamCoordinator,
        entry: BlustreamConfigEntry,
        output: int,
    ) -> None:
        super().__init__(coordinator)
        self._output = output
        self._attr_unique_id = f"{entry.unique_id}_output_{output}"
        self._attr_translation_placeholders = {"number": str(output)}

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

    @property
    def state(self) -> MediaPlayerState:
        """Always ON while the device is reachable.

        Reachability is reflected by ``available`` (driven by the
        coordinator's last update); the output itself has no power state of
        its own, so it reads ON whenever it reports at all.
        """
        return MediaPlayerState.ON

    @property
    def source(self) -> str | None:
        """The label of the source currently feeding this output.

        The L channel is canonical (ADR 0014). Returns ``None`` only when the
        status carries no routing row for this output (it never has yet).
        """
        status = self.coordinator.data
        if status is None:
            return None
        for row in status.routing:
            if row.output == self._output and row.channel == "L":
                return source_to_label(row.source)
        return None

    async def async_select_source(self, source: str) -> None:
        """Route ``source`` to this output, or clear it when ``None``."""
        target = label_to_source(source)
        await self.coordinator.device.set_output_source(self._output, target)
        await self.coordinator.async_request_refresh()
