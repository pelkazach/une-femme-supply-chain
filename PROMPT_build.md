# Building Mode

You are in building mode for the Une Femme Wine Supply Chain Platform. Your job is to implement one task at a time.

## Phase 0: Orientation

1. Read `IMPLEMENTATION_PLAN.md` to find the highest-priority incomplete task
2. Read the corresponding spec file in `specs/`
3. Check `CLAUDE.md` for project conventions
4. Examine existing code to understand patterns

## Phase 1: Investigation

Before implementing, search the codebase:

1. **Check if already implemented** - Don't assume it's not done
2. **Find similar patterns** - Match existing code style
3. **Identify dependencies** - What needs to exist first?

If the task depends on an incomplete task, note this and move to the next available task.

## Phase 2: Implementation

Implement the task following these rules:

1. **One task only** - Complete a single task per iteration
2. **Follow the spec** - Match acceptance criteria exactly
3. **Write tests** - Every feature needs tests
4. **Use existing patterns** - Don't invent new conventions

### Code Location

```
Projects/Supply_Chain_Platform/
├── src/
│   ├── api/              # FastAPI routes
│   ├── models/           # SQLAlchemy models
│   ├── services/         # Business logic
│   ├── agents/           # LangGraph agents
│   └── config.py         # Settings
├── tests/
└── migrations/           # Alembic migrations
```

### Key Dependencies

- FastAPI for API routes
- SQLAlchemy for ORM
- Alembic for migrations
- Prophet for forecasting
- LangGraph for agents
- httpx for async HTTP clients

## Phase 3: Validation

Before marking complete:

1. **Run tests**: `poetry run pytest`
2. **Run linter**: `poetry run ruff check src/`
3. **Run typecheck**: `poetry run mypy src/`

All checks must pass.

## Phase 4: Completion

1. **Update IMPLEMENTATION_PLAN.md**:
   - Mark the task as `[x]` complete
   - Add any discoveries to the Discoveries section

2. **Commit changes**:
   ```
   git add .
   git commit -m "Implement [task description]"
   ```

3. **Note next task** - Identify what should be done next

## Phase 999: Guardrails

- **One task per iteration** - Stop after completing one task
- **All tests must pass** - Don't commit failing tests
- **Update plan before exiting** - Mark task complete
- **Document discoveries** - If something doesn't match the spec, note it

## Quick Reference

| Action | Command |
|--------|---------|
| Run tests | `cd Projects/Supply_Chain_Platform && poetry run pytest` |
| Run linter | `cd Projects/Supply_Chain_Platform && poetry run ruff check src/` |
| Run typecheck | `cd Projects/Supply_Chain_Platform && poetry run mypy src/` |
| Run all | See AGENTS.md "Validate All" |

## Task Selection Priority

1. Foundation tasks (database, project setup)
2. P0 tasks in order (MVP requirements)
3. P1 tasks in order (automation)
4. P2 tasks in order (intelligence)

Within each priority, work in task number order (1.1.1 before 1.1.2).
