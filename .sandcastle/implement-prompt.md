# TASK

Fix issue {{TASK_ID}}: {{ISSUE_TITLE}}

Pull in the issue using `gh issue view <ID>`. If it has a parent PRD, pull that in too.

Only work on the issue specified.

Work on branch {{BRANCH}}. Make commits and run tests.

# CONTEXT

Here are the last 10 commits:

<recent-commits>

!`git log -n 10 --format="%H%n%ad%n%B---" --date=short`

</recent-commits>

# EXPLORATION

Explore the repo and fill your context window with relevant information that will allow you to complete the task.

Pay extra attention to test files that touch the relevant parts of the code.

# EXECUTION

If applicable, use RGR to complete the task.

1. RED: write one test
2. GREEN: write the implementation to pass that test
3. REPEAT until done
4. REFACTOR the code

# FEEDBACK LOOPS

Before committing, run:

- `ruff check blustream tests`
- `pytest`

Both must pass.

# COMMIT

Make a git commit using [Conventional Commits](https://www.conventionalcommits.org/):

    <type>(<optional scope>): <description>

    <optional body>

    <optional footer>

- `<type>` is one of: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `chore`, `build`, `ci`
- `<scope>` names the affected area (e.g. `dmp168`, `cli`, `connection`, `base`)
- Subject ≤ 72 chars, imperative mood, no trailing period
- Body explains the why and key decisions; wrap at 72
- Footer references the issue: `Refs: #{{TASK_ID}}` (or `Closes: #{{TASK_ID}}` if the work fully resolves it)

Keep it concise.

# THE ISSUE

If the task is not complete, leave a comment on the issue with what was done.

Do not close the issue - this will be done later.

Once complete, output <promise>COMPLETE</promise>.

# FINAL RULES

ONLY WORK ON A SINGLE TASK.
