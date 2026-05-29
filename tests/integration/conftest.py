"""Integration-suite fixtures and the env-var skip gate.

The whole ``tests/integration/`` package is skipped unless
``BLUSTREAM_INTEGRATION_HOST`` is set. Default CI keeps the env var unset
so unit-test runs collect-and-skip these tests cleanly; running against
real hardware happens in a separate workflow / a developer's local shell.
See ``tests/integration/README.md``.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from blustream.devices.dmp168.device import DMP168

INTEGRATION_HOST_ENV = "BLUSTREAM_INTEGRATION_HOST"
INTEGRATION_PORT_ENV = "BLUSTREAM_INTEGRATION_PORT"
DEFAULT_INTEGRATION_PORT = 23


def _integration_host() -> str | None:
    return os.environ.get(INTEGRATION_HOST_ENV)


def _integration_port() -> int:
    return int(os.environ.get(INTEGRATION_PORT_ENV, str(DEFAULT_INTEGRATION_PORT)))


@pytest.fixture(autouse=True)
def _require_integration_host() -> None:
    """Skip every test in this package unless a live-device host is configured.

    Autouse keeps the gate per-test (rather than per-collection) so a partial
    matrix of env vars still produces clear, individual skip reasons in
    ``pytest -v`` output.
    """
    if not _integration_host():
        pytest.skip(
            f"{INTEGRATION_HOST_ENV} not set; integration suite requires a live "
            f"DMP168. See tests/integration/README.md."
        )


@pytest.fixture
def host() -> str:
    host = _integration_host()
    assert host, "skip gate should have fired before this fixture is used"
    return host


@pytest.fixture
def port() -> int:
    return _integration_port()


@pytest_asyncio.fixture
async def device(host: str, port: int) -> AsyncIterator[DMP168]:
    """Yield one connected DMP168 for the duration of a test."""
    dmp = DMP168(host=host, port=port)
    await dmp.connect()
    try:
        yield dmp
    finally:
        await dmp.disconnect()
