# Blustream — domain glossary

Canonical vocabulary for the Blustream project. Update inline as new terms
are resolved during design or grilling sessions. Implementation details
belong in ADRs, not here.

## HA integration POC

The first published version of the Home Assistant integration is a
**"gold-tier POC"**: it exposes a single entity (the uptime sensor)
but every other surface — config flow, discovery, reconfiguration,
diagnostics, repair issues, translations, device registry — is built
to the HA Integration Quality Scale Gold standard from day one. The
narrowness is in entity *count*, not in production-quality
scaffolding. Adding further entities (volume, mute, routing, presets)
in later versions is purely additive — no scaffolding catch-up
required.

## Uptime

The elapsed duration since the device last booted.

The DMP168 protocol reports uptime as a `DDDD:HH:MM:SS` string from the
`UPTIME` command (also embedded in `STATUS`). The Python library exposes it
both unmodified — as a string via `get_uptime_raw()` (the *uptime duration*) —
and parsed into a `timedelta` via `get_uptime()`.

The Home Assistant integration derives a **boot time** from uptime
(`now - parsed_uptime`) and surfaces *that* as the entity value, using
`SensorDeviceClass.UPTIME`. So in the HA surface, "the uptime sensor" reports
*when the device last booted*, not how long it has been up — even though the
sensor is conventionally named "uptime" both in HA's vocabulary and ours.

When discussing this in code or design: prefer "boot time" for the derived
datetime, "uptime duration" for the raw `DDDD:HH:MM:SS` string. Reserve
"uptime" alone for the user-facing concept (which collapses both).

## Device identity

The DMP168 has a MAC address (shown on the web GUI's Information page as
e.g. `34:D0:B8:27:2D:96`) and a user-configurable mDNS domain name
(default: `dmp168.local`). **Neither is reachable through the device's
TCP command protocol** — the `NET …` commands are setters only, `STATUS`
emits no identity fields beyond model and firmware, and a live-hardware
probe of 52 undocumented-command candidates (firmware MCU 1.5.0 / Web
1.4.0 / DSP 1.5.9) confirmed the device has no hidden identity getter.
The device's `HELP` output matches the published API doc verbatim.

The MAC is reachable through two non-protocol channels:

1. **DHCP discovery** — the device requests DHCP leases with its
   real MAC. HA's `dhcp` discovery surface delivers `DhcpServiceInfo`
   with `macaddress`, hostname, and IP. This is the canonical
   programmatic identity path. The Blustream MAC prefix is the 28-bit
   IEEE MA-M block `34:D0:B8:2*` (NOT the full 24-bit OUI `34:D0:B8`,
   which is the parent IEEE MA-M block shared with other vendors).
2. **HTTP scrape of the web GUI Information page** — works but
   requires admin auth, is brittle to firmware UI changes, and is
   considered a code-review smell in HA core.

The default mDNS Domain Name is `DMP168` (fixed `dmp168.local`, not
MAC-derived), so two out-of-the-box units on one LAN collide on mDNS
until renamed. mDNS therefore serves as a discovery UX assist (find
the IP automatically) but **cannot** carry stable per-device identity.

## Source

The signal feeding an output. Each output is fed by **exactly one** source at
a time, expressed as a stereo pair (L and R move together). A source is one of
the 16 **inputs**, one of the 8 **buses**, or **None** — the device's own term
for an output with no source routed (STATUS reports `Out1 L  None`). "None" is
a first-class, selectable source value, not an absence of state: selecting it
clears the output's route.

The matrix is therefore single-select *per output*, not many-to-one:
- One input (or bus) may feed **multiple** outputs simultaneously.
- Multiple inputs may **not** feed one output directly — that requires routing
  them into a bus first (see *Bus*). This is a hardware constraint of the
  DMP168 (User Manual p.7), not an integration choice.

## Routing

Selecting which source feeds an output. The HA integration models each output
as a `media_player` entity exposing `SELECT_SOURCE`: `source` is the single
currently-routed source, `source_list` is the available sources — **None** plus
the 16 inputs and 8 buses — and routing is performed via the standard
`media_player.select_source` action. Selecting **None** clears the output's
route. One input is routed to several outputs by targeting several output
entities (or an area/label) in a single `select_source` call.

## Bus

One of 8 internal mix buses. A bus sums multiple inputs into a single signal
that can then be selected as an output's source — the device's only path to
"multiple inputs feeding one output." Buses are first-class mixers with their
own volume/mute (User Manual p.8).

The integration lets a bus be **selected** as an output source, but **defining
what a bus mixes** (its constituent inputs, bus volume/mute) is out of scope
for this round — bus contents are configured on the device's own web GUI.
