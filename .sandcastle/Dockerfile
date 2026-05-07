FROM python:3.12-slim-bookworm

# System deps: git/curl/jq for sandcastle's worktree + prompt expansion,
# build-essential for any C extensions in transitive deps.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl jq ca-certificates build-essential \
  && rm -rf /var/lib/apt/lists/*

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

# Project venv — pre-baked into the image so cold start is fast.
# The per-iteration hook in main.mts runs `pip install -e '.[dev]'`
# against the bind-mounted workspace, populating this venv with the project
# in editable mode plus dev tools (pytest, ruff).
RUN python -m venv /home/agent/.venv \
  && /home/agent/.venv/bin/pip install --upgrade pip
ENV PATH="/home/agent/.venv/bin:/home/agent/.local/bin:$PATH"

# Sandcastle's Docker provider passes `--user ${hostUid}:${hostGid}` from the
# host. On macOS that's typically 501, not the 1000 we used at build time. Make
# /home/agent and its contents writable by any UID so sandcastle can write
# .gitconfig and the per-iteration `pip install -e '.[dev]'` can populate the
# venv regardless of which UID the host uses.
USER root
RUN chmod -R a+rwX /home/agent
USER agent

WORKDIR /home/agent

# In worktree sandbox mode, Sandcastle bind-mounts the git worktree at
# /home/agent/workspace and overrides the working directory there at container
# start. Structure your Dockerfile so /home/agent/workspace can serve as the
# project root.
ENTRYPOINT ["sleep", "infinity"]
