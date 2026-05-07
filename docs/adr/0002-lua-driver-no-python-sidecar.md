---
applies_to: [c4-driver]
---

# Pure-Lua Control4 driver, no Python sidecar

The Control4 driver is a fresh Lua port of the protocol layer, not a sidecar that shells out to the existing Python library. The protocol surface is small enough that a Lua implementation is cheaper than the operational complexity of a sidecar — separate process lifecycle, no Composer Lua-console debugging, additional latency. The Python library remains the runtime for the CLI and the future HA integration; the Lua driver is independent.
