"""Spec loader and content hashing.

Both emitters share this module so the hash stamped into Python and Lua
generated files is computed identically — reviewers can confirm the two
generated artifacts are derived from the same spec content.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "spec" / "protocol.yaml"


def load_spec(path: Path | str = SPEC_PATH) -> dict[str, Any]:
    """Parse the protocol spec YAML at ``path`` into a Python dict."""
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def spec_hash(path: Path | str = SPEC_PATH) -> str:
    """Return a short, stable SHA-256 of the spec file's bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
