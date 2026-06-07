"""DataUpdateCoordinator for the Blustream integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from blustream import DMP168
from blustream.base.exceptions import (
    CommandError as BlustreamCommandError,
)
from blustream.base.exceptions import (
    ConnectionError as BlustreamConnectionError,
)
from blustream.base.exceptions import (
    ParseError as BlustreamParseError,
)
from blustream.base.exceptions import (
    TimeoutError as BlustreamTimeoutError,
)
from blustream.devices.dmp168.models import SystemStatus

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

# HA's modern idiom is PEP 695 ``type BlustreamConfigEntry = ConfigEntry[...]``
# (Python 3.12+, which the integration runtime targets). The library's ruff
# target stays at py39 for the wider package, so the alias is declared as a
# plain subscript assignment instead — semantically equivalent to the type
# statement, but parseable under the older target.
BlustreamConfigEntry = ConfigEntry["BlustreamCoordinator"]


class BlustreamCoordinator(DataUpdateCoordinator[SystemStatus]):
    """Polls a single DMP168 for its full system status.

    A single ``get_status()`` per cycle drives every entity (output routing,
    uptime, …); the typed :class:`SystemStatus` is exposed on
    ``coordinator.data`` (issue #64, ADR 0014).
    """

    config_entry: BlustreamConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: BlustreamConfigEntry,
        device: DMP168,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.device = device

    async def _async_update_data(self) -> SystemStatus:
        try:
            if not self.device.is_connected:
                await self.device.connect()
            return await self.device.get_status()
        except (
            BlustreamConnectionError,
            BlustreamTimeoutError,
            BlustreamParseError,
            BlustreamCommandError,
            ConnectionError,
            TimeoutError,
        ) as err:
            raise UpdateFailed(str(err)) from err
