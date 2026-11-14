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
| `stop()`, then `start()` | Abort every client socket and stop listening, then listen again on the same ports |
| `silent = True` | Accept connections and read commands, but send nothing |
| `chunk_delay`, `chunk_size` | Stream replies in `chunk_size` pieces with a pause between them |

Only recorded replies are exact. Write commands were never sent to the real
device, so the simulator answers them with a guessed `[SUCCESS]` and changes no
state; STATUS, UPTIME and TEMP always return the recorded values.

`test_fidelity.py` checks the simulator against the captures.
`test_known_bugs.py` and `tests/components/blustream/test_sim_reconnect.py` (for
Home Assistant) hold the known-bug tests. Open bugs are strict `xfail` tests: they
assert the correct behaviour, so a fix makes them pass and the fix then removes
the marker. Each reason names its issue:

- **B1 ([#107](https://github.com/caidurbin/blustream/issues/107)):** an
  `[ERROR]` reply raises `CommandError` carrying the device's message. Its
  tests carry no marker. They force the rejection with `reject_next()`,
  because no valid write command was recorded failing.
- **B2 ([#108](https://github.com/caidurbin/blustream/issues/108)):** when the
  device closes or resets the socket, the client marks itself disconnected and
  the next `connect()` opens a new link. The B2 tests, in the library and in
  Home Assistant, carry no marker.
- **[#109](https://github.com/caidurbin/blustream/issues/109):** every reply is
  broadcast to every client, so a reader takes another client's reply that
  lands first as its own.
- **[#110](https://github.com/caidurbin/blustream/issues/110):** a corrupted
  STATUS dump (binary frames mixed in, bytes missing) is accepted by the client
  and by both STATUS parsers instead of being rejected.

The Control4 command-queue risk (sends interleaving with a streaming STATUS,
and a stall when the device goes silent) is not covered yet: the driver's
specs run under busted on Lua 5.1, which this simulator doesn't drive. The
`chunk_delay` and `silent` switches are there for that work.
