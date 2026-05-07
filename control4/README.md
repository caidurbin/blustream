# Control4 drivers

Lua source for Control4 drivers built against the Blustream protocol layer.
Per [ADR-0002](../docs/adr/0002-lua-driver-no-python-sidecar.md), the driver
is a pure-Lua port of the protocol layer rather than a sidecar to the Python
library.

## Layout

```
control4/
└── dmp168/
    ├── src/         # Driver source — input to drivers-driverpackager
    │   ├── manifest.xml # Build manifest listing the items below
    │   ├── driver.xml   # Proxy/capabilities declaration
    │   └── driver.lua   # Driver lifecycle and command handlers
    └── spec/        # Busted unit tests (run in CI on Lua 5.1)
```

`src/` currently holds the no-op driver shell from issue #17 — it
registers in Composer Pro as an `audio_matrix_switch` proxy with 16
stereo input + 8 stereo output bindings (per
[ADR-0003](../docs/adr/0003-c4-audio-matrix-proxy-shape.md)) but the
Lua handlers are empty. Connection state machine, polling coordinator,
proxy handler, and the codegen-emitted `generated.lua`
(see [ADR-0007](../docs/adr/0007-codegen-with-shared-test-vectors.md))
arrive in later slices. The `spec/` tree carries a smoke test today so
the CI Lua harness has something to exercise.

## Building the .c4z

```bash
# Both flavors at once; clones snap-one/drivers-driverpackager into .cache/
# if it is not already present.
python tools/build_c4z.py both --auto-clone

# Just the dev flavor (-ae, hot-pasteable into the Composer Lua console).
python tools/build_c4z.py dev --auto-clone

# Release flavor (clean, no debug affordances).
python tools/build_c4z.py release --auto-clone
```

Outputs land in `dist/c4z/{dev,release}/blustream-dmp168.c4z`. Pass
`--driverpackager-path /path/to/checkout` (or set `DRIVERPACKAGER_PATH`)
to point at an existing local clone instead of using `--auto-clone`.

## Local development

See the project [README](../README.md#lua-development) for instructions on
installing Lua 5.1, `luacheck`, and `busted` locally.
