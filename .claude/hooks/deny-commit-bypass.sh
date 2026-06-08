#!/usr/bin/env bash
# PreToolUse(Bash) guard: deny attempts to bypass the pre-commit gate.
#
# Claude Code runs this before every Bash tool call, passing the tool input as
# JSON on stdin. We inspect the command and, if it is a `git commit` that skips
# hooks (--no-verify / -n) or disables them inline via core.hooksPath, we return
# a PreToolUse "deny" decision so the command never runs.
#
# Scope: this governs Claude Code AGENTS only -- this repo's interactive
# sessions and the sandcastle in-sandbox agents. It does not (and cannot)
# affect a human committing in a plain terminal; for that, rely on the git-side
# hook and CI.
#
# Deliberately narrow to avoid false denials: the bypass checks only fire on a
# command that actually carries a `git ... commit`, so legit setup like
# `git config core.hooksPath .githooks` (no commit) is allowed. A two-step
# bypass (disable hooks in one command, commit in another) is out of scope --
# the target is the reflexive `--no-verify`, not deliberate sabotage.
#
# Fails OPEN on any internal error (missing jq, malformed input) rather than
# wedging every Bash call. Always exits 0; the decision travels in stdout JSON.
set -uo pipefail

input="$(cat)"

cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // ""' 2>/dev/null)" || exit 0
[ -n "$cmd" ] || exit 0

emit_deny() {
  # $1 = human-readable reason. jq -Rn safely JSON-encodes it.
  jq -Rn --arg r "$1" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
}

# Only inspect commands that actually run `git ... commit`. Require both a `git`
# word and a `commit` subcommand token so unrelated text ("deny-commit-bypass",
# "svn commit", a grep for the flag) doesn't trip the guard.
if printf '%s' "$cmd" | grep -Eq '(^|[^[:alnum:]_])git([[:space:]]|$)' \
   && printf '%s' "$cmd" | grep -Eq '(^|[[:space:]])commit([[:space:]]|$)'; then

  # core.hooksPath set inline on the commit (e.g. `git -c core.hooksPath=...
  # commit`) neuters every hook -- check the whole command, since it precedes
  # the `commit` token.
  if printf '%s' "$cmd" | grep -Eq 'core\.hooksPath'; then
    emit_deny "Blocked: 'git -c core.hooksPath=... commit' disables the pre-commit gate. Commit without overriding core.hooksPath."
  fi

  # --no-verify / -n: look only AFTER the first `commit` token so a flag on an
  # earlier subcommand (e.g. `git clean -n && git commit`) is not misread.
  rest="${cmd#*commit}"
  if printf '%s' "$rest" | grep -Eq '(^|[[:space:]])--no-verify([[:space:]]|=|$)'; then
    emit_deny "Blocked: 'git commit --no-verify' bypasses the pre-commit gate. Commit normally; if the pre-commit hook cannot run (e.g. pre-commit not installed), fix that instead of bypassing."
  fi
  if printf '%s' "$rest" | grep -Eq '(^|[[:space:]])-[A-Za-z]*n[A-Za-z]*([[:space:]]|=|$)'; then
    emit_deny "Blocked: 'git commit -n' (short for --no-verify) bypasses the pre-commit gate. Drop -n and commit normally."
  fi
fi

exit 0
