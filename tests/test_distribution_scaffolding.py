"""Tests for the in-repo distribution scaffolding (issue #19).

These tests pin the contract for three artifacts that ship the project
to its three audiences:

* ``LICENSE`` — Apache 2.0, matching the setup.py classifier.
* ``.github/workflows/release-pypi.yml`` — fires on ``v*`` tags and
  publishes the Python package to PyPI.
* ``.github/workflows/release-c4z.yml`` — fires on ``c4-v*`` tags,
  builds the release ``.c4z`` via ``tools/build_c4z.py``, and attaches
  it to a GitHub release.

The README is also asserted to describe all three components (library
+ CLI, Control4 driver, future Home Assistant integration) and the
independent-versioning scheme (different tag prefixes per component).

PyPI account creation and ``GITHUB_TOKEN`` / PyPI publish secrets are
explicitly out of scope for issue #19; these tests assert only on
files committed to the repo.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
LICENSE_PATH = REPO_ROOT / "LICENSE"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
RELEASE_PYPI_PATH = WORKFLOWS_DIR / "release-pypi.yml"
RELEASE_C4Z_PATH = WORKFLOWS_DIR / "release-c4z.yml"
RELEASE_HACS_PATH = WORKFLOWS_DIR / "release-hacs.yml"
README_PATH = REPO_ROOT / "README.md"


def _load_workflow(path: Path) -> dict:
    """Load a GitHub Actions workflow as a dict.

    PyYAML parses the bareword ``on`` key as the boolean True (YAML 1.1
    compatibility). Re-key it to the literal string ``"on"`` so tests
    can index into the trigger config without caring about that quirk.
    """
    data = yaml.safe_load(path.read_text())
    if True in data and "on" not in data:
        data["on"] = data.pop(True)
    return data


class TestLicense:
    """Acceptance: a top-level LICENSE file formalizes Apache 2.0 licensing."""

    def test_license_file_exists_at_repo_root(self):
        assert LICENSE_PATH.is_file(), "issue #19 requires a top-level LICENSE file"

    def test_license_is_apache_2_0(self):
        text = LICENSE_PATH.read_text()
        assert "Apache License" in text
        assert "Version 2.0" in text

    def test_license_contains_copyright_notice(self):
        # The Apache 2.0 text references copyright in its redistribution
        # terms and appendix; without it the license is incomplete.
        text = LICENSE_PATH.read_text()
        assert "Copyright" in text

    def test_license_contains_grant_clauses(self):
        # Pin the Apache 2.0 copyright + patent grants so a future swap
        # to a different license shows up as a deliberate test change.
        text = LICENSE_PATH.read_text()
        assert "Grant of Copyright License" in text
        assert "Grant of Patent License" in text

    def test_license_contains_warranty_disclaimer(self):
        text = LICENSE_PATH.read_text()
        assert "WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND" in text


class TestReleasePypiWorkflow:
    """Acceptance: ``v*`` tags trigger a PyPI publish workflow."""

    def test_workflow_file_exists(self):
        assert RELEASE_PYPI_PATH.is_file()

    def test_triggers_only_on_v_prefixed_tags(self):
        wf = _load_workflow(RELEASE_PYPI_PATH)
        triggers = wf["on"]
        # ``push.tags`` must include ``v*`` so the library version
        # bumps independently of the .c4z driver releases.
        assert "v*" in triggers["push"]["tags"]
        # ``c4-v*`` must NOT be on this workflow — that prefix is the
        # driver's, and overlapping triggers would publish the wrong
        # artifact for the wrong tag.
        assert "c4-v*" not in triggers["push"]["tags"]

    def test_runs_on_ubuntu(self):
        wf = _load_workflow(RELEASE_PYPI_PATH)
        jobs = wf["jobs"]
        assert any(
            str(job.get("runs-on", "")).startswith("ubuntu") for job in jobs.values()
        )

    def test_workflow_publishes_to_pypi(self):
        # The workflow must invoke the official PyPI publisher action.
        # Account creation + secret wiring is a separate HITL slice; the
        # workflow code itself should be ready to fire the moment those
        # credentials land.
        text = RELEASE_PYPI_PATH.read_text()
        assert "pypa/gh-action-pypi-publish" in text

    def test_workflow_builds_sdist_and_wheel(self):
        # Both artifacts are expected by PyPI; ``python -m build`` is
        # the standard tool. Pin its presence so a refactor doesn't
        # accidentally drop the wheel.
        text = RELEASE_PYPI_PATH.read_text()
        assert "python -m build" in text or "pyproject-build" in text


class TestReleaseC4zWorkflow:
    """Acceptance: ``c4-v*`` tags trigger a GitHub release with .c4z."""

    def test_workflow_file_exists(self):
        assert RELEASE_C4Z_PATH.is_file()

    def test_triggers_only_on_c4_v_prefixed_tags(self):
        wf = _load_workflow(RELEASE_C4Z_PATH)
        triggers = wf["on"]
        assert "c4-v*" in triggers["push"]["tags"]
        # ``v*`` belongs to the library workflow; listing it here too
        # would publish the wrong artifact for a library tag.
        assert "v*" not in triggers["push"]["tags"]

    def test_runs_on_ubuntu(self):
        wf = _load_workflow(RELEASE_C4Z_PATH)
        jobs = wf["jobs"]
        assert any(
            str(job.get("runs-on", "")).startswith("ubuntu") for job in jobs.values()
        )

    def test_workflow_invokes_build_c4z_release_flavor(self):
        # The build pipeline is owned by tools/build_c4z.py; the release
        # workflow must call it so the released artifact uses the same
        # path tested by tests/test_c4z_build.py rather than re-rolling
        # an alternate driverpackager invocation.
        text = RELEASE_C4Z_PATH.read_text()
        assert "tools/build_c4z.py" in text
        assert "release" in text

    def test_workflow_creates_github_release_and_attaches_artifact(self):
        # The acceptance criterion explicitly requires a GitHub release
        # with the .c4z attached. softprops/action-gh-release is the
        # de-facto action for that and accepts a glob in ``files``.
        text = RELEASE_C4Z_PATH.read_text()
        assert "softprops/action-gh-release" in text
        assert ".c4z" in text

    def test_workflow_grants_contents_write_permission(self):
        # Creating a GitHub release requires write access to the
        # repository contents; without this the release-publish step
        # silently 403s.
        wf = _load_workflow(RELEASE_C4Z_PATH)
        permissions = wf.get("permissions") or {}
        # Could be at workflow scope or job scope; accept either.
        if "contents" not in permissions:
            for job in wf["jobs"].values():
                permissions = job.get("permissions") or {}
                if "contents" in permissions:
                    break
        assert permissions.get("contents") == "write"


class TestReleaseHacsWorkflow:
    """Acceptance: ``hacs-v*`` tags publish a GitHub release, gated on a
    check that the manifest's pinned requirements are published on PyPI."""

    def test_workflow_file_exists(self):
        assert RELEASE_HACS_PATH.is_file()

    def test_triggers_only_on_hacs_v_prefixed_tags(self):
        wf = _load_workflow(RELEASE_HACS_PATH)
        triggers = wf["on"]
        assert "hacs-v*" in triggers["push"]["tags"]
        # The library (v*) and driver (c4-v*) lanes must not fire here, or
        # a library/driver tag would publish an integration release.
        assert "v*" not in triggers["push"]["tags"]
        assert "c4-v*" not in triggers["push"]["tags"]

    def test_runs_on_ubuntu(self):
        wf = _load_workflow(RELEASE_HACS_PATH)
        jobs = wf["jobs"]
        assert any(
            str(job.get("runs-on", "")).startswith("ubuntu") for job in jobs.values()
        )

    def test_workflow_grants_contents_write_permission(self):
        # Creating a GitHub release requires contents: write; accept it at
        # workflow or job scope (the requirements guard job is read-only).
        wf = _load_workflow(RELEASE_HACS_PATH)
        scopes = [wf.get("permissions") or {}]
        scopes += [job.get("permissions") or {} for job in wf["jobs"].values()]
        assert any(scope.get("contents") == "write" for scope in scopes)

    def test_guards_that_manifest_requirements_are_published(self):
        # The hacs-v0.2.0 regression: the manifest pinned blustream==0.3.0
        # before its v0.3.0 PyPI release, so HA could not install it after a
        # restart. The release must run the published-requirements guard so
        # an unsatisfiable pin fails the release, not users' setups.
        text = RELEASE_HACS_PATH.read_text()
        assert "tools/check_manifest_requirements_published.py" in text

    def test_requirements_guard_gates_the_release(self):
        # The guard only protects the release if the release job waits on
        # it. Assert the job that creates the GitHub release ``needs`` the
        # job that runs the guard, so a future edit can't leave the guard
        # running in parallel (or dropped) while the release still ships.
        wf = _load_workflow(RELEASE_HACS_PATH)
        jobs = wf["jobs"]
        release_jobs = {
            name: job
            for name, job in jobs.items()
            if "softprops/action-gh-release" in yaml.safe_dump(job)
        }
        guard_jobs = {
            name
            for name, job in jobs.items()
            if "check_manifest_requirements_published" in yaml.safe_dump(job)
        }
        assert release_jobs, "expected a job that creates the GitHub release"
        assert guard_jobs, "expected a job that runs the requirements guard"
        for name, job in release_jobs.items():
            needs = job.get("needs") or []
            if isinstance(needs, str):
                needs = [needs]
            assert guard_jobs & set(needs), (
                f"release job '{name}' must `needs` the requirements guard"
            )

    def test_requirements_guard_is_not_neutered(self):
        # `needs` only gates the release if the guard job actually fails on a
        # bad pin. A `continue-on-error: true` on the job or its steps would
        # let the guard "succeed" despite a non-zero exit, reopening the hole
        # while the gating test above still passed.
        wf = _load_workflow(RELEASE_HACS_PATH)
        for name, job in wf["jobs"].items():
            if "check_manifest_requirements_published" not in yaml.safe_dump(job):
                continue
            assert job.get("continue-on-error") is not True, (
                f"guard job '{name}' must not set continue-on-error"
            )
            for step in job.get("steps", []):
                assert step.get("continue-on-error") is not True, (
                    f"a step in guard job '{name}' must not set continue-on-error"
                )


class TestReadmeDescribesAllThreeComponents:
    """Acceptance: README explains library/CLI, driver, and HA."""

    @pytest.fixture(scope="class")
    def readme(self) -> str:
        return README_PATH.read_text()

    def test_readme_mentions_python_library_and_cli(self, readme):
        # The library + CLI is the existing component; the rewrite must
        # not drop it.
        assert "Python library" in readme or "Python Library" in readme
        assert "CLI" in readme

    def test_readme_mentions_control4_driver(self, readme):
        assert "Control4" in readme

    def test_readme_mentions_home_assistant(self, readme):
        # HA is forward-looking but must be visible so an open-source
        # consumer searching for "Home Assistant" finds the project.
        assert "Home Assistant" in readme

    def test_readme_describes_independent_versioning(self, readme):
        # The v*/c4-v* prefix split is the load-bearing convention for
        # how the components release independently. Both prefixes must
        # appear in the README so users know which tag to read.
        assert "v*" in readme
        assert "c4-v*" in readme

    def test_readme_links_to_pypi_distribution(self, readme):
        # The library ships to PyPI; surface that so users don't try to
        # install from GitHub when a published wheel exists.
        assert "PyPI" in readme or "pypi" in readme

    def test_readme_links_to_c4z_artifact_distribution(self, readme):
        # Dealers install the driver from the GitHub release page; the
        # README must point at that path.
        assert ".c4z" in readme
