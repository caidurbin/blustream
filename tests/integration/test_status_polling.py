"""STATUS polling reflects out-of-band routing changes.

The Control4 driver assumes that routing changes made outside the driver
(matrix web GUI, the Python CLI, a future Home Assistant integration) show
up in the next ``STATUS`` poll. This test simulates an out-of-band change
by opening a *second* TCP client to the matrix and issuing a route from
that connection, then asserts the *first* client's STATUS observes it.

Two clients are an honest stand-in for the web GUI: the matrix has no
notion of "which client made this change", so any concurrent client that
mutates state and is observed via STATUS exercises the same code path the
web GUI does on the device side.
"""

from __future__ import annotations

import asyncio

import pytest

from blustream.devices.dmp168.device import DMP168
from tests.integration.conftest import output_l_input

TEST_OUTPUT = 7
TEST_INPUT = 14
ALT_INPUT = 13

# Time to allow the device to apply the route from the "external" client and
# settle before the "driver" client polls STATUS. Real polling intervals run
# at 15 s; a few hundred ms is plenty for the apply-and-observe gap.
SETTLE_DELAY_S = 0.5


@pytest.mark.asyncio
async def test_status_reflects_external_routing_change(host: str, port: int) -> None:
    driver = DMP168(host=host, port=port)
    external = DMP168(host=host, port=port)

    await driver.connect()
    await external.connect()
    try:
        baseline = await driver.execute_command("status")
        prior_input = output_l_input(baseline, TEST_OUTPUT)
        target_input = ALT_INPUT if prior_input == TEST_INPUT else TEST_INPUT

        await external.route_input_to_output(
            input_ch=target_input, output=TEST_OUTPUT
        )
        try:
            await asyncio.sleep(SETTLE_DELAY_S)
            seen = await driver.execute_command("status")
            observed = output_l_input(seen, TEST_OUTPUT)
            assert observed == target_input, (
                f"driver STATUS did not see external route change: "
                f"expected output {TEST_OUTPUT} from input {target_input}, "
                f"got {observed}"
            )
        finally:
            if prior_input is not None and prior_input != target_input:
                await driver.route_input_to_output(
                    input_ch=prior_input, output=TEST_OUTPUT
                )
            elif prior_input is None:
                await driver.remove_input_from_output(
                    output=TEST_OUTPUT, input_ch=target_input
                )
    finally:
        await driver.disconnect()
        await external.disconnect()
