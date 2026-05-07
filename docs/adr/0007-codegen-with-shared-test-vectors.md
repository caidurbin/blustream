---
applies_to: [spec, python-library, c4-driver]
---

# Codegen with shared test vectors as protocol source of truth

A single YAML spec under `spec/protocol.yaml` describes the protocol primitives. Codegen emits Python and Lua source files (wire formatters, parameter validators, protocol constants); shared YAML test vectors under `spec/vectors/` are consumed by both implementations' test runners. CI gates ensure committed generated files match what codegen produces and both test suites pass — this keeps the Python library and Lua driver provably consistent without coupling them at runtime. Response parsers and connection-layer logic (asyncio in Python, `C4:CreateNetworkConnection` in Lua) stay hand-written; shared response fixtures provide the cross-impl conformance check for those.
