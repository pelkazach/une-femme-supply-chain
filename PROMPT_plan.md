# Planning Mode

You are in planning mode for the Une Femme Wine Supply Chain Platform. Your job is to analyze the current state and update the implementation plan.

## Phase 0: Orientation

1. Read all specs in `specs/` directory to understand requirements
2. Study `IMPLEMENTATION_PLAN.md` to see current task status
3. Examine code structure in `Projects/Supply_Chain_Platform/` (if exists)
4. Read `CLAUDE.md` for project conventions

## Phase 1: Gap Analysis

Compare specifications against implemented code:

1. For each spec file in `specs/`:
   - List the acceptance criteria
   - Check if corresponding code exists
   - Note what's implemented vs missing

2. Review `IMPLEMENTATION_PLAN.md`:
   - Identify completed tasks
   - Flag any blocked tasks
   - Note tasks that may need re-sequencing

3. Check for integration gaps:
   - Do implemented features connect properly?
   - Are there missing dependencies?

## Phase 2: Synthesis

Update the implementation plan:

1. **Add new tasks** if discoveries require them
2. **Re-prioritize** if dependencies have changed
3. **Update task descriptions** if requirements are clearer
4. **Document blockers** in the Discoveries section

## Phase 3: Output

Write your findings to `IMPLEMENTATION_PLAN.md`:

1. Update task checkboxes for completed items
2. Add any new tasks discovered
3. Update the "Discoveries" section with:
   - Spec inconsistencies found
   - Technical blockers identified
   - Suggested approach changes

## Phase 999: Guardrails

- **NEVER implement code** during planning mode
- **ALWAYS update** IMPLEMENTATION_PLAN.md before exiting
- **ALWAYS capture** the "why" for each task change
- If a task is unclear, note the ambiguity - don't guess

## Planning Checklist

Before exiting planning mode, confirm:
- [ ] All specs reviewed
- [ ] IMPLEMENTATION_PLAN.md updated
- [ ] Discoveries section current
- [ ] No code was written
