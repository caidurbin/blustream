# Changelog

All notable changes to the `blustream` Python library and CLI are documented
here. The format is based on [Keep a Changelog](https://keepachangelog.com/),
and the project follows the `v*` release lane published to PyPI (see
`.github/workflows/release-pypi.yml`).

## [Unreleased]

### Added

- `DMP168.get_help()` and a `help` CLI command — send the device's `?/HELP`
  and return its raw command listing verbatim. The device's HELP is the
  authoritative record of the commands its firmware supports; the published
  API doc and user manual have been observed to drift from it (the REVA1
  manual mislabels `REBOOT` as "Set System Key Control", whereas the live
  V1.5.0 firmware reports "Set System Reboot" — surfaced in #78). HELP emits
  no `[SUCCESS]`/`[ERROR]` marker, so it is framed on the listing's `=`-only
  footer. Defined in `spec/protocol.yaml` and covered by the shared formatter
  vectors like every other command.

### Fixed

- A command the device answers with an `[ERROR]` line now raises
  `CommandError` carrying the device's message. The public methods used to
  return that text as a normal response, so a rejected command looked like a
  success. This includes `DMP168.get_preset_status()` on an empty preset,
  which the device answers with `[ERROR]Preset N config status null.` (#107)
- The client reconnects after the device drops the link (#108). When the
  device closes or resets the socket, `TCPConnection` closes the transport,
  clears its reader, writer and buffer, and reports itself disconnected. The
  command that finds the dead link fails; the next `connect()` (which the
  Home Assistant coordinator calls on its next poll) opens a new link. A
  connect the device closes during the welcome banner now fails with
  `ConnectionError` instead of reporting success on a dead link.
- `DMP168.get_status()`, `DMP168Parser.parse_status()` and
  `status_parser.parse()` raise `ParseError` on a corrupted STATUS dump
  instead of returning its values (#110). A dump is corrupted when it holds a
  character outside printable ASCII, tab, CR and LF (the device's interleaved
  `AA 54 …` binary frames), or an `In<n>`/`Out<n>` row that doesn't match a
  clean row shape. Truncated rows such as `In1 On 50` or `Out1 L` with no
  source now raise too, where `parse_status` used to skip them. The Home
  Assistant coordinator treats the error as a failed poll.

## [0.3.0] - 2026-06-07

Typed output sources and output settings in `SystemStatus`, so a single
`get_status()` fully describes round-one output state (issue #63, PRD #62).

### Added

- `OutputSource` model distinguishing an **input** from a **bus**
  (`kind` ∈ {`input`, `bus`} + `number`); `None` continues to mean an
  unrouted output. The device's unified 1-24 column addressing
  (1-16 = inputs, 17-24 = buses) stays inside the library (ADR 0011).
- `OutputSettings` dataclass (per-output `volume_pct_l/r`, `mute_l/r`,
  `lock`) parsed from the `Output Settings Status` section and exposed as
  `SystemStatus.output_settings`.
- `DMP168.set_output_source(output, source_or_None)` — routes an input or
  bus via the `route` wire command, or clears the route via `output_remove`
  when given `None` (ADR 0014, single-source-per-output).
- STATUS parser now reads `In<n>`, `Bus<n>`, and `None` source tokens in the
  Matrix Config section; bus-routed outputs were previously dropped to
  `None`.

### Changed

- **Breaking:** `OutputRouting.from_input: Optional[int]` is replaced by
  `OutputRouting.source: Optional[OutputSource]`. The CLI `--json` status
  surface now emits a typed `source` object (`{"kind", "number"}` or `null`)
  per routing row and an `output_settings` array.

[0.3.0]: https://github.com/caidurbin/blustream/releases/tag/v0.3.0
