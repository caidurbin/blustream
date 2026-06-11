"""Regression suite for the commit-bypass guard (.claude/hooks/deny_commit_bypass.py).

The guard is a Claude Code PreToolUse(Bash) hook that denies attempts to skip the
pre-commit gate. It must (a) catch the reflexive bypasses, (b) NOT block a
legitimate commit whose message merely mentions the tokens, or a neighbouring
command in a compound line, and (c) fail OPEN on malformed input. Each case
below is one of those guarantees; the file mentions ``--no-verify`` /
``core.hooksPath`` only as test data, never as a real flag.
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys

import pytest

_HOOK = (
    pathlib.Path(__file__).resolve().parents[1]
    / ".claude"
    / "hooks"
    / "deny_commit_bypass.py"
)

_spec = importlib.util.spec_from_file_location("deny_commit_bypass", _HOOK)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


# --- must DENY: real bypasses, including compound lines and short clusters ---
DENY = [
    "git commit --no-verify",
    'git commit -m "x" --no-verify',
    'git commit -n -m "x"',
    'git commit -nm "x"',
    "git commit -an",
    "git commit -nv",
    "git -c core.hooksPath=/dev/null commit -m x",
    "git -c core.hooksPath= commit",
    "git add -A && git commit --no-verify",
    'git commit -m"x" --no-verify',
    "git commit --no-verify&&git push",  # no spaces around the operator
    "foo=bar git commit --no-verify",  # env-prefixed git invocation
    # newline-separated commands (shlex treats \n as whitespace, so these must
    # be normalised to separators or the bypass on a later line is missed)
    "git add -A\ngit commit --no-verify",
    "git status\ngit commit -n",
    "cat <<EOF\nx\nEOF\ngit commit --no-verify",  # here-doc then the bypass
    "if true; then git commit --no-verify; fi",  # leading shell keyword
    "git commit -nu",  # real -n precedes -u (--untracked-files), still a bypass
    "git commit -uno -n",  # legit -uno, but a real -n token follows
]

# --- must ALLOW: the false-positive classes the hardening fixes, plus normals.
ALLOW = [
    'git commit -m "x"',
    "git commit",
    "git commit -av",
    # message/heredoc bodies that merely mention the tokens
    'git commit -m "msg with --no-verify"',
    'git commit -m "refactor core.hooksPath handling"',
    'git commit -m "drop the -n shortcut"',
    'git commit -m "can\'t --no-verify yet"',
    "git commit -F - <<'EOF'\nbody mentions --no-verify here\nEOF",
    # a flag in a message *value* position is data, not a flag
    "git commit -m -n",
    "git commit -am --no-verify",
    # a real -n / core.hooksPath on a *different* command in the line
    'git commit -m "x" && git log -n 10',
    'git commit -m "x" && grep -rn TODO src/',
    'git commit -m "x" && head -n 20 CHANGELOG.md',
    "git config core.hooksPath .githooks && git commit -m wip",
    "git log --grep=commit -n 5 && git commit -am wip",
    # not a git commit at all
    "git switch -n feat",
    'echo "use --no-verify to skip"',
    'git commit -m "x"&&git push',
    # a real -n / commit on a *different* command on a later newline
    "git commit -m x\ngit log -n 5",
    "git commit -F - <<EOF\nmsg\nEOF\ngit log -n 5",
    # attached message whose value contains the letter n (not the -n flag)
    'git commit -m"fix in parser"',
    "git commit -mdone",
    'git commit -am"green"',
    "git commit -mn",  # message is literally "n"
    "git commit -m 'a\nb'",  # newline inside a quoted message stays data
    # attached-value short options whose value contains an "n" are not the -n flag
    "git commit -uno",  # --untracked-files=no
    "git commit -unormal -m wip",  # --untracked-files=normal, then a message
    "git commit -Sname",  # --gpg-sign=<keyid containing n>
    "git commit -S -m wip",  # bare --gpg-sign (default key), never eats "wip"
]

# --- must fail OPEN (allow) on malformed input rather than wedge ---
FAIL_OPEN = [
    "",
    'git commit --no-verify "oops',  # unbalanced quote -> shlex ValueError
]


@pytest.mark.parametrize("cmd", DENY)
def test_bypasses_are_denied(cmd: str) -> None:
    assert guard.decide(cmd) is not None, cmd


@pytest.mark.parametrize("cmd", ALLOW)
def test_legitimate_commands_are_allowed(cmd: str) -> None:
    assert guard.decide(cmd) is None, cmd


@pytest.mark.parametrize("cmd", FAIL_OPEN)
def test_malformed_input_fails_open(cmd: str) -> None:
    assert guard.decide(cmd) is None, cmd


# --- main(): the stdin/stdout/exit-code contract Claude Code relies on ---
def _run_main(stdin: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, str(_HOOK)], input=stdin, capture_output=True
    )


@pytest.mark.parametrize(
    "stdin",
    [b"", b"   ", b"not json", b"null", b"[]", b'{"tool_input": null}', b"{}"],
)
def test_main_fails_open_and_never_blocks(stdin: bytes) -> None:
    # Any malformed payload: exit 0 (never 2 = block) with no deny on stdout.
    result = _run_main(stdin)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == b""


def test_main_emits_deny_for_real_bypass() -> None:
    result = _run_main(b'{"tool_input": {"command": "git commit --no-verify"}}')
    assert result.returncode == 0
    assert b'"permissionDecision": "deny"' in result.stdout


def test_main_allows_message_mention() -> None:
    payload = b'{"tool_input": {"command": "git commit -m \\"note --no-verify\\""}}'
    result = _run_main(payload)
    assert result.returncode == 0
    assert result.stdout.strip() == b""
