#!/usr/bin/env bash
# PreToolUse(Bash) guard: deny attempts to bypass the pre-commit gate.
#
# Thin wrapper. The detection lives in deny_commit_bypass.py (tokenizes the
# command so a --no-verify in a commit *message*, or a -n on a neighbouring
# command in a compound line, is not mistaken for the flag). This wrapper exists
# only so settings.json can invoke a stable path and so we fail OPEN when python3
# is unavailable -- a guard that cannot run must never block a Bash call.
#
# Always exits 0; any deny decision travels as JSON on the Python script's
# stdout. See deny_commit_bypass.py for scope and the (deliberately accepted)
# out-of-scope bypasses.
set -uo pipefail

# Allow when python3 is missing rather than wedge every Bash call.
command -v python3 >/dev/null 2>&1 || exit 0

dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || exit 0

# exec so the tool-input JSON on our stdin flows straight into the script, which
# always exits 0 (deny travels in its stdout).
exec python3 "$dir/deny_commit_bypass.py"
