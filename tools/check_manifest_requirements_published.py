#!/usr/bin/env python3
"""Fail when a Home Assistant manifest pins a requirement absent from PyPI.

Home Assistant installs a custom integration's ``manifest.json``
``requirements`` with pip during setup, so a ``hacs-v*`` release whose pin was
never published to PyPI installs cleanly in this repo yet aborts on the user's
box with "No solution found when resolving dependencies". That is exactly how
``blustream==0.3.0`` shipped in ``hacs-v0.2.0``: the integration re-pinned the
library to ``0.3.0`` for the output-routing API, but the ``v0.3.0`` PyPI
release (the ``v*`` lane in release-pypi.yml) was never cut, so every setup
after a restart failed.

``release-hacs.yml`` runs this guard *before* creating the GitHub release so an
unsatisfiable pin fails the release instead of users' setups. It runs only on
the ``hacs-v*`` release tag, never on PRs or ``main`` -- this monorepo
legitimately holds an unreleased pin while the library and integration are
developed together, and that intermediate state must not fail everyday CI.

The PyPI fetch (:func:`published_versions`) is kept separate from the pure
satisfaction check (:func:`unsatisfied_requirements`) so the latter is unit
tested without touching the network.

Requirements are assumed version-pinned with ``==`` (HA manifests must be; HA
core rejects URL/marker/loose specifiers). A version whose PyPI distribution
files were all deleted is treated as unpublished -- pip cannot install it --
while a *yanked* version keeps its files and stays installable for an exact
pin (PEP 592), so it is left counted. Environment markers are not evaluated:
a pin must be published regardless of which interpreter HA runs.

Usage::

    python tools/check_manifest_requirements_published.py path/to/manifest.json

Exit status is 0 when every requirement is satisfiable from a published
release, 1 (with a ``::error::`` line per offender) when one is not, and 2 on
a usage error.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable

from packaging.requirements import Requirement

PYPI_JSON_URL = "https://pypi.org/pypi/{name}/json"

VersionResolver = Callable[[str], list[str]]


def installable_versions(releases: dict[str, list]) -> list[str]:
    """Versions from a PyPI ``releases`` mapping that have a distribution file.

    A version key lingers in ``releases`` with an empty file list once every
    artifact is deleted/removed; pip cannot install such a version, so it does
    not count as published. A version whose files are merely *yanked* (PEP 592)
    keeps its files and stays counted -- pip still selects a yanked file for an
    exact ``==`` pin (with a warning), which is how an HA manifest pins.
    """
    return [version for version, files in releases.items() if files]


def published_versions(name: str) -> list[str]:
    """Return every installable version of *name* on PyPI (``[]`` if unknown)."""
    try:
        with urllib.request.urlopen(
            PYPI_JSON_URL.format(name=name), timeout=30
        ) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return []
        raise
    return installable_versions(payload.get("releases", {}))


def unsatisfied_requirements(
    requirements: Iterable[str],
    resolve: VersionResolver | None = None,
) -> list[str]:
    """Return the requirement strings no published release can satisfy.

    *resolve* maps a project name to its published versions; it defaults to
    the live PyPI lookup and is injected so tests supply a fixed catalogue
    instead of querying the network. It is read off the module at call time so
    monkeypatching :func:`published_versions` also redirects this default.
    """
    resolve = resolve or published_versions
    unmet: list[str] = []
    for raw in requirements:
        req = Requirement(raw)
        # ``SpecifierSet.filter`` applies PEP 440 semantics, including
        # admitting a prerelease only when the specifier itself pins one.
        if not list(req.specifier.filter(resolve(req.name))):
            unmet.append(raw)
    return unmet


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_manifest_requirements_published.py <manifest.json>")
        return 2
    manifest_path = argv[1]
    try:
        with open(manifest_path, encoding="utf-8") as handle:
            requirements = json.load(handle).get("requirements", [])
    except (OSError, json.JSONDecodeError) as exc:
        print(f"::error::cannot read manifest {manifest_path}: {exc}")
        return 2
    if not requirements:
        print(f"{manifest_path}: no requirements to verify")
        return 0
    unmet = unsatisfied_requirements(requirements)
    for raw in unmet:
        print(
            f"::error::manifest requirement '{raw}' is not installable from "
            "PyPI; publish that release before tagging this integration release"
        )
    if unmet:
        return 1
    print(f"All {len(requirements)} manifest requirement(s) are published on PyPI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
