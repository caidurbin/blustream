# Changelog

All notable changes to the `blustream` Python library and CLI are documented
here. The format is based on [Keep a Changelog](https://keepachangelog.com/),
and the project follows the `v*` release lane published to PyPI (see
`.github/workflows/release-pypi.yml`).

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
