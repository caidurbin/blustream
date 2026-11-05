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
| `chunk_delay`, `chunk_size` | Stream replies in `chunk_size` pieces with a pause between them |

Only recorded replies are exact. Write commands were never sent to the real
device, so the simulator answers them with a guessed `[SUCCESS]` and changes no
state; STATUS, UPTIME and TEMP always return the recorded values.

`test_fidelity.py` checks the simulator against the captures.
`test_known_bugs.py` (and `tests/components/blustream/test_sim_reconnect.py`
for Home Assistant) reproduce known client bugs as strict `xfail` tests: they
assert the correct behaviour, so a fix makes them pass and the fix then removes
the marker. The bug labels in their reasons:

- **B1:** an `[ERROR]` reply is returned as a normal response, so a rejected
  command is reported as a success. The test forces the rejection with
  `reject_next()`, because no valid write command was recorded failing.
- **B2:** when the device closes the socket, `is_connected` stays True, so
  nothing reconnects and every later poll fails.

The Control4 command-queue risk (sends interleaving with a streaming STATUS,
and a stall when the device goes silent) is not covered yet: the driver's
specs run under busted on Lua 5.1, which this simulator doesn't drive. The
`chunk_delay` and `silent` switches are there for that work.
