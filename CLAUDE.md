# Claude Code Instructions

## Project Context

This is the Une Femme Wine Supply Chain Intelligence Platform - a system to replace manual Excel workbooks with real-time inventory tracking, forecasting, and automated alerting.

## Tech Stack

- **Backend**: Python 3.11+ with FastAPI
- **Database**: PostgreSQL 17 on Railway (standard PostgreSQL, no TimescaleDB)
- **Queue**: Celery with Redis
- **Forecasting**: Prophet
- **Agents**: LangGraph
- **OCR**: Azure Document Intelligence
- **Dashboard**: Redash
- **Hosting**: Railway (backend + database)

## Key Commands

```bash
# Development
cd Projects/Supply_Chain_Platform
python -m pytest                    # Run tests
python -m mypy src/                 # Type checking
python -m ruff check src/           # Linting

# Database
railway run alembic upgrade head    # Run migrations

# Deployment
/railway:deploy                     # Deploy to Railway
/railway:status                     # Check deployment
/railway:logs                       # View logs
```

## Project Structure

```
Projects/Supply_Chain_Platform/
├── src/
│   ├── api/                 # FastAPI routes
│   ├── models/              # SQLAlchemy models
│   ├── services/            # Business logic
│   │   ├── winedirect.py    # WineDirect API client
│   │   ├── distributor.py   # File processing
│   │   ├── metrics.py       # DOH calculations
│   │   └── forecast.py      # Prophet forecasting
│   ├── agents/              # LangGraph agents
│   └── config.py            # Settings
├── tests/
├── migrations/              # Alembic migrations
└── pyproject.toml
```

## Database Schema

Core tables:
- `products` - 4 SKUs (UFBub250, UFRos250, UFRed250, UFCha250)
- `warehouses` - Storage locations
- `distributors` - RNDC, Southern Glazers, Winebow, etc.
- `inventory_events` - Time-series data with BRIN index
- `forecasts` - Prophet forecast results

## Environment Variables

Required for Railway:
```
DATABASE_URL=postgresql://...
WINEDIRECT_CLIENT_ID=...
WINEDIRECT_CLIENT_SECRET=...
AZURE_DOC_INTELLIGENCE_ENDPOINT=...
AZURE_DOC_INTELLIGENCE_KEY=...
SLACK_WEBHOOK_URL=...
```

## Development Guidelines

1. **Read specs first** - Check `specs/` for detailed requirements before implementing
2. **Follow existing patterns** - Match code style in existing files
3. **Write tests** - Every feature needs tests
4. **Update IMPLEMENTATION_PLAN.md** - Mark tasks complete after finishing
5. **Commit frequently** - Small, focused commits with clear messages

## Ralph Loop

This project uses the Ralph methodology:
- `IMPLEMENTATION_PLAN.md` - Task checklist
- `specs/` - Detailed feature specs
- `./loop.sh build` - Autonomous development loop

When working on a task:
1. Read the task from IMPLEMENTATION_PLAN.md
2. Check the corresponding spec in `specs/`
3. Implement the feature
4. Run tests to verify
5. Mark task complete in IMPLEMENTATION_PLAN.md
6. Commit changes

## Useful Specs Reference

| Feature | Spec File |
|---------|-----------|
| Database setup | specs/01-database-schema.md |
| WineDirect API | specs/02-winedirect-integration.md |
| File processing | specs/03-distributor-data-processing.md |
| Metrics | specs/04-inventory-metrics.md |
| Forecasting | specs/05-demand-forecasting.md |
| Dashboards | specs/06-dashboard-alerting.md |
