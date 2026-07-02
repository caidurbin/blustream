---
applies_to: [ha-integration, python-library]
date: 2026-05-29
---

# HA integration: operationalizing the gold-tier commitment

ADR 0009 commits the HA integration to the Gold tier of HA's Integration Quality Scale from v0.1; this ADR records the operational choices that flow from that commitment and would surprise a future contributor without context.

**Test location.** Integration tests live at `tests/components/blustream/` — HA core's `tests/components/<domain>/` convention — because hassfest trips when a test package sits nested inside the integration directory it is linting. The name also avoids colliding with the live-hardware `tests/integration/` suite, which already claims that path.

**Coverage split.** 100 % on `config_flow.py` per the Gold rule `config-flow-test-coverage` vs ≥95 % on every other integration module per the Silver rule `test-coverage` — the config-flow rule is stricter than the general one.

**CI.** Integration workflows pin a single HA version (`pytest-homeassistant-custom-component` pins one HA version per release, so a matrix would test PHCC versions, not real-world HA variance) and the validate workflow adds a daily `schedule: cron`; see the header comments in `.github/workflows/lint-ha.yml` for the operational detail.

**py.typed.** The `blustream` library ships a `py.typed` marker from v0.1.0: adding it later floods downstream `mypy --strict` consumers with sudden type errors, so shipping it now keeps Platinum's `strict-typing` rule reachable without a breaking library change.

**Manifest `"loggers"`.** `"loggers": ["blustream"]` declares the library's logger namespace so HA's debug-logging UI captures the library's protocol-level log lines, not just the integration's. Recorded here because `manifest.json` is JSON and cannot carry comments.
