#!/usr/bin/env bash
# git PATH shim (sandbox only): refuse the pre-commit-gate bypasses that coding
# agents reach for -- `git commit --no-verify` / `-n` and inline
# `-c core.hooksPath=...`. Installed at /usr/local/bin/git so it shadows the real
# git at /usr/bin/git on PATH.
#
# Why a shim in addition to the host PreToolUse hook: this receives argv ALREADY
# tokenized by the kernel, so there is no shell string to mis-parse (no quoting /
# heredoc / compound-command edge cases), and it governs ALL tooling in the
# sandbox (Make, scripts, every agent), not just Claude Code's Bash tool.
#
# Scope: a guardrail against the reflexive bypass, NOT a security boundary.
# Deliberate evasion (a different git on PATH, `env -i`, two-step hook disabling)
# and pre-commit's own `SKIP=<hook>` env var are out of scope; CI is the backstop.
# On anything it does not understand it falls through to real git.
set -uo pipefail

# The real git. Overridable only to relocate the binary (or for tests) -- it
# does not weaken the guard, since the deny checks below run before this is ever
# exec'd.
REAL_GIT="${GIT_SHIM_REAL_GIT:-/usr/bin/git}"

args=("$@")
n=${#args[@]}
i=0
hookspath=0
sub=""
subidx=-1

# Phase 1: git-level options, up to the subcommand word.
while [ "$i" -lt "$n" ]; do
  a="${args[$i]}"
  case "$a" in
    -c)
      j=$((i + 1))
      if [ "$j" -lt "$n" ]; then
        # git config keys are case-insensitive; lower-case before matching.
        lc=$(printf '%s' "${args[$j]}" | tr '[:upper:]' '[:lower:]')
        case "$lc" in
          core.hookspath=*) hookspath=1 ;;
        esac
      fi
      i=$((i + 2))
      continue
      ;;
    --git-dir | --work-tree | -C | --namespace | --exec-path | --super-prefix)
      i=$((i + 2))
      continue
      ;;
    -*)
      i=$((i + 1))
      continue
      ;;
    *)
      sub="$a"
      subidx=$i
      break
      ;;
  esac
done

if [ "$sub" = "commit" ]; then
  if [ "$hookspath" -eq 1 ]; then
    echo "git-shim: refusing 'git -c core.hooksPath=... commit' -- it disables the pre-commit gate." >&2
    exit 1
  fi
  k=$((subidx + 1))
  while [ "$k" -lt "$n" ]; do
    a="${args[$k]}"
    case "$a" in
      --)
        break
        ;; # end of options; the rest are pathspecs
      --no-verify)
        echo "git-shim: refusing 'git commit --no-verify' -- it bypasses the pre-commit gate. pre-commit is installed in this image; commit normally." >&2
        exit 1
        ;;
      -m | --message | -F | --file | -c | --reedit-message | -C | --reuse-message \
        | -t | --template | --fixup | --squash | --author | --date)
        k=$((k + 2)) # skip the option's (space-separated) value
        continue
        ;;
      --*)
        k=$((k + 1))
        continue
        ;;
      -?*)
        # Short-flag cluster. The first value-taking letter (m/F/c/C/t) consumes
        # the rest of the cluster as its attached value (-mfix) or, if it is the
        # last letter, the next token (-am <msg>). `n` means --no-verify only
        # when it appears before that value letter, so a message value that
        # merely contains n (-mdone), or an attached-value option like -uno
        # (--untracked-files) / -Skeyid (--gpg-sign), is not misread.
        cluster="${a#-}"
        boolean_part="$cluster"
        consumes_next=0
        idx=0
        while [ "$idx" -lt "${#cluster}" ]; do
          case "${cluster:$idx:1}" in
            [mFcCt])
              boolean_part="${cluster:0:$idx}"
              [ "$idx" -eq "$((${#cluster} - 1))" ] && consumes_next=1
              break
              ;;
            [uS])
              # optional attached-only value: terminates the cluster but never
              # consumes the next token (-uno, -Skeyid, or bare -u/-S).
              boolean_part="${cluster:0:$idx}"
              break
              ;;
          esac
          idx=$((idx + 1))
        done
        case "$boolean_part" in
          *n*)
            echo "git-shim: refusing 'git commit -n' (short for --no-verify) -- it bypasses the pre-commit gate." >&2
            exit 1
            ;;
        esac
        [ "$consumes_next" -eq 1 ] && k=$((k + 2)) || k=$((k + 1))
        continue
        ;;
      *)
        k=$((k + 1))
        continue
        ;; # pathspec
    esac
  done
fi

exec "$REAL_GIT" "$@"
