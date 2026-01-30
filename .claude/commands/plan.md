# Plan from Todo

Process todo.md items into detailed implementation plans.

## Instructions

1. Read `/Users/chriscushman/local/src/trendlab/todo.md`

2. Read `/Users/chriscushman/local/src/trendlab/plan.md` (if exists)

3. For each unplanned item in todo.md:
   - Ask clarifying questions using AskUserQuestion
   - Understand the scope and requirements
   - Identify which files need changes
   - Consider edge cases and potential issues

4. Write detailed plan to `/Users/chriscushman/local/src/trendlab/plan.md`:
   ```markdown
   # Implementation Plan

   ## Item: <title>
   **Status:** planned | in-progress | done
   **Phase:** <which phase from todo.md>

   ### Requirements
   - <bullet points from discussion>

   ### Files to Create/Modify
   - `app/path/to/file.py` - <what changes>

   ### Implementation Steps
   1. <step>
   2. <step>

   ### Dependencies to Add
   - <package name> - <why needed>

   ### Tests Needed
   - <test case>

   ---
   ```

5. Mark items as planned in todo.md by changing `- [ ]` to `- [planned]`

## Rules

- NO CODING in this phase
- Ask questions if anything is unclear
- One item at a time unless user wants batch planning
- Keep plans focused and actionable
- Reference the phase structure in todo.md to maintain order
