# Blustream — domain glossary

Canonical vocabulary for the Blustream project. Implementation details
belong in ADRs, not here.

## Language

**Uptime duration**:
The elapsed time since the device last booted, as reported by the device
(raw `DDDD:HH:MM:SS`).

**Boot time**:
The instant the device last booted, derived from uptime duration; the value
HA's uptime sensor reports.
_Avoid_: uptime (for the derived datetime)

**Source**:
The one signal feeding an output — an input, a bus, or None (the device's
own selectable no-route value). Normally a stereo pair; per-channel
divergence is possible via the web GUI (ADR 0014).
_Avoid_: channel, feed

**Routing**:
Selecting which source feeds an output; single-select per output. See
ADR 0014.
_Avoid_: switching, patching

**Bus**:
One of 8 internal mix buses summing multiple inputs into a single signal
selectable as an output's source. Defining what a bus mixes is configured
on the device's web GUI.

**Device identity**:
The MAC address is the unit's only stable identifier; it is unreachable
over the TCP command protocol and arrives via DHCP discovery or manual
entry, else the config-entry id. See
[ADR 0010](docs/adr/0010-ha-integration-device-identity.md).
