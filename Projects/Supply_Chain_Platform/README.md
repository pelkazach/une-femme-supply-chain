# Une Femme Wine Supply Chain Intelligence Platform

A supply chain intelligence platform that replaces manual Excel workbooks with real-time inventory tracking, forecasting, and automated alerting for Une Femme's wine SKUs.

## Setup

```bash
poetry install
```

## Development

```bash
# Run tests
poetry run pytest

# Run linter
poetry run ruff check src/

# Run type checker
poetry run mypy src/

# Start development server
poetry run uvicorn src.api.main:app --reload
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

- `DATABASE_URL` - PostgreSQL connection string
- `WINEDIRECT_CLIENT_ID` - WineDirect API client ID
- `WINEDIRECT_CLIENT_SECRET` - WineDirect API client secret
- `REDIS_URL` - Redis connection string for Celery
- `SLACK_WEBHOOK_URL` - Slack webhook for alerts
