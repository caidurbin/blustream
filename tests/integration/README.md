# Live-device integration suite

This directory holds pytest tests that exercise the DMP168 driver path
against **real hardware**. They are skipped by default; only the unit-test
suite under `tests/` (excluding this subdirectory) runs in normal CI.

## When these tests run

A pytest fixture in `conftest.py` checks for the
`BLUSTREAM_INTEGRATION_HOST` environment variable. If it is unset, every
test in this directory is skipped with a clear reason. With the env var
set, the suite opens TCP connections to the matrix at that address.

| Variable                       | Required | Default | Purpose                                |
| ------------------------------ | -------- | ------- | -------------------------------------- |
| `BLUSTREAM_INTEGRATION_HOST`   | yes      | _none_  | Hostname or IP of the live matrix      |
| `BLUSTREAM_INTEGRATION_PORT`   | no       | `23`    | TCP port; use `8000` for the raw-TCP listener |

The default port `23` matches the Python library's existing default
(telnet) so the suite works against the same listener the CLI talks to.
The Control4 driver targets port `8000` by default — flip the env var to
match if you want the integration suite to exercise the same listener
the driver uses in production.

## Running locally

```bash
# default port 23 (telnet)
BLUSTREAM_INTEGRATION_HOST=192.0.2.10 pytest tests/integration -v

# raw TCP listener
BLUSTREAM_INTEGRATION_HOST=192.0.2.10 \
BLUSTREAM_INTEGRATION_PORT=8000 \
pytest tests/integration -v
```

`pytest` from the repo root with no env var will collect these tests and
mark them all `SKIPPED`, which is what default CI sees.

## What the suite covers

- **`test_routing_roundtrip.py`** — Issues a route command for output 8 /
  input 16 (the corners of the matrix, least likely to disrupt a
  homeowner's listening room), polls `STATUS`, and asserts the change is
  observable. Captures the prior route and restores it on teardown.
- **`test_status_polling.py`** — Opens two TCP connections, issues a route
  via the "external" connection, and asserts the "driver" connection's
  next `STATUS` poll observes the change. The matrix has no concept of
  *which* client made a change, so two clients are a faithful stand-in
  for the matrix web GUI.
- **`test_concurrent_clients.py`** — Opens four parallel TCP clients and
  issues `STATUS` on each concurrently. Re-verifies the load-bearing
  assumption (PRD #9) that Control4 + CLI + future HA can coexist with
  the matrix web GUI.

## Safety notes

The routing tests pick the highest output and input channels (output 8,
inputs 14–16) so a homeowner running the suite while music is playing
should not have an active zone disrupted. They still mutate live device
state for ~1 second per test, so coordinate before running against a
production rack. Each test captures the prior routing for the channels
it touches and restores it on teardown.

## Why not run in default CI

Running this suite requires a real matrix on the network. CI runners
have neither the hardware nor a stable address for one. A separate
manual / scheduled GitHub Actions workflow (deferred to a later slice —
see issue #9, "dealer-load smoke-test slice") will run this suite
against a known-good device on demand.
