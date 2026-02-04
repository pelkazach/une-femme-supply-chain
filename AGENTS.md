# Project Commands

Build, test, and validation commands for the Une Femme Supply Chain Platform.

## Prerequisites

```bash
# Install Python dependencies
cd Projects/Supply_Chain_Platform
poetry install

# Install Railway CLI
npm install -g @railway/cli
railway login
railway link
```

## Build

```bash
# Install dependencies
cd Projects/Supply_Chain_Platform && poetry install
```

## Test

```bash
# Run all tests
cd Projects/Supply_Chain_Platform && poetry run pytest

# Run with coverage
cd Projects/Supply_Chain_Platform && poetry run pytest --cov=src --cov-report=term-missing

# Run specific test file
cd Projects/Supply_Chain_Platform && poetry run pytest tests/test_metrics.py -v
```

## Typecheck

```bash
# Run mypy type checking
cd Projects/Supply_Chain_Platform && poetry run mypy src/
```

## Lint

```bash
# Run ruff linter
cd Projects/Supply_Chain_Platform && poetry run ruff check src/

# Run ruff with auto-fix
cd Projects/Supply_Chain_Platform && poetry run ruff check src/ --fix
```

## Format

```bash
# Format code with ruff
cd Projects/Supply_Chain_Platform && poetry run ruff format src/
```

## Validate All

```bash
# Run all checks (lint, typecheck, test)
cd Projects/Supply_Chain_Platform && poetry run ruff check src/ && poetry run mypy src/ && poetry run pytest
```

## Database

```bash
# Run migrations (via Railway)
cd Projects/Supply_Chain_Platform && railway run alembic upgrade head

# Create new migration
cd Projects/Supply_Chain_Platform && railway run alembic revision --autogenerate -m "description"

# Check current migration version
cd Projects/Supply_Chain_Platform && railway run alembic current
```

## Deploy

```bash
# Deploy to Railway
railway up

# Or use Claude Code skill
/railway:deploy
```

## Local Development

```bash
# Start local server
cd Projects/Supply_Chain_Platform && poetry run uvicorn src.main:app --reload

# Pull Railway environment variables
cd Projects/Supply_Chain_Platform && railway run env > .env.local
```

## Monitoring

```bash
# View Railway logs
railway logs

# Check Railway status
railway status

# Or use Claude Code skills
/railway:logs
/railway:status
```

## Quick Validation Commands

| Check | Command |
|-------|---------|
| Lint only | `cd Projects/Supply_Chain_Platform && poetry run ruff check src/` |
| Types only | `cd Projects/Supply_Chain_Platform && poetry run mypy src/` |
| Tests only | `cd Projects/Supply_Chain_Platform && poetry run pytest` |
| Full validation | See "Validate All" above |
