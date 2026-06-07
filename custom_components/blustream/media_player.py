"""Media player platform for the Blustream integration — output routing.

Each of the DMP168's 8 outputs is modelled as a single-source
``media_player`` exposing ``SELECT_SOURCE`` (ADR 0014). ``source_list`` is
the device-native ``None`` target plus the 16 inputs and 8 buses; selecting a
source routes it, and selecting ``None`` clears the route. One input feeds
several outputs by targeting several output entities (or an area/label) in a
single ``media_player.select_source`` action.

Each output also exposes volume and mute (``VOLUME_SET | VOLUME_STEP |
VOLUME_MUTE``). The device keeps independent L/R volume and mute; HA's
single-value model collapses them with the L channel canonical (ADR 0014):
``volume_level`` follows L, ``is_volume_muted`` is true only when *both*
channels are muted, and writes always target both channels (``channel=LR``).
When the channels diverge — settable from the device's own web GUI — the raw
per-channel values are surfaced in ``extra_state_attributes`` so the
collapse stays lossless.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from blustream.devices.dmp168.models import (
    SOURCE_BUS,
    OutputSettings,
    OutputSource,
)

from .const import BUS_COUNT, INPUT_COUNT, OUTPUT_COUNT
from .coordinator import BlustreamConfigEntry, BlustreamCoordinator
from .device import build_device_info

# The device steps output volume in 1% increments via its native relative
# ``+``/``-`` commands; HA expresses the step as a 0-1 fraction.
_VOLUME_STEP = 0.01
# The device works in whole-percent volume (0-100); HA works in a 0-1 float.
_VOLUME_SCALE = 100

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
        return OutputSource.for_input(int(label[len(_INPUT_PREFIX) :]))
    if label.startswith(_BUS_PREFIX):
        return OutputSource.for_bus(int(label[len(_BUS_PREFIX) :]))
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
    _attr_supported_features = (
        MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
    )
    _attr_source_list = SOURCE_LIST
    _attr_volume_step = _VOLUME_STEP

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
        self._attr_device_info = build_device_info(entry, coordinator)

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

    @property
    def _settings(self) -> OutputSettings | None:
        """This output's settings row from the latest poll, if present."""
        status = self.coordinator.data
        if status is None:
            return None
        for row in status.output_settings:
            if row.output == self._output:
                return row
        return None

    @property
    def volume_level(self) -> float | None:
        """The output level as a 0-1 fraction, from the canonical L channel."""
        settings = self._settings
        if settings is None:
            return None
        return settings.volume_pct_l / _VOLUME_SCALE

    @property
    def is_volume_muted(self) -> bool | None:
        """Muted only when *both* channels are muted (ADR 0014 collapse)."""
        settings = self._settings
        if settings is None:
            return None
        return settings.mute_l and settings.mute_r

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Surface per-channel state only when L and R diverge.

        ``volume_level``/``is_volume_muted`` collapse to the L channel; when
        the channels disagree (settable from the device web GUI) the raw
        ``volume_left``/``volume_right`` fractions and ``channel_locked`` flag
        keep the collapse lossless. Equal channels add no noise.
        """
        settings = self._settings
        if settings is None:
            return None
        diverged = (
            settings.volume_pct_l != settings.volume_pct_r
            or settings.mute_l != settings.mute_r
        )
        if not diverged:
            return None
        return {
            "volume_left": settings.volume_pct_l / _VOLUME_SCALE,
            "volume_right": settings.volume_pct_r / _VOLUME_SCALE,
            "channel_locked": settings.lock,
        }

    async def async_set_volume_level(self, volume: float) -> None:
        """Set both channels to the same absolute level (0-1 fraction)."""
        await self.coordinator.device.set_output_volume(
            self._output, round(volume * _VOLUME_SCALE), channel="LR"
        )
        await self.coordinator.async_request_refresh()

    async def async_volume_up(self) -> None:
        """Step both channels up via the device's native relative command."""
        await self.coordinator.device.set_output_volume(
            self._output, "+", channel="LR"
        )
        await self.coordinator.async_request_refresh()

    async def async_volume_down(self) -> None:
        """Step both channels down via the device's native relative command."""
        await self.coordinator.device.set_output_volume(
            self._output, "-", channel="LR"
        )
        await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute both channels together."""
        await self.coordinator.device.set_output_mute(
            self._output, mute, channel="LR"
        )
        await self.coordinator.async_request_refresh()
