# Coding Standards

The reviewer agent loads this via `@.sandcastle/CODING_STANDARDS.md` during code review, so these standards are enforced at review time without costing tokens during implementation.

## Style

- Python 3.12+ (see `pyproject.toml` `requires-python = ">=3.12"` and ADR-0013)
- Line length 88 (ruff / Black compatible)
- Run `ruff check blustream tests` and `ruff format` before committing
- Prefer `async`/`await` for device I/O — every public DMP168 method is async
- Use type hints on all public APIs

## Testing

- Tests live under `tests/`, discovered by `pytest` (see `pytest.ini`)
- `asyncio_mode = auto` — write async tests with plain `async def test_...`
- Every new public function needs at least one test
- Test names should describe behavior, not implementation

## Architecture

- New device types go under `blustream/devices/<name>/` and subclass the base in `blustream/base/`
- Connection transports (TCP, serial, ...) live under `blustream/connection/`
- CLI commands belong in `blustream/cli/`; keep device logic out of CLI modules

## Commits

- Use [Conventional Commits](https://www.conventionalcommits.org/): `<type>(<scope>): <description>`
- `<type>` ∈ `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `chore`, `build`, `ci`
- Subject ≤ 72 chars, imperative mood, no trailing period
