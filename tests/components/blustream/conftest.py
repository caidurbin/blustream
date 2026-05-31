"""Pytest fixtures for the Blustream HA integration tests.

These tests require ``pytest-homeassistant-custom-component``; the whole
package is skipped at collection time when it isn't installed (e.g. the
library-only CI lane). The dedicated ``test-ha.yml`` workflow installs
PHCC and runs this directory.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.components.sensor import SensorDeviceClass  # noqa: E402

# ``SensorDeviceClass.UPTIME`` was introduced in HA 2026.5.0 (core PR
# #164266), shipped by pytest-homeassistant-custom-component 0.13.329+,
# which requires Python 3.14. PHCC pins one HA version per release, so a
# lane on an older PHCC/HA (e.g. PHCC <=0.13.316 -> HA 2026.2.3, the last
# Python-3.13 HA) lacks the symbol and cannot import the integration's
# sensor module at collection time. Skip the whole directory via
# ``collect_ignore_glob`` -- a pytest hook that runs before any test file
# is imported -- rather than letting collection blow up. test-ha.yml pins
# PHCC 0.13.329+ on Python 3.14, so this guard is a no-op in CI; it only
# trips in a mismatched local/older environment.
if not hasattr(SensorDeviceClass, "UPTIME"):
    collect_ignore_glob = ["test_*.py"]

from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.blustream.const import DOMAIN  # noqa: E402


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):  # noqa: ARG001
    """Auto-enable custom_components/ resolution for every test."""
    yield


@pytest.fixture
def mock_device() -> Generator[MagicMock, None, None]:
    """Patch DMP168 with a MagicMock so no network I/O happens."""
    device = MagicMock()
    device.connect = AsyncMock()
    device.disconnect = AsyncMock()
    device.get_uptime = AsyncMock(return_value=timedelta(days=3, hours=2, minutes=1))
    device.is_connected = True
    with (
        patch(
            "custom_components.blustream.DMP168",
            return_value=device,
        ),
        patch(
            "custom_components.blustream.config_flow.DMP168",
            return_value=device,
        ),
    ):
        yield device


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A MAC-bearing config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test DMP168",
        data={
            "host": "192.0.2.10",
            "port": 23,
            "name": "Test DMP168",
            "mac": "34:d0:b8:21:22:33",
        },
        unique_id="34:d0:b8:21:22:33",
    )


@pytest.fixture
def mock_config_entry_no_mac() -> MockConfigEntry:
    """A MAC-less config entry (entry-id identity tier)."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="192.0.2.11",
        data={
            "host": "192.0.2.11",
            "port": 23,
        },
        unique_id=None,
    )
