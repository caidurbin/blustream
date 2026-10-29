# Simulated DMP168

`matrix.py` is a fake DMP168 for tests. It listens on two loopback ports and
answers with the exact bytes the real matrix sent during the read-only capture
in `tests/fixtures/live/2026-10-29/` (see `FINDINGS.md` there).

```python
from tests.sim import SimulatedMatrix

async with SimulatedMatrix() as sim:
    device = DMP168(sim.host, sim.telnet_port)  # or sim.raw_port
```

`telnet_port` plays the device's port 23 (IAC negotiation, banner, echo and
`DMP168> ` prompt) and `raw_port` its port 8000 (bare replies). Like the real
device, every reply and every port-23 banner goes to every open client on both
ports.

Fault switches:

| Call | Effect |
|---|---|
| `reject_next(n, reply)` | Answer the next `n` commands with an `[ERROR]` reply |
| `corrupt_next_status(n)` | Answer the next `n` STATUS requests with the corrupted broadcast dump from the capture |
| `interleave_foreign(cmd)` | Broadcast another client's reply to `cmd` just before the next reply |
| `broadcast_foreign(cmd)` | Broadcast another client's reply to `cmd` now |
| `drop_connections()` | Abort every client socket; the listeners stay up |
| `silent = True` | Accept connections and read commands, but send nothing |
| `chunk_size`, `chunk_delay` | Stream replies in small, slow chunks |

Only recorded replies are exact. Write commands were never sent to the real
device, so the simulator answers them with a guessed `[SUCCESS]` and changes no
state; STATUS, UPTIME and TEMP always return the recorded values.

`test_fidelity.py` checks the simulator against the captures.
`test_known_bugs.py` (and `tests/components/blustream/test_sim_reconnect.py`
for Home Assistant) reproduce known client bugs as strict `xfail` tests: they
assert the correct behaviour, so a fix makes them pass and the fix then removes
the marker.
