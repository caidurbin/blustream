"""Fixtures shared by the simulator tests."""

import pytest

from blustream.connection.tcp import TCPConnection
from blustream.devices.dmp168.device import DMP168
from tests.sim.matrix import SimulatedMatrix

# Keeps connect() quick on port 8000 and on a silent device, which send no banner.
BANNER_TIMEOUT = 0.1


@pytest.fixture
async def sim():
    async with SimulatedMatrix() as matrix:
        yield matrix


@pytest.fixture(params=["telnet", "raw"])
def port(request, sim) -> int:
    """Run each test once against port 23 and once against port 8000."""
    return sim.telnet_port if request.param == "telnet" else sim.raw_port


@pytest.fixture
async def device(sim, port):
    """A connected DMP168 on ``port`` of the simulator."""
    connection = TCPConnection(sim.host, port, banner_timeout=BANNER_TIMEOUT)
    dmp = DMP168(sim.host, port, connection=connection)
    await dmp.connect()
    yield dmp
    await dmp.disconnect()
