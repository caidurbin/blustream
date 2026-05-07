# Blustream Home Assistant integration (reserved)

This directory reserves the `custom_components/blustream/` slot in the
repository for the future Home Assistant integration. **The integration
itself is not yet implemented** — only the directory and HACS metadata
exist today.

## Why a stub?

Reserving the slot now makes the project findable in HACS and aligns
with Home Assistant's architectural rule that API/protocol code lives
in a third-party library. When the integration ships, it will depend
on the published [`blustream`](https://pypi.org/project/blustream/)
PyPI package (the same library that powers the CLI and the Control4
driver's protocol primitives) rather than carrying its own copy of the
wire-format code.

## Status

- No `manifest.json`, no entities, no config flow — the integration is
  intentionally non-functional.
- Installing this repository as a HACS custom integration today will
  not give you a working device in Home Assistant.
- The integration will be designed and built under a separate PRD.

## Context

- Parent PRD: [issue #9](https://github.com/caidurbin/blustream/issues/9)
  (Control4 driver + monorepo restructure; see "Out of Scope" for the
  HA deferral).
- This stub: [issue #14](https://github.com/caidurbin/blustream/issues/14).
- Background: [`docs/control4-driver-plan.md`](../../docs/control4-driver-plan.md).
