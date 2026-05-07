# Control4 drivers

Lua source for Control4 drivers built against the Blustream protocol layer.
Per [ADR-0002](../docs/adr/0002-lua-driver-no-python-sidecar.md), the driver
is a pure-Lua port of the protocol layer rather than a sidecar to the Python
library.

## Layout

```
control4/
└── dmp168/
    ├── src/         # Driver Lua source (loaded by Control4 Composer)
    └── spec/        # Busted unit tests (run in CI on Lua 5.1)
```

The `src/` tree is empty until later slices land the connection state
machine, polling coordinator, proxy handler, and the codegen-emitted
`generated.lua` (see [ADR-0007](../docs/adr/0007-codegen-with-shared-test-vectors.md)).
The `spec/` tree carries a smoke test today so the CI Lua harness has
something to exercise.

## Local development

See the project [README](../README.md#lua-development) for instructions on
installing Lua 5.1, `luacheck`, and `busted` locally.
