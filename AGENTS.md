# AGENTS.md

## Agent skills

### Issue tracker

Issues live as GitHub issues on `caidurbin/blustream`, managed via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical triage roles map 1:1 to label strings (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout: one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Editing GitHub Actions workflows

When you change any file under `.github/` (a workflow, `actionlint.yaml`, or a composite action), run `actionlint` before finishing and resolve everything it reports. It validates the Actions schema, type-checks `${{ }}` expressions, and runs shellcheck over `run:` blocks — catching mistakes a plain YAML parse can't. CI enforces the same check via `.github/workflows/lint-actionlint.yml`.

Install locally if missing (`brew install actionlint`); `shellcheck` must also be on `PATH` for the `run:`-block checks to run. See <https://github.com/rhysd/actionlint>.
