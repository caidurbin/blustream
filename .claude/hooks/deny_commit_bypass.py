#!/usr/bin/env python3
"""PreToolUse(Bash) guard: deny attempts to bypass the pre-commit gate.

Claude Code runs this before every Bash tool call, passing the tool input as
JSON on stdin. We inspect ``.tool_input.command`` and, if it runs a ``git
commit`` that skips hooks (``--no-verify`` / ``-n``) or disables them inline via
``-c core.hooksPath=...``, we emit a PreToolUse "deny" so the command never runs.

Why tokenize instead of grep the raw string? Two independent traps sink a
naive scan:

  * data-vs-flag -- ``git commit -m "mentions --no-verify"`` carries the token
    inside a *message*, not as a flag; and
  * which-command-owns-it -- ``git commit -m x && git log -n 10`` carries a real
    ``-n`` on a *different* command in the same line.

So we strip heredoc bodies, split on shell operators, and inspect only the argv
of the segment that actually runs ``git ... commit`` -- skipping the values of
message-bearing options so a flag quoted as a message value is not misread.

Scope: this governs Claude Code AGENTS only (interactive sessions + the
sandcastle in-sandbox agents). It cannot affect a human in a plain terminal --
for that, rely on the git-side hook, the sandbox ``git`` shim, and CI. It is a
guardrail against the *reflexive* ``--no-verify``, not a security boundary:
deliberately quoted/obfuscated flags (``git commit '--no-verify'``,
``git $(echo commit) -n``) and env-var skips (``SKIP=hook git commit``) are out
of scope by design.

Fails OPEN on any error (bad/empty input, parse failure, missing deps): it
prints nothing and exits 0, so a guard bug never wedges Bash. It NEVER exits 2
(PreToolUse exit 2 = block), so an internal error can only allow, never deny.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

# Heredoc opener through its closing delimiter line. The closer must be a full
# line equal to the delimiter (bash requires an exact match), so a body line
# like "EOF and notes" does not close it early. Covers <<EOF, <<-EOF, <<'EOF',
# <<"EOF". We replace the whole span with a space so a --no-verify mentioned in
# a here-doc message is never tokenized as a flag.
_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?\n[ \t]*\2[ \t]*(?:\n|$)", re.S)

# Shell operators that separate one simple-command from the next. We split the
# token stream on these so a flag on a neighbouring command is never attributed
# to the commit. (Bare newlines are normalised to `;` before tokenizing -- see
# decide() -- because shlex treats a newline as ordinary whitespace.)
_OPERATORS = {"&&", "||", "|", "|&", "&", ";", ";;", "(", ")"}

# Leading NAME=value environment assignments before the command word.
_ENV_ASSIGN = re.compile(r"^\w+=")

# Leading shell keywords that can directly precede the command word in a
# one-liner (`if ...; then git commit --no-verify`, `for ...; do git commit -n`).
# Skipped like env assignments so the bypass on the guarded clause is still seen.
_LEADING_SKIP = {"then", "do", "else", "elif"}

# commit options that consume the following token as a value; a flag sitting in
# that value position (e.g. ``-m --no-verify``) is a message, not a bypass.
_VALUE_OPTS = {
    "-m",
    "--message",
    "-F",
    "--file",
    "-c",
    "--reedit-message",
    "-C",
    "--reuse-message",
    "-t",
    "--template",
    "--fixup",
    "--squash",
    "--author",
    "--date",
}
# Short value-option letters, for clustered forms like ``-am <msg>``.
_VALUE_LETTERS = set("mFcCt")

# git-level options (before the subcommand) that consume the following token.
_GIT_VALUE_OPTS = {
    "-C",
    "--git-dir",
    "--work-tree",
    "--namespace",
    "--exec-path",
    "--super-prefix",
}

_NO_VERIFY = (
    "Blocked: 'git commit --no-verify' bypasses the pre-commit gate. Commit "
    "normally; if the pre-commit hook cannot run (e.g. pre-commit not "
    "installed), fix that instead of bypassing."
)
_SHORT_N = (
    "Blocked: 'git commit -n' (short for --no-verify) bypasses the pre-commit "
    "gate. Drop -n and commit normally."
)
_HOOKSPATH = (
    "Blocked: 'git -c core.hooksPath=... commit' disables the pre-commit gate. "
    "Commit without overriding core.hooksPath."
)


def _segments(cmd: str) -> list[list[str]]:
    """Tokenize ``cmd`` and split into per-simple-command argv lists.

    Uses shlex with ``punctuation_chars`` so operators split even without
    surrounding whitespace (``a&&b``) and quoted spans collapse to one token.
    Raises ``ValueError`` on unbalanced quotes -- the caller fails open.
    """
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    segments: list[list[str]] = []
    current: list[str] = []
    for tok in lex:
        if tok in _OPERATORS:
            if current:
                segments.append(current)
                current = []
        else:
            current.append(tok)
    if current:
        segments.append(current)
    return segments


def _commit_argv(argv: list[str]) -> tuple[list[str], bool] | None:
    """If ``argv`` runs ``git ... commit``, return (commit-options, hooksPath?).

    ``commit-options`` are the tokens after the ``commit`` subcommand;
    ``hooksPath`` is True when a git-level ``-c core.hooksPath=...`` precedes it.
    Returns None when this segment is not a git-commit.
    """
    i = 0
    while i < len(argv) and (_ENV_ASSIGN.match(argv[i]) or argv[i] in _LEADING_SKIP):
        i += 1  # skip `FOO=bar` env prefixes and leading shell keywords
    if i >= len(argv) or os.path.basename(argv[i]) != "git":
        return None
    i += 1

    hookspath = False
    while i < len(argv):
        a = argv[i]
        if a == "-c":
            if i + 1 < len(argv) and re.match(r"core\.hooksPath=", argv[i + 1], re.I):
                hookspath = True
            i += 2
            continue
        if a.startswith("-c") and "=" in a and "core.hookspath=" in a.lower():
            hookspath = True
            i += 1
            continue
        if a in _GIT_VALUE_OPTS:
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        # first bare word is the subcommand
        return (argv[i + 1 :], hookspath) if a == "commit" else None
    return None


def _scan_commit_options(opts: list[str]) -> str | None:
    """Return a deny reason if commit ``opts`` carry --no-verify / -n."""
    j = 0
    while j < len(opts):
        a = opts[j]
        if a == "--":
            break  # end of options; the rest are pathspecs
        if a == "--no-verify":
            return _NO_VERIFY
        if a in _VALUE_OPTS:
            j += 2  # skip the option's value
            continue
        if a.startswith("--"):
            j += 1
            continue
        if a.startswith("-") and len(a) > 1:
            # Short-flag cluster. The first value-taking letter consumes the
            # rest of the cluster as its attached value (``-mfix``) or, if it is
            # the last letter, the next token (``-am <msg>``). ``n`` means
            # --no-verify only when it appears *before* that value letter, so a
            # message value that merely contains "n" (``-mdone``) is not misread.
            cluster = a[1:]
            consumes_next = False
            boolean_part = cluster
            for idx, ch in enumerate(cluster):
                if ch in _VALUE_LETTERS:
                    boolean_part = cluster[:idx]
                    consumes_next = idx == len(cluster) - 1
                    break
            if "n" in boolean_part:
                return _SHORT_N
            if consumes_next:
                j += 2
                continue
        j += 1
    return None


def decide(cmd: str) -> str | None:
    """Return a deny reason for ``cmd``, or None to allow.

    Never raises: any internal failure returns None (allow).
    """
    try:
        # Cheap necessary condition: no `commit` token anywhere -> nothing to do.
        # Also bounds the cost of the regex/shlex work below on pathological,
        # commit-free input.
        if not cmd or "commit" not in cmd:
            return None
        # Collapse heredoc bodies AND bare newlines to an explicit `;` separator.
        # shlex treats a newline as ordinary whitespace, so without this a
        # multi-line script (`git add -A\ngit commit --no-verify`) would tokenize
        # into one argv blob and the bypass on a later line would be missed.
        # Newlines inside quotes stay data -- shlex honours the quoting.
        cmd = _HEREDOC.sub(" ; ", cmd)
        cmd = cmd.replace("\n", " ; ")
        try:
            segments = _segments(cmd)
        except ValueError:
            return None  # unbalanced quotes etc. -> fail open
        for argv in segments:
            found = _commit_argv(argv)
            if found is None:
                continue
            opts, hookspath = found
            if hookspath:
                return _HOOKSPATH
            reason = _scan_commit_options(opts)
            if reason:
                return reason
        return None
    except Exception:
        return None


def main() -> None:
    """Read the hook payload from stdin; emit a deny decision if warranted.

    Always exits 0 and only ever prints a deny on stdout, so a failure here can
    never block a command (no exit 2).
    """
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        tool_input = data.get("tool_input") if isinstance(data, dict) else None
        cmd = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
        reason = decide(cmd if isinstance(cmd, str) else "")
        if reason:
            json.dump(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": reason,
                    }
                },
                sys.stdout,
            )
    except Exception:
        pass  # fail open: allow on any internal error
    sys.exit(0)


if __name__ == "__main__":
    main()
