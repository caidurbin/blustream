"""Tests for the .c4z build pipeline (tools/build_c4z.py).

These tests pin the contract between the build script and
drivers-driverpackager: dev builds pass ``-ae``, release builds do
not, and the build wrapper plumbs paths and manifests through
unchanged. driverpackager is not required to be installed — the
subprocess call is replaced with a fake recorder.
"""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tools.build_c4z import (
    DEFAULT_MANIFEST,
    DEFAULT_SRC_DIR,
    FLAVORS,
    build_dp_argv,
    build_one,
    parse_args,
    resolve_driverpackager,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DRIVER_SRC_DIR = REPO_ROOT / "control4" / "dmp168" / "src"


class TestBuildDpArgv:
    """Pure-function tests for the driverpackager argv constructor."""

    def test_dev_flavor_passes_allowexecute(self):
        argv = build_dp_argv(
            driverpackager=Path("/dp/driverpackager.py"),
            src_dir=Path("/src"),
            out_dir=Path("/out"),
            flavor="dev",
        )
        assert "-ae" in argv

    def test_release_flavor_omits_allowexecute(self):
        argv = build_dp_argv(
            driverpackager=Path("/dp/driverpackager.py"),
            src_dir=Path("/src"),
            out_dir=Path("/out"),
            flavor="release",
        )
        assert "-ae" not in argv

    def test_unknown_flavor_rejected(self):
        with pytest.raises(ValueError, match="unknown flavor"):
            build_dp_argv(
                driverpackager=Path("/dp/driverpackager.py"),
                src_dir=Path("/src"),
                out_dir=Path("/out"),
                flavor="prod",
            )

    def test_argv_contains_src_and_out_paths_after_flags(self):
        argv = build_dp_argv(
            driverpackager=Path("/dp/driverpackager.py"),
            src_dir=Path("/src"),
            out_dir=Path("/out"),
            flavor="release",
            manifest="manifest.xml",
            verbose=False,
        )
        assert argv[-3:] == ["/src", "/out", "manifest.xml"]

    def test_verbose_flag_added_when_requested(self):
        argv = build_dp_argv(
            driverpackager=Path("/dp/driverpackager.py"),
            src_dir=Path("/src"),
            out_dir=Path("/out"),
            flavor="release",
            verbose=True,
        )
        assert "-v" in argv

    def test_uses_provided_python_executable(self):
        argv = build_dp_argv(
            driverpackager=Path("/dp/driverpackager.py"),
            src_dir=Path("/src"),
            out_dir=Path("/out"),
            flavor="release",
            python_executable="/opt/python/bin/python3",
        )
        assert argv[0] == "/opt/python/bin/python3"
        assert argv[1] == "/dp/driverpackager.py"

    def test_dp_invoked_via_python_so_macos_no_execute_bit(self):
        """driverpackager.py is shipped as a Python script; we always
        invoke it via the Python interpreter rather than relying on a
        shebang + executable bit, so the build works on any host."""
        argv = build_dp_argv(
            driverpackager=Path("/dp/driverpackager.py"),
            src_dir=Path("/src"),
            out_dir=Path("/out"),
            flavor="release",
            python_executable="python3",
        )
        assert argv[0] == "python3"


class TestResolveDriverpackager:
    """Tests for the path-resolution + auto-clone logic."""

    def test_explicit_path_wins(self, tmp_path):
        dp = tmp_path / "driverpackager.py"
        dp.write_text("# stub")
        resolved = resolve_driverpackager(explicit=dp, env={})
        assert resolved == dp

    def test_explicit_directory_finds_dp3_subdir_layout(self, tmp_path):
        # Real upstream layout: dp3/driverpackager.py is the Python 3
        # entry script, dp/ is the (unmaintained) Python 2 variant.
        repo = tmp_path / "drivers-driverpackager"
        (repo / "dp3").mkdir(parents=True)
        (repo / "dp3" / "driverpackager.py").write_text("# stub")
        resolved = resolve_driverpackager(explicit=repo, env={})
        assert resolved == repo / "dp3" / "driverpackager.py"

    def test_explicit_directory_with_flat_layout_also_works(self, tmp_path):
        # Some users may extract just driverpackager.py to a directory.
        flat = tmp_path / "flat"
        flat.mkdir()
        (flat / "driverpackager.py").write_text("# stub")
        resolved = resolve_driverpackager(explicit=flat, env={})
        assert resolved == flat / "driverpackager.py"

    def test_env_var_used_when_no_explicit(self, tmp_path):
        dp = tmp_path / "driverpackager.py"
        dp.write_text("# stub")
        resolved = resolve_driverpackager(
            explicit=None, env={"DRIVERPACKAGER_PATH": str(dp)}
        )
        assert resolved == dp

    def test_cache_dir_used_when_no_explicit_or_env(self, tmp_path):
        cache = tmp_path / "cache"
        (cache / "dp3").mkdir(parents=True)
        (cache / "dp3" / "driverpackager.py").write_text("# stub")
        resolved = resolve_driverpackager(
            explicit=None, env={}, cache_dir=cache, auto_clone=False
        )
        assert resolved == cache / "dp3" / "driverpackager.py"

    def test_missing_without_auto_clone_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Could not locate"):
            resolve_driverpackager(
                explicit=None,
                env={},
                cache_dir=tmp_path / "missing",
                auto_clone=False,
            )


class TestBuildOne:
    """Integration-shaped tests with a fake driverpackager runner."""

    def test_invokes_runner_with_constructed_argv(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "manifest.xml").write_text("<Driver/>")
        out = tmp_path / "out"
        dp = tmp_path / "driverpackager.py"
        dp.write_text("# stub")

        recorded = {}

        def fake_runner(argv, check, cwd):
            recorded["argv"] = argv
            recorded["check"] = check
            recorded["cwd"] = cwd
            (out / "release" / "blustream-dmp168.c4z").parent.mkdir(
                parents=True, exist_ok=True
            )
            (out / "release" / "blustream-dmp168.c4z").write_bytes(b"PK\x03\x04")

        produced = build_one(
            flavor="release",
            src_dir=src,
            out_dir=out,
            driverpackager=dp,
            runner=fake_runner,
        )

        assert recorded["check"] is True
        assert recorded["cwd"] == src
        assert str(dp) in recorded["argv"]
        assert "-ae" not in recorded["argv"]
        assert produced.name == "blustream-dmp168.c4z"

    def test_dev_flavor_propagates_allowexecute_through_runner(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "manifest.xml").write_text("<Driver/>")
        out = tmp_path / "out"
        dp = tmp_path / "driverpackager.py"
        dp.write_text("# stub")

        recorded_argv: list[list[str]] = []

        def fake_runner(argv, check, cwd):
            recorded_argv.append(list(argv))
            target = out / "dev"
            target.mkdir(parents=True, exist_ok=True)
            (target / "blustream-dmp168.c4z").write_bytes(b"PK\x03\x04")

        build_one(
            flavor="dev",
            src_dir=src,
            out_dir=out,
            driverpackager=dp,
            runner=fake_runner,
        )

        assert "-ae" in recorded_argv[0]

    def test_missing_manifest_raises_before_runner(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        out = tmp_path / "out"
        dp = tmp_path / "driverpackager.py"
        dp.write_text("# stub")

        called = False

        def fake_runner(*_args, **_kwargs):
            nonlocal called
            called = True

        with pytest.raises(FileNotFoundError, match="manifest not found"):
            build_one(
                flavor="release",
                src_dir=src,
                out_dir=out,
                driverpackager=dp,
                runner=fake_runner,
            )
        assert called is False

    def test_dev_and_release_outputs_do_not_collide(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "manifest.xml").write_text("<Driver/>")
        out = tmp_path / "out"
        dp = tmp_path / "driverpackager.py"
        dp.write_text("# stub")

        def fake_runner(argv, check, cwd):
            target_dir = Path(argv[-2])
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / "blustream-dmp168.c4z").write_bytes(b"PK\x03\x04")

        dev = build_one(
            flavor="dev", src_dir=src, out_dir=out, driverpackager=dp,
            runner=fake_runner,
        )
        release = build_one(
            flavor="release", src_dir=src, out_dir=out, driverpackager=dp,
            runner=fake_runner,
        )
        assert dev.parent.name == "dev"
        assert release.parent.name == "release"
        assert dev != release


class TestParseArgs:
    """Tests for the CLI surface."""

    def test_default_flavors_are_dev_release_or_both(self):
        # The "both" choice exists so CI can build both with one call.
        for flavor in ("dev", "release", "both"):
            args = parse_args([flavor])
            assert args.flavor == flavor

    def test_unknown_flavor_rejected(self):
        with pytest.raises(SystemExit):
            parse_args(["staging"])

    def test_defaults_target_dmp168_driver_directory(self):
        args = parse_args(["release"])
        assert args.src_dir == DEFAULT_SRC_DIR
        assert args.manifest == DEFAULT_MANIFEST


class TestDriverShell:
    """Surface checks on the committed driver source files."""

    def test_driver_xml_is_well_formed(self):
        tree = ET.parse(DRIVER_SRC_DIR / "driver.xml")
        root = tree.getroot()
        assert root.tag == "devicedata"

    def test_driver_xml_declares_audio_matrix_switch_proxy(self):
        # The Control4 proxy contract from ADR-0003.
        tree = ET.parse(DRIVER_SRC_DIR / "driver.xml")
        proxies = tree.findall(".//proxies/proxy")
        assert len(proxies) == 1
        assert proxies[0].text == "audio_matrix_switch"

    def test_driver_xml_has_16_inputs_and_8_outputs(self):
        # Channel-lock-on stereo bindings; matches ADR-0003 §"16 stereo
        # input + 8 stereo output bindings". Filter on class=STEREO so
        # the network-control connection (added in issue #20) does not
        # accidentally bump these counts.
        def is_stereo(c):
            return any(
                (cls.findtext("classname") or "").strip().upper() == "STEREO"
                for cls in c.findall(".//classes/class")
            )

        tree = ET.parse(DRIVER_SRC_DIR / "driver.xml")
        connections = tree.findall(".//connections/connection")
        consumers = [
            c
            for c in connections
            if (c.findtext("consumer") or "").strip().lower() == "true"
            and is_stereo(c)
        ]
        providers = [
            c
            for c in connections
            if (c.findtext("audiosource") or "").strip().lower() == "true"
            and is_stereo(c)
        ]
        assert len(consumers) == 16
        assert len(providers) == 8

    def test_driver_xml_capabilities_match_binding_counts(self):
        tree = ET.parse(DRIVER_SRC_DIR / "driver.xml")
        assert tree.findtext(".//capabilities/audio_consumers") == "16"
        assert tree.findtext(".//capabilities/audio_providers") == "8"

    def test_driver_xml_does_not_declare_volume_or_power_capability(self):
        # ADR-0003: no has_volume / has_mute / has_power. Downstream
        # amplifier owns volume; matrix power is internal lifecycle.
        tree = ET.parse(DRIVER_SRC_DIR / "driver.xml")
        capabilities = tree.find(".//capabilities")
        assert capabilities is not None
        children = {child.tag for child in capabilities}
        assert "has_volume" not in children
        assert "has_mute" not in children
        assert "has_power" not in children

    def test_driver_lua_defines_lifecycle_entrypoints(self):
        text = (DRIVER_SRC_DIR / "driver.lua").read_text()
        for entrypoint in (
            "OnDriverInit",
            "OnDriverLateInit",
            "OnDriverDestroyed",
            "ExecuteCommand",
        ):
            assert f"function {entrypoint}" in text, entrypoint

    def test_driver_lua_does_not_hardcode_allowexecute(self):
        # C4:AllowExecute(true) is injected by driverpackager -ae for the
        # dev flavor; release builds must stay clean. If this call landed
        # in source we'd be shipping debug affordances in every release.
        non_comment = "\n".join(
            line for line in (DRIVER_SRC_DIR / "driver.lua").read_text().splitlines()
            if not line.lstrip().startswith("--")
        )
        assert "C4:AllowExecute" not in non_comment


class TestManifestXml:
    """Surface checks on the driverpackager manifest."""

    MANIFEST_PATH = DRIVER_SRC_DIR / "manifest.xml"

    def test_manifest_is_well_formed(self):
        tree = ET.parse(self.MANIFEST_PATH)
        root = tree.getroot()
        assert root.tag == "Driver"
        assert root.get("type") == "c4z"

    def test_manifest_lists_driver_xml_and_driver_lua(self):
        tree = ET.parse(self.MANIFEST_PATH)
        names = {item.get("name") for item in tree.findall(".//Items/Item")}
        # driverpackager's -ae logic hardcodes driver.lua at the manifest
        # directory root, so the manifest sits in src/ next to the Lua.
        # The manifest also pulls in the require()-able Lua modules that
        # ship inside the .c4z (connection.lua etc.).
        assert {"driver.xml", "driver.lua"} <= names

    def test_manifest_output_basename_matches_driver_id(self):
        # The .c4z basename matters: GitHub release artifacts and dealer
        # install instructions reference it by name.
        tree = ET.parse(self.MANIFEST_PATH)
        assert tree.getroot().get("name") == "blustream-dmp168"

    def test_manifest_lives_in_src_alongside_driver_files(self):
        # If this fires, driverpackager will fail to find driver.lua at
        # the path it hardcodes for -ae injection. See driverpackager.py
        # in dp3/, ~line 205.
        assert self.MANIFEST_PATH.is_file()
        assert (self.MANIFEST_PATH.parent / "driver.lua").is_file()
        assert (self.MANIFEST_PATH.parent / "driver.xml").is_file()


def test_flavors_constant_is_dev_and_release():
    # Pinned so a future "staging" flavor lands as a deliberate change.
    assert FLAVORS == ("dev", "release")


_DRIVERPACKAGER_PATH = (
    REPO_ROOT / ".cache" / "drivers-driverpackager" / "dp3" / "driverpackager.py"
)


def _lxml_available(python_executable: str = sys.executable) -> bool:
    """Whether ``python_executable`` can import lxml.

    driverpackager.py imports ``lxml`` at module scope, so a present
    checkout with lxml missing fails the build hard rather than skipping.
    We probe the *interpreter that will run the packager* (``sys.executable``,
    matching ``build_one``'s default ``runner``) rather than this pytest
    process, so the gate stays correct even if a build is ever pointed at a
    different interpreter via ``python_executable``.
    """
    return (
        subprocess.run(
            [python_executable, "-c", "import lxml"],
            capture_output=True,
        ).returncode
        == 0
    )


@pytest.mark.skipif(
    not _DRIVERPACKAGER_PATH.exists(),
    reason="drivers-driverpackager not available; run `python tools/build_c4z.py both --auto-clone` once.",
)
@pytest.mark.skipif(
    not _lxml_available(),
    reason="lxml not importable in the build interpreter; run `uv sync --extra c4z` (or pip install lxml).",
)
class TestC4zBuildEndToEnd:
    """End-to-end checks that exercise driverpackager + the real driver source.

    These run only when the upstream tool is already cloned (CI calls
    ``--auto-clone``; locally users opt in by running the build once).
    Without this gate, pytest would either skip silently or trigger a
    ``git clone`` from a unit test, which is too magical.
    """

    def test_release_c4z_does_not_inject_allowexecute(self, tmp_path):
        import zipfile

        from tools.build_c4z import build_one, resolve_driverpackager

        dp = resolve_driverpackager()
        out = build_one(
            flavor="release",
            src_dir=DRIVER_SRC_DIR,
            out_dir=tmp_path,
            driverpackager=dp,
        )
        with zipfile.ZipFile(out) as z:
            lua = z.read("driver.lua").decode()
        non_comment = "\n".join(
            line for line in lua.splitlines()
            if not line.lstrip().startswith("--")
        )
        assert "C4:AllowExecute" not in non_comment
        assert "gIsDevelopmentVersionOfDriver" not in non_comment

    def test_dev_c4z_injects_allowexecute_and_devlog(self, tmp_path):
        import zipfile

        from tools.build_c4z import build_one, resolve_driverpackager

        dp = resolve_driverpackager()
        out = build_one(
            flavor="dev",
            src_dir=DRIVER_SRC_DIR,
            out_dir=tmp_path,
            driverpackager=dp,
        )
        with zipfile.ZipFile(out) as z:
            lua = z.read("driver.lua").decode()
        assert "C4:AllowExecute(true)" in lua
        assert "gIsDevelopmentVersionOfDriver = true" in lua

    def test_c4z_archive_contains_driver_xml_and_driver_lua(self, tmp_path):
        import zipfile

        from tools.build_c4z import build_one, resolve_driverpackager

        dp = resolve_driverpackager()
        out = build_one(
            flavor="release",
            src_dir=DRIVER_SRC_DIR,
            out_dir=tmp_path,
            driverpackager=dp,
        )
        with zipfile.ZipFile(out) as z:
            names = set(z.namelist())
        assert "driver.xml" in names
        assert "driver.lua" in names
