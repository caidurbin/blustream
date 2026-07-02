---
applies_to: [c4-driver]
date: 2026-05-06
---

# Control4 driver: routing-only scope

The DMP168 has a large feature surface (DSP, EQ, ducking, presets, audio sensing, etc.). The Control4 driver exposes only audio routing — setup-time concerns (DSP, EQ) stay in the device's web GUI; runtime concerns beyond routing (volume, mute) are owned by other devices in the audio chain. This scope decision is specific to the Control4 driver: the Python library and CLI expose the full protocol surface, and the HA integration exposes more than routing — see ADR 0014.
