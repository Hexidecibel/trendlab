# Work on Planned Items

Implement items from plan.md using TDD.

## Instructions

1. Read `plan.md`

2. Find the next item with **Status: planned** or **Status: in-progress**

3. For each item, follow TDD:

   a. **Write tests first**
      - Create/update test files based on "Tests Needed" section
      - Run tests - they should fail (red):
        ```bash
        uv run pytest
        ```

   b. **Implement the feature**
      - Follow the "Implementation Steps" from plan
      - Install any dependencies listed:
        ```bash
        uv add <package>
        ```
      - Make tests pass (green)
      - Run linter:
        ```bash
        uv run ruff check . && uv run ruff format .
        ```

   c. **Refactor if needed**
      - Clean up code while keeping tests green

   d. **Commit**
      - Commit with descriptive message
      - Update plan.md status to "done"
      - Update todo.md checkbox to `- [x]`

4. When ALL items for a phase in plan.md are done:

   a. **Run full test suite**
      ```bash
      uv run pytest -v
      ```

   b. **Run linter**
      ```bash
      uv run ruff check .
      ```

   c. **Report completion**
      - List all commits made
      - Summarize what was built
      - Ask if ready to move to next phase

## Rules

- Tests first, always
- Commit after each completed item
- NO push without explicit approval
- Ask if stuck or unclear
- Follow the project structure from CLAUDE.md
