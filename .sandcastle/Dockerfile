# ── Builder: Go-based linters ────────────────────────────────────────────────
# betterleaks (secret-scan pre-commit hook + secret-scan.yml) and actionlint
# (workflow-lint gate per AGENTS.md + lint-actionlint.yml) are Go programs.
# Build them static (CGO_ENABLED=0) in a throwaway stage and copy just the
# binaries into the slim final image — no Go toolchain left behind. Versions
# are pinned to match CI and .pre-commit-config.yaml; bump deliberately.
FROM golang:1.25-bookworm AS gobuild
ENV CGO_ENABLED=0
RUN go install github.com/betterleaks/betterleaks@v1.4.1 \
 && go install github.com/rhysd/actionlint/cmd/actionlint@v1.7.12

# ── Final image ──────────────────────────────────────────────────────────────
# Python 3.14 matches test-ha.yml: pytest-homeassistant-custom-component pins
# one HA release, and current HA (>=2026.3) requires 3.14. The library/CLI
# suites run on it too, so a single interpreter covers every Python lane.
FROM python:3.14-slim-bookworm

# System deps:
#   git/curl/jq/build-essential/ca-certificates — sandcastle worktrees + prompts
#   shellcheck                                   — actionlint's run:-block checks
#   lua5.1 + liblua5.1-0-dev + luarocks          — luacheck (pre-commit) + busted
#   libyaml-dev                                  — lyaml build dep (Lua VectorRunner)
# Lua 5.1 is pinned because Control4 drivers run in the Composer Lua 5.1 sandbox
# (see .tool-versions, lint-control4.yml).
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl jq ca-certificates build-essential \
    shellcheck \
    lua5.1 liblua5.1-0-dev luarocks \
    libyaml-dev \
  && rm -rf /var/lib/apt/lists/*

# Go-built linters from the builder stage.
COPY --from=gobuild /go/bin/betterleaks /go/bin/actionlint /usr/local/bin/

# git PATH shim: shadows /usr/bin/git (PATH puts /usr/local/bin first) to refuse
# pre-commit-gate bypasses (`commit --no-verify`/`-n`, inline `-c core.hooksPath`)
# for ALL sandbox tooling, not just Claude Code's Bash tool. argv-based, so no
# shell-parsing edge cases. Belt-and-suspenders with the PreToolUse hook in
# .claude/hooks/. Falls through to real git for everything else.
COPY --chmod=0755 git-shim.sh /usr/local/bin/git

# Lua rocks for the luacheck pre-commit hook and the busted suite, pinned to the
# versions CI installs (lint-control4.yml / test-control4.yml). --lua-version
# targets the 5.1 interpreter installed above rather than luarocks' default.
RUN luarocks --lua-version 5.1 install luacheck 1.2.0 \
 && luarocks --lua-version 5.1 install busted 2.2.0 \
 && luarocks --lua-version 5.1 install lyaml

# GitHub CLI — planner uses `gh issue list/view`, merger uses `gh issue close`.
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
  && apt-get update && apt-get install -y gh \
  && rm -rf /var/lib/apt/lists/*

# Sandcastle requires UID 1000 named "agent" with home /home/agent.
# Keeping UID 1000 lets --userns=keep-id (Podman) and --user 1000:1000 (Docker)
# map to the correct home directory owner.
RUN useradd -m -u 1000 -s /bin/bash agent
USER agent

# Claude Code CLI
RUN curl -fsSL https://claude.ai/install.sh | bash

# Project venv — pre-baked into the image so cold start is fast. The
# per-iteration hook in main.mts runs `pip install -e '.[dev,codegen,c4z]'`
# against the bind-mounted workspace (editable project + pytest/ruff + the
# codegen and c4z test deps). Pre-install here the stable tooling that editable
# install does NOT cover:
#   pre-commit          — so `git commit` runs the hooks instead of erroring on
#                         a missing binary and getting bypassed with --no-verify
#   PHCC + syrupy       — the HA test stack (PHCC pins one HA release; syrupy is
#                         its snapshot dep), pinned to match test-ha.yml
# pre-commit provisions its managed hook envs (ruff, large-files) from the
# network on first run inside the sandbox; the system hooks (betterleaks,
# luacheck) use the binaries installed above.
RUN python -m venv /home/agent/.venv \
  && /home/agent/.venv/bin/pip install --upgrade pip \
  && /home/agent/.venv/bin/pip install \
       pre-commit \
       "pytest-homeassistant-custom-component>=0.13.329" \
       syrupy
ENV PATH="/home/agent/.venv/bin:/home/agent/.local/bin:$PATH"

# Sandcastle's Docker provider passes `--user ${hostUid}:${hostGid}` from the
# host. On macOS that's typically 501, not the 1000 we used at build time. Make
# /home/agent and its contents writable by any UID so sandcastle can write
# .gitconfig and the per-iteration `pip install -e` can populate the venv
# regardless of which UID the host uses.
USER root
RUN chmod -R a+rwX /home/agent
USER agent

WORKDIR /home/agent

# In worktree sandbox mode, Sandcastle bind-mounts the git worktree at
# /home/agent/workspace and overrides the working directory there at container
# start. Structure your Dockerfile so /home/agent/workspace can serve as the
# project root.
ENTRYPOINT ["sleep", "infinity"]
