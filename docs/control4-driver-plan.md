# Control4 Driver for Blustream DMP168 — Implementation Plan

**Status:** Draft. Synthesis of design conversation, 2026-05-06.
**Author:** Cai Durbin (`name@example.com`)
**Scope:** Add a Control4 driver to the existing Python project, restructured as a monorepo, with a codegen-driven protocol layer that prevents drift across implementations. A Home Assistant integration is reserved as future work but not implemented in this phase.

This document captures architectural decisions, empirical findings about the device, the implementation roadmap, and known open items. Several individual decisions in this document are good candidates for promotion to standalone ADRs under `docs/adr/` once that directory is established.

---

## 1. Goals and non-goals

### 1.1 Goals (v1)

- A Control4 driver (`.c4z`) for the Blustream DMP168 that exposes audio routing only.
- A monorepo housing three things: the Python library/CLI, the Control4 Lua driver, and a planned-but-unbuilt Home Assistant integration directory.
- A codegen pipeline that emits protocol primitives (formatters, validators, constants) into both Python and Lua from a single YAML spec.
- A shared test vector format that both implementations exercise, with CI gates that catch drift mechanically.
- Public open source release on GitHub, PyPI, and (when the HA integration ships) HACS.

### 1.2 Non-goals (v1)

- Volume, mute, or power capability on the Control4 matrix proxy. The downstream amplifier owns user-facing volume/mute in the user's topology; matrix power is managed internally by the driver, not exposed as a proxy capability.
- DSP, EQ, ducking, audio sensing, contact closures, presets, output grouping. These remain accessible via the device's web GUI for setup-time configuration.
- Internal Bus mixing channels exposed to Control4 as bindable inputs.
- Independent L/R channel control. Channel-lock is always on.
- Snap One driver certification or commercial distribution.
- A working Home Assistant integration. The directory and design space are reserved; implementation is deferred.
- Other Blustream device support beyond the DMP168. Architecture admits future devices without rework.

---

## 2. Naming

The project is renamed from `bluestream` to **`blustream`** to match the manufacturer's brand and improve discoverability in HACS, PyPI, and GitHub search. The rename touches:

- Repository name: `caidurbin/bluestream` → `caidurbin/blustream` (GitHub redirects from the old name automatically).
- Python package name: `bluestream` → `blustream`.
- All Python imports across `bluestream/`, `tests/`, and `main.py`.
- `pyproject.toml`, `setup.py`, `package.json` package metadata.
- Future HA integration domain: `blustream`.
- Future `.c4z` driver name and identifier strings.

The rename should be done as one mechanical commit before any other work in this plan begins.

---

## 3. Distribution

- **License:** Apache 2.0.
- **GitHub:** Public repository.
- **PyPI:** Python library published as `blustream`. Tags `v*` trigger PyPI release.
- **HACS:** Future. Structure (`custom_components/blustream/` + `hacs.json` at repo root) is established now even though the integration code is deferred.
- **Control4 driver:** Unencrypted `.c4z` artifact attached to GitHub releases. Tags `c4-v*` trigger driver build/release. Dealer-installable; not submitted to drivercentral.io or Snap One certification at this stage.
- **Independent versioning:** PyPI library, `.c4z` driver, and (eventually) HACS integration cut releases independently. The shared protocol spec under `spec/` is the coordination point.

---

## 4. High-level architecture

```
                                   ┌─────────────────────────────┐
                                   │   spec/protocol.yaml        │  ← single source of truth
                                   │   spec/vectors/*.yaml       │  ← shared test vectors
                                   └──────────────┬──────────────┘
                                                  │
                       ┌──────────────────────────┼──────────────────────────┐
                       │ codegen                  │ codegen                  │ humans
                       ▼                          ▼                          ▼
            ┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
            │  Python: generated   │   │  Lua: generated      │   │  Spec doc            │
            │  formatters,         │   │  formatters,         │   │  (driver-protocol.md)│
            │  validators,         │   │  validators,         │   │  + empirical         │
            │  constants           │   │  constants           │   │  findings            │
            └──────────┬───────────┘   └──────────┬───────────┘   └──────────────────────┘
                       │                          │
                       │ imported by              │ embedded in
                       ▼                          ▼
            ┌──────────────────────┐   ┌──────────────────────┐
            │  blustream Python    │   │  control4 Lua driver │
            │  library             │   │  (.c4z)              │
            │  (PyPI: blustream)   │   │                      │
            └──────────┬───────────┘   └──────────────────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
        ┌─────────┐      ┌──────────────────────┐
        │  CLI    │      │  HA integration      │
        │         │      │  (future, reserved)  │
        └─────────┘      └──────────────────────┘
```

Three runtimes (Python asyncio, Lua-in-DriverWorks, future HA Python) share a single protocol contract via codegen. The protocol primitives — wire formatters, range validators, constants like default port and line terminator — are mechanically generated. Higher-level concerns (asyncio connection handling, Control4 proxy lifecycle, HA `DataUpdateCoordinator`) are environment-specific and hand-written per runtime.

---

## 5. Repo layout (target)

```
blustream/                             ← repo root
├── CONTEXT.md                         ← project domain context (per AGENTS.md)
├── AGENTS.md, CLAUDE.md               ← agent instructions (existing)
├── README.md
├── LICENSE                            ← Apache 2.0
├── pyproject.toml                     ← Python lib + CLI entry point
├── hacs.json                          ← HACS integration metadata (forward-looking)
├── .github/workflows/                 ← CI: codegen-clean, pytest, lua tests, c4z build
│
├── blustream/                         ← Python library (formerly bluestream/)
│   ├── base/                          ← existing
│   ├── connection/                    ← existing
│   ├── devices/
│   │   └── dmp168/
│   │       ├── __init__.py
│   │       ├── device.py              ← high-level device API (hand-written)
│   │       └── _generated.py          ← protocol primitives (codegen output, committed)
│   └── cli/                           ← existing CLI lives here
│
├── control4/                          ← Lua driver(s)
│   └── dmp168/
│       ├── src/
│       │   ├── driver.xml             ← proxy/capabilities declaration
│       │   ├── driver.lua             ← main driver logic (hand-written)
│       │   └── generated.lua          ← protocol primitives (codegen output, committed)
│       ├── tests/                     ← Lua unit tests
│       │   └── run.lua
│       ├── manifest.xml               ← DriverPackager input
│       └── README.md                  ← dealer install + smoke test instructions
│
├── custom_components/                 ← HA integration (deferred; directory reserved)
│   └── blustream/
│       ├── manifest.json              ← will require ["blustream==X.Y.Z"]
│       └── README.md                  ← "deferred — see plan doc"
│
├── spec/                              ← protocol source of truth
│   ├── protocol.yaml                  ← the spec itself
│   ├── codegen/
│   │   ├── emit_python.py
│   │   ├── emit_lua.py
│   │   └── templates/
│   └── vectors/
│       ├── formatters.yaml
│       ├── parsers.yaml
│       └── fixtures/                  ← captured STATUS responses, etc.
│
├── docs/
│   ├── control4-driver-plan.md        ← this document
│   ├── driver-protocol.md             ← human-readable subset spec + invariants
│   ├── adr/                           ← per AGENTS.md convention (to be created)
│   └── agents/                        ← existing
│
├── references/                        ← manufacturer docs (existing)
└── tests/                             ← Python tests (existing)
```

---

## 6. Architectural decisions (in order locked)

Decisions that cleared the ADR-worthy bar (hard-to-reverse + surprising + real trade-off) have been promoted to standalone ADRs under [`docs/adr/`](adr/). The rest stay here as the canonical record.

### D1. Access path: friendly dealer + planned own Composer Pro license

The user is a homeowner with a Control4 system and a friendly dealer who will load test builds. A path to acquiring a personal Composer Pro license through the dealer or via Snap One's Driver Development Partner program exists but has no concrete timeline. Iteration optimization assumes the slow dealer-load loop for now.

### D2. Driver scope: minimum viable matrix (routing only)

→ Promoted to [ADR-0001](adr/0001-c4-routing-only-scope.md).

### D3. Implementation strategy: pure Lua port (no Python sidecar)

→ Promoted to [ADR-0002](adr/0002-lua-driver-no-python-sidecar.md).

### D4. Proxy choice: `audio_matrix_switch`, no volume capability

→ Promoted to [ADR-0003](adr/0003-c4-audio-matrix-proxy-shape.md) (folded with D5 and D9).

### D5. Power: lifecycle-managed internally, no proxy capability

→ Promoted to [ADR-0003](adr/0003-c4-audio-matrix-proxy-shape.md) (folded with D4 and D9).

### D6. State feedback: periodic poll + on-demand refresh

→ Promoted to [ADR-0004](adr/0004-c4-polling-with-optimistic-lockout.md).

### D7. Connection: persistent TCP on port 8000

→ Promoted to [ADR-0005](adr/0005-c4-tcp-port-8000.md).

### D8. Discovery / IP setup: single Host property

A single `Host` property accepts either an IP address or a hostname. The driver hands the value directly to `C4:CreateNetworkConnection`; Control4's network stack handles IP-vs-hostname resolution natively. This admits both a static-IP setup (`192.0.2.176`) and the device's mDNS name (`dmp168.local`) with no special-casing in the Lua. A `Port` property defaults to 8000.

SDDP is not supported (Blustream does not implement Snap One's SDDP protocol; auto-discovery would have required a dedicated certification path).

### D9. Binding model: 16 stereo input + 8 stereo output, buses hidden

→ Promoted to [ADR-0003](adr/0003-c4-audio-matrix-proxy-shape.md) (folded with D4 and D5).

### D10. Iteration topology: offline-first, dealer-load for integration

→ Promoted to [ADR-0006](adr/0006-c4-offline-first-dealer-load.md).

### D11. Spec source of truth: codegen with shared vectors (Stages 1 and 2)

→ Promoted to [ADR-0007](adr/0007-codegen-with-shared-test-vectors.md).

### D12. Project name: `blustream` (rename from `bluestream`)

See section 2 above.

### D13. Distribution: public open source

→ Promoted to [ADR-0008](adr/0008-public-oss-no-snap-one-cert.md).

---

## 7. Empirical findings about the DMP168

These were discovered during the design conversation and are not in the manufacturer's references. They should be captured in `docs/driver-protocol.md` once that file exists; until then, they live here as the canonical record.

- **Two control listeners exist:** Telnet on port **23** (default) and TCP on port **8000** (default). Both expose the full command surface. Both are independently enable/disableable in the web GUI.
- **Port 23 performs telnet IAC negotiation** (sends `0xFF 0x03 / 0x01 / 0x01 / 0x00` on connect — DO/WILL escape codes). Clients must filter or speak telnet (`telnetlib3` works in Python).
- **Port 8000 does not perform telnet negotiation.** Raw text command/response. Cleaner to write a Lua driver against; chosen as the driver's default port (D7).
- **Concurrent multi-client TCP works.** Verified empirically: two clients on the same port (both 23 and 8000) and clients on different ports remain alive and responsive simultaneously. No multiplexer needed for parallel use of Control4 + future HA integration + CLI + web GUI.
- **`POFF` is documented as "Power Save State", not a hard power-off.** TCP listeners remain alive after `POFF`. The driver can detect off-state and issue `PON` over the network.
- **Firmware version drift in references:** the manufacturer manual is rev'd against firmware 1.1.0; current firmware on the test device is **1.5.0**. Command surface is consistent but minor diffs may exist; the driver pins firmware 1.5.0 as its tested baseline in `spec/protocol.yaml`.
- **mDNS:** the device publishes itself as `dmp168.local`. Suitable for the `Host` property as an alternative to a static IP (D8).
- **Default credentials (factory):** username `blustream`, password `********`. First admin login is forced to set a new password.


---

## 8. Codegen specification

### 8.1 Spec format (`spec/protocol.yaml`)

```yaml
device: dmp168
firmware_min: "1.5.0"

transport:
  default_port: 8000
  terminator: "\r\n"
  alternative_port:
    number: 23
    notes: telnet IAC negotiation; not used by driver

commands:
  power_on:
    wire: "PON"
    notes: idempotent; wakes from POFF/Sleep/Standby

  set_sleep_mode:
    wire: "STANDBY 0"
    notes: 0=Sleep (API alive), 1=Standby (API down)

  disable_auto_standby:
    wire: "AUTO STB 0"
    notes: persists across reboots

  status:
    wire: "STATUS"
    response: multi_section_text
    parser: hand_written

  route_input_to_output:
    wire: "OUT {output} FR {input}"
    params:
      output: { type: int, range: [1, 8] }
      input:  { type: int, range: [1, 16] }
```

### 8.2 Generators

- `spec/codegen/emit_python.py` reads `protocol.yaml`, emits `blustream/devices/dmp168/_generated.py` via Jinja2 templates.
- `spec/codegen/emit_lua.py` reads `protocol.yaml`, emits `control4/dmp168/src/generated.lua` via the same template structure adapted for Lua syntax.
- Both emitters write a header comment with the spec file's content hash so reviewers can verify lockstep.
- Generated files are committed to the repo (not gitignored) so they are visible in PRs.

### 8.3 Shared test vectors (`spec/vectors/formatters.yaml`)

```yaml
- name: route_basic
  op: route_input_to_output
  args: { output: 3, input: 5 }
  expect_wire: "OUT 3 FR 5\r\n"

- name: route_output_out_of_range
  op: route_input_to_output
  args: { output: 9, input: 5 }
  expect_error: true

- name: power_on_no_args
  op: power_on
  args: {}
  expect_wire: "PON\r\n"
```

Test runners on each side load this YAML, dispatch by `op`, and assert outcomes. The Lua side either consumes a YAML loader (`lyaml`) or, as a fallback, the codegen emits a `tests/lua_vectors.lua` table from the same source so vectors stay single-source.

### 8.4 CI invariant

The CI pipeline runs:

1. `python spec/codegen/emit_python.py`
2. `python spec/codegen/emit_lua.py`
3. `git diff --exit-code` — generated files must match committed.
4. `pytest tests/` — Python unit tests + shared formatter vectors.
5. `lua control4/dmp168/tests/run.lua` — Lua unit tests + shared formatter vectors.
6. `python -m driverpackager …` — `.c4z` builds cleanly.

Any of (3), (4), (5), or (6) failing blocks merge. This is the drift-detection contract.

---

## 9. Implementation roadmap

Phases are ordered by dependency. Each is a discrete unit that can land in its own PR.

### Phase 0 — Rename and restructure

- Rename `bluestream` → `blustream` across Python package, repo, imports, package metadata.
- Create top-level `spec/`, `control4/dmp168/`, `custom_components/blustream/` (stub), `docs/adr/` directories.
- Add `LICENSE` (Apache 2.0), `hacs.json` (forward-looking), `.github/workflows/ci.yml` skeleton.
- Move existing CLI entry point reference in `pyproject.toml` to use `blustream.cli.main`.

### Phase 1 — Codegen for Python only

- Author `spec/protocol.yaml` for the Scope A command surface.
- Implement `spec/codegen/emit_python.py` with Jinja2 templates.
- Generate `blustream/devices/dmp168/_generated.py`; refactor `blustream/devices/dmp168/device.py` to import from it (replacing any hand-written formatters).
- Write `spec/vectors/formatters.yaml`.
- Add pytest tests that load the vectors and exercise generated formatters.
- CI: codegen-clean check + pytest.

This phase already pays off: spec-driven Python with mechanical drift detection on the Python side, even before the Lua driver exists.

### Phase 2 — Lua driver MVP

- Implement `spec/codegen/emit_lua.py`.
- Generate `control4/dmp168/src/generated.lua`.
- Hand-write `control4/dmp168/src/driver.lua`:
  - `OnDriverInit` / `OnDriverLateInit`.
  - Connection state machine (D7).
  - Init sequence: `PON`, `STANDBY 0`, `AUTO STB 0`, `STATUS` (D5).
  - Polling loop (D6) — 15 s default, configurable Property.
  - `SELECT_AUDIO_DEVICE` proxy command handler — call generated `format_route_input_to_output`, send.
  - `STATUS` response parser, hand-written, for the Matrix Config Status section only.
  - Optimistic local update + 2 s command lockout.
  - Diff-and-notify when poll detects routing change.
  - `DEBUG_MODE` Property gating verbose logging (D10).
  - `Refresh Matrix State` Composer Action.
- Hand-write `control4/dmp168/src/driver.xml`:
  - `audio_matrix_switch` proxy.
  - 16 stereo input bindings + 8 stereo output bindings (D9).
  - No `has_volume`, no `has_mute`, no `has_power` capabilities (D4, D5).
  - Properties: `Host` (D8), `Port` (default 8000, D7), `Poll Interval (s)` (default 15, D6), `Debug Mode` (default off, D10).
- Build pipeline: `manifest.xml` for DriverPackager. Two build modes: dev (`-ae`) and release.
- `control4/dmp168/tests/run.lua` — load shared vectors, exercise generated formatters.
- `control4/dmp168/README.md` — dealer install instructions and smoke test script.
- CI: extend codegen-clean check to Lua; add Lua test run.

### Phase 3 — Live smoke test

- Build dev `.c4z` with `-ae`.
- Send to dealer; have them load into the live project.
- Run smoke test: route input 1 → output 1, verify audio path, watch `DEBUG_MODE` output.
- Iterate on bugs via the dealer-load loop, using Lua-console hot patches for fast fixes.
- Tag `c4-v0.1.0` once the smoke test passes consistently for ~1 week of normal use.

### Phase 4 — Public release

- Publish `blustream` to PyPI on `v*` tag.
- Cut GitHub release with the encrypted production `.c4z` attached on `c4-v*` tag.
- Update README with: install instructions for each component, dealer-facing C4 install steps, link to a getting-started guide.
- Optional: announce on c4forums.com (Driver Development category) and the Home Assistant community forum (forward-looking, even though HA integration is deferred).

### Phase 5 (deferred) — Home Assistant integration

Tracked as future work. When started:

- `media_player` platform, one entity per output zone, `source_list` populated from inputs.
- `DataUpdateCoordinator` polling at the same 15 s default as the Control4 driver, sharing the polling logic in spirit (separate code, same protocol via the `blustream` library).
- Config flow: host, port, optional name overrides for inputs/outputs.
- HACS submission once stable.

### Phase 6 (deferred) — Second Blustream device

When the user adds another Blustream device to the project, the codegen architecture pays off:

- Add a new `spec/<device>.yaml`.
- Re-run codegen; new generated files appear in `blustream/devices/<device>/` and `control4/<device>/src/`.
- Hand-write the new device's higher-level Python class and Lua driver.
- Both sides get formatters, validators, and constants for free.

---

## 10. Open items and deferred decisions

### 10.1 Tracked-as-future-work

- Home Assistant integration (Phase 5).
- Second-device support (Phase 6).
- Composer Action for `Power Off` as dealer-only escape hatch (D5).
- HACS submission.
- `c4forums.com` / drivercentral.io listing.

### 10.2 Will resolve as the work progresses

- Whether `lyaml` for Lua is robust enough to consume `spec/vectors/formatters.yaml` directly, or whether codegen should emit a `tests/lua_vectors.lua` table. Prototype during Phase 2.
- `STATUS` parser implementation strategy — line-indexed vs. regex. Prototype during Phase 2.
- Whether to split this plan doc into multiple ADRs under `docs/adr/`. Probably yes, once `docs/adr/` exists; D1 through D13 are reasonable ADR boundaries.

### 10.3 Will require a follow-on grilling session

- The CLI's long-term destiny (primary product vs. dev tool) — affects whether it tracks the device's full feature surface or stays narrow. Currently it has more features than the driver exposes; that asymmetry is fine for now.
- Whether to pursue Snap One Driver Development Partner status independently (separate from going through the dealer for a Composer Pro license).
- Whether the user invests in a used dev controller (HC-250 / EA-1) once Composer Pro arrives, or relies on Virtual Director.

---

## 11. Source-conversation provenance

This document is the synthesis of a `/grill-me` design session. Decisions were locked one branch at a time, with research grounding (Exa searches, the manufacturer references in `references/`, and an empirical TCP probe of the live device at `192.0.2.176`). The conversation also produced a throwaway diagnostic script that confirmed concurrent multi-client TCP support; that script can be discarded, and the finding is captured in section 7.
