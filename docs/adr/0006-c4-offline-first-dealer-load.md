---
applies_to: [c4-driver]
date: 2026-05-06
---

# Control4 driver: offline-first development with dealer-load integration

With Composer Pro acquisition uncertain, the dev loop is optimized around the slow dealer-load cycle: VS Code + `luacheck`, a local Lua interpreter for unit tests, `snap-one/drivers-driverpackager` for offline `.c4z` builds on macOS, and `--allowexecute` builds during dev so the dealer can paste hot patches into the Composer Lua console without a fresh `.c4z` round-trip. A `Debug Mode` Property gates verbose `print()` output as the primary debug channel (DriverEditor's debug port is broken on OS 3, so the dealer copies Lua-window output back to the developer). No dedicated dev controller at this stage — re-evaluate once Composer Pro arrives and Virtual Director becomes the fast loop.
