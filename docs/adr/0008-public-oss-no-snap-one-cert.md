---
applies_to: [python-library, c4-driver, ha-integration]
---

# Public OSS distribution, no Snap One certification

Three runtime artifacts ship independently: the `blustream` Python library on PyPI (tags `v*`), the unencrypted Control4 `.c4z` driver attached to GitHub releases (tags `c4-v*`), and (eventually) a Home Assistant integration via HACS. The `.c4z` is dealer-installable but is **not** submitted to drivercentral.io or Snap One certification — the certification path didn't exist for this configuration and dealer-loadable distribution is sufficient for the user's deployment. The shared protocol spec under `spec/` is the coordination point across the three artifacts; they cut releases independently.
