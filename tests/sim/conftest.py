"""Fixtures shared by the simulator tests."""

import pytest

from tests.sim.matrix import SimulatedMatrix


@pytest.fixture
async def sim():
    async with SimulatedMatrix() as matrix:
        yield matrix
