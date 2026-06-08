#!/usr/bin/env python3
"""Build .c4z Control4 driver packages via snap-one/drivers-driverpackager.

Two flavors:

* ``dev`` — passes ``-ae`` (``--allowexecute``) to driverpackager so the
  resulting archive is hot-pasteable into Composer Pro's Lua console
  (per ADR-0006). Use this during dealer-load development.
* ``release`` — clean build with no debug affordances. This is what
  attaches to GitHub releases on ``c4-v*`` tags.

drivers-driverpackager is not on PyPI; it is consumed as a Git checkout.
This script resolves its location in three places, in order:

1. ``--driverpackager-path`` CLI flag.
2. ``DRIVERPACKAGER_PATH`` environment variable.
3. A repo-local clone at ``.cache/drivers-driverpackager``. The script
   will clone it on demand when ``--auto-clone`` is set (CI uses this).

Usage::

    python tools/build_c4z.py dev
    python tools/build_c4z.py release --output-dir dist/c4z
    python tools/build_c4z.py both --auto-clone
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC_DIR = REPO_ROOT / "control4" / "dmp168" / "src"
DEFAULT_MANIFEST = "manifest.xml"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "dist" / "c4z"
DEFAULT_CACHE_DIR = REPO_ROOT / ".cache" / "drivers-driverpackager"
DRIVERPACKAGER_GIT_URL = "https://github.com/snap-one/drivers-driverpackager.git"
# Pin the upstream packager to an immutable commit so a compromised or
# force-pushed upstream cannot inject code into the build. Bump deliberately.
DRIVERPACKAGER_GIT_REF = (
    "16eef8beb70303606f066524cda516b2aa7ce38d"  # master @ 2026-05-31
)

FLAVORS = ("dev", "release")


def build_dp_argv(
    *,
    driverpackager: Path,
    src_dir: Path,
    out_dir: Path,
    flavor: str,
    manifest: str = DEFAULT_MANIFEST,
    verbose: bool = True,
    python_executable: str | None = None,
) -> list[str]:
    """Construct the argv that invokes drivers-driverpackager for one flavor.

    Splitting argv construction out lets unit tests assert the contract
    (``-ae`` exactly when ``flavor == "dev"``) without invoking the
    external tool.
    """
    if flavor not in FLAVORS:
        raise ValueError(f"unknown flavor {flavor!r}; expected one of {FLAVORS}")

    argv: list[str] = [python_executable or sys.executable, str(driverpackager)]
    if verbose:
        argv.append("-v")
    if flavor == "dev":
        argv.append("-ae")
    argv.extend([str(src_dir), str(out_dir)])
    if manifest:
        argv.append(manifest)
    return argv


# Inside a snap-one/drivers-driverpackager checkout, the Python 3 entry
# script lives at dp3/driverpackager.py; dp/ is the unmaintained Python 2
# variant. Search the Python 3 path first, then fall back to a flat layout
# (lets users point at a hand-extracted driverpackager.py directly).
DRIVERPACKAGER_REL_CANDIDATES = (
    Path("dp3") / "driverpackager.py",
    Path("driverpackager.py"),
)


def resolve_driverpackager(
    *,
    explicit: Path | None = None,
    env: os._Environ[str] | dict[str, str] | None = None,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    auto_clone: bool = False,
) -> Path:
    """Locate driverpackager.py, optionally cloning the upstream repo.

    Resolution order: explicit path → ``DRIVERPACKAGER_PATH`` env var →
    repo-local cache. If none exist and ``auto_clone`` is true, clone the
    upstream repo into ``cache_dir``.
    """
    env = env if env is not None else os.environ
    candidates: list[Path] = []
    if explicit is not None:
        candidates.extend(_expand_dp_candidates(explicit))
    env_value = env.get("DRIVERPACKAGER_PATH")
    if env_value:
        candidates.extend(_expand_dp_candidates(Path(env_value)))
    candidates.extend(_expand_dp_candidates(cache_dir))

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    if auto_clone:
        cloned = _clone_driverpackager(cache_dir)
        if cloned.is_file():
            return cloned

    searched = "\n  ".join(str(c) for c in candidates)
    raise FileNotFoundError(
        "Could not locate drivers-driverpackager. Searched:\n  "
        + searched
        + "\nPass --driverpackager-path, set DRIVERPACKAGER_PATH, or rerun "
        + "with --auto-clone."
    )


def _expand_dp_candidates(path: Path) -> list[Path]:
    """Expand a path to the concrete driverpackager.py files to try.

    A file path is taken verbatim. A directory is expanded into the
    repo-relative candidates (dp3/driverpackager.py, then a flat layout).
    """
    if path.is_file():
        return [path]
    return [path / rel for rel in DRIVERPACKAGER_REL_CANDIDATES]


def _clone_driverpackager(cache_dir: Path) -> Path:
    """Clone the upstream driverpackager into cache_dir, pinned to an
    immutable commit (``DRIVERPACKAGER_GIT_REF``) for supply-chain safety."""
    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    if not (cache_dir / ".git").is_dir():
        subprocess.run(
            ["git", "clone", DRIVERPACKAGER_GIT_URL, str(cache_dir)],
            check=True,
        )
    else:
        subprocess.run(
            ["git", "-C", str(cache_dir), "fetch", "origin", DRIVERPACKAGER_GIT_REF],
            check=True,
        )
    subprocess.run(
        ["git", "-C", str(cache_dir), "checkout", "--quiet", DRIVERPACKAGER_GIT_REF],
        check=True,
    )
    return cache_dir / "dp3" / "driverpackager.py"


def build_one(
    *,
    flavor: str,
    src_dir: Path,
    out_dir: Path,
    driverpackager: Path,
    manifest: str = DEFAULT_MANIFEST,
    verbose: bool = True,
    runner=subprocess.run,
) -> Path:
    """Build a single flavor and return the produced .c4z path.

    The output is placed under ``out_dir/<flavor>/`` so the two flavors
    do not overwrite each other when built in sequence.
    """
    if not (src_dir / manifest).is_file():
        raise FileNotFoundError(f"manifest not found: {src_dir / manifest}")

    target_dir = out_dir / flavor
    target_dir.mkdir(parents=True, exist_ok=True)

    argv = build_dp_argv(
        driverpackager=driverpackager,
        src_dir=src_dir,
        out_dir=target_dir,
        flavor=flavor,
        manifest=manifest,
        verbose=verbose,
    )
    runner(argv, check=True, cwd=src_dir)

    produced = list(target_dir.glob("*.c4z"))
    if not produced:
        raise RuntimeError(f"driverpackager produced no .c4z in {target_dir}")
    return produced[0]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build .c4z Control4 driver packages.",
    )
    parser.add_argument(
        "flavor",
        choices=(*FLAVORS, "both"),
        help="Build flavor: 'dev' (-ae), 'release' (clean), or 'both'.",
    )
    parser.add_argument(
        "--src-dir",
        type=Path,
        default=DEFAULT_SRC_DIR,
        help=f"Driver source directory (default: {DEFAULT_SRC_DIR}).",
    )
    parser.add_argument(
        "--manifest",
        default=DEFAULT_MANIFEST,
        help=f"Manifest filename relative to --src-dir (default: {DEFAULT_MANIFEST}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output root (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--driverpackager-path",
        type=Path,
        default=None,
        help="Path to driverpackager.py (or its containing directory).",
    )
    parser.add_argument(
        "--auto-clone",
        action="store_true",
        help="Clone snap-one/drivers-driverpackager into .cache/ if not found.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress driverpackager's -v flag.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if shutil.which("git") is None and args.auto_clone:
        print("error: --auto-clone requires `git` on PATH", file=sys.stderr)
        return 2

    try:
        driverpackager = resolve_driverpackager(
            explicit=args.driverpackager_path,
            auto_clone=args.auto_clone,
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    flavors = FLAVORS if args.flavor == "both" else (args.flavor,)
    for flavor in flavors:
        produced = build_one(
            flavor=flavor,
            src_dir=args.src_dir,
            out_dir=args.output_dir,
            driverpackager=driverpackager,
            manifest=args.manifest,
            verbose=not args.quiet,
        )
        print(f"built {flavor}: {produced}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
