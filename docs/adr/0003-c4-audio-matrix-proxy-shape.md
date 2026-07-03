---
applies_to: [c4-driver]
date: 2026-05-06
---

# Control4 driver: audio matrix proxy shape

The driver declares the `audio_matrix_switch` proxy with **16 stereo input bindings + 8 stereo output bindings** (channel-lock always on; bus channels and L/R-independence are hidden, available via the device's web GUI for advanced setup-time use). **No `volume` capability**: the driver treats the matrix as a routing fabric and assumes a downstream amplifier (with its own Control4 driver) owns user-facing volume — the typical topology for this device class; with volume undeclared, Composer Pro's Room model routes volume requests to the amplifier as expected. **No `has_power` capability**: Control4 cannot send `OFF` to the matrix, so no Room-Off macro can silence the entire house's audio. Power is lifecycle-managed internally — `PON` / `STANDBY 0` / `AUTO STB 0` / `STATUS` are issued on every connect/reconnect.
