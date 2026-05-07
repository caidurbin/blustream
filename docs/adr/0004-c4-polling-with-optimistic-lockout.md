---
applies_to: [c4-driver]
---

# Control4 driver: polling with optimistic update + lockout window

Multiple control surfaces operate the matrix concurrently (Control4, future HA, the device's web GUI), so out-of-band routing changes must be reflected in Control4's view. The driver background-polls every 15 s (configurable; range 5–60 s), reissues `STATUS`, and reconciles routing fields. Routing commands optimistically update local state immediately and fire diff-based proxy notifications; for ~2 s after a command, poll responses for that output are ignored to avoid a race where a stale poll undoes the optimistic update. A `Refresh Matrix State` Composer Action exposes on-demand refresh on top of the periodic loop.
