"""Unit tests for tools/check_manifest_requirements_published.py.

The guard exists because ``blustream==0.3.0`` shipped in the ``hacs-v0.2.0``
integration manifest before its ``v0.3.0`` PyPI release, so Home Assistant
could not install it after a restart. These tests drive the pure satisfaction
logic with a fixed catalogue (no PyPI network) and confirm the real manifest's
pins parse, so the checker itself can't crash on malformed input.
"""

from __future__ import annotations

import json
from pathlib import Path

from packaging.requirements import Requirement

import tools.check_manifest_requirements_published as guard
from tools.check_manifest_requirements_published import (
    installable_versions,
    main,
    unsatisfied_requirements,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "custom_components" / "blustream" / "manifest.json"


def _resolver(catalogue):
    """A resolver returning ``catalogue[name]`` (``[]`` for unknown names)."""
    return lambda name: catalogue.get(name, [])


class TestUnsatisfiedRequirements:
    def test_exact_pin_present_is_satisfied(self):
        resolve = _resolver({"blustream": ["0.1.0", "0.2.0"]})
        assert unsatisfied_requirements(["blustream==0.2.0"], resolve) == []

    def test_exact_pin_absent_is_unsatisfied(self):
        # The blustream==0.3.0 / hacs-v0.2.0 regression in miniature.
        resolve = _resolver({"blustream": ["0.1.0", "0.2.0"]})
        assert unsatisfied_requirements(["blustream==0.3.0"], resolve) == [
            "blustream==0.3.0"
        ]

    def test_unknown_project_is_unsatisfied(self):
        assert unsatisfied_requirements(["nope==1.0"], _resolver({})) == ["nope==1.0"]

    def test_range_specifier_uses_any_published_match(self):
        resolve = _resolver({"blustream": ["0.1.0", "0.2.0"]})
        assert unsatisfied_requirements(["blustream>=0.2.0"], resolve) == []
        assert unsatisfied_requirements(["blustream>=0.9"], resolve) == [
            "blustream>=0.9"
        ]

    def test_prerelease_pin_matches_only_that_prerelease(self):
        resolve = _resolver({"blustream": ["0.3.0a1"]})
        assert unsatisfied_requirements(["blustream==0.3.0a1"], resolve) == []
        # A stable pin is NOT satisfied by a lone prerelease.
        assert unsatisfied_requirements(["blustream==0.3.0"], resolve) == [
            "blustream==0.3.0"
        ]

    def test_reports_each_offender_in_order(self):
        resolve = _resolver({"a": ["1.0"], "b": ["1.0"]})
        unmet = unsatisfied_requirements(["a==1.0", "b==2.0", "c==1.0"], resolve)
        assert unmet == ["b==2.0", "c==1.0"]


class TestInstallableVersions:
    """Only versions with a distribution file count as installable."""

    def test_versions_with_files_are_kept(self):
        releases = {"0.1.0": [{"filename": "a.whl"}], "0.2.0": [{"filename": "b.whl"}]}
        assert installable_versions(releases) == ["0.1.0", "0.2.0"]

    def test_empty_file_list_is_excluded(self):
        # A version key lingers after every artifact is deleted; pip cannot
        # install it, so it must not count as published (the false-PASS case).
        releases = {"0.2.0": [{"filename": "b.whl"}], "0.3.0": []}
        assert installable_versions(releases) == ["0.2.0"]

    def test_yanked_but_present_files_stay_counted(self):
        # Yanked files remain in the list; pip still picks them for an exact
        # == pin (PEP 592), so a yanked-but-present version stays installable.
        releases = {"0.3.0": [{"filename": "c.whl", "yanked": True}]}
        assert installable_versions(releases) == ["0.3.0"]


class TestMain:
    def test_no_requirements_returns_zero(self, tmp_path):
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps({"domain": "x"}))
        assert main(["prog", str(manifest)]) == 0

    def test_missing_manifest_returns_two(self, tmp_path):
        # Documented contract: a usage error exits 2, not a bare traceback.
        assert main(["prog", str(tmp_path / "nope.json")]) == 2

    def test_malformed_manifest_returns_two(self, tmp_path):
        manifest = tmp_path / "manifest.json"
        manifest.write_text("{ not json")
        assert main(["prog", str(manifest)]) == 2

    def test_unpublished_pin_fails_with_error_annotation(
        self, tmp_path, monkeypatch, capsys
    ):
        # Redirect the default resolver so main() never touches PyPI.
        monkeypatch.setattr(
            guard, "published_versions", lambda name: ["0.1.0", "0.2.0"]
        )
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps({"requirements": ["blustream==0.3.0"]}))
        assert main(["prog", str(manifest)]) == 1
        out = capsys.readouterr().out
        assert "::error::" in out
        assert "blustream==0.3.0" in out

    def test_published_pin_passes(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            guard, "published_versions", lambda name: ["0.1.0", "0.2.0"]
        )
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps({"requirements": ["blustream==0.2.0"]}))
        assert main(["prog", str(manifest)]) == 0

    def test_usage_error_returns_two(self):
        assert main(["prog"]) == 2


class TestRealManifest:
    def test_manifest_requirements_parse(self):
        # If a pin is malformed, Requirement() raises and the guard would
        # crash instead of reporting -- pin the real manifest stays parseable.
        requirements = json.loads(MANIFEST_PATH.read_text()).get("requirements", [])
        for raw in requirements:
            Requirement(raw)
