"""Acceptance tests for the PEP 561 ``py.typed`` marker (issue #29).

The library is fully type-annotated; shipping ``py.typed`` lets downstream
consumers (notably the forthcoming Home Assistant integration) type-check
against it. The marker must exist in the package AND be wired into the build so
it lands in the published wheel and sdist — adding it later would be a
breaking-ish change for consumers who'd suddenly start seeing type errors.

Following the philosophy of ``tests/test_distribution_scaffolding.py``, these
assert on the committed marker and the build configuration rather than running
a full ``python -m build``.
"""

from __future__ import annotations

from pathlib import Path

import tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]
PY_TYPED = REPO_ROOT / "blustream" / "py.typed"
PYPROJECT = REPO_ROOT / "pyproject.toml"


def test_py_typed_marker_present_in_package():
    assert PY_TYPED.is_file(), (
        "blustream/py.typed (PEP 561 inline-types marker) must exist in the package"
    )


def test_py_typed_declared_as_package_data():
    config = tomllib.loads(PYPROJECT.read_text())
    package_data = config.get("tool", {}).get("setuptools", {}).get("package-data", {})
    assert "py.typed" in package_data.get("blustream", []), (
        "pyproject.toml must declare blustream/py.typed as package-data so the "
        "marker ships in the built wheel and sdist"
    )
