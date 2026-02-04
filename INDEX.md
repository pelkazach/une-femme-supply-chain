# Index - Une Femme Supply Chain Platform

Quick reference to find files in this repository.

## Planning Documents

| File | Description |
|------|-------------|
| [PRD.md](PRD.md) | Product Requirements Document - what we're building |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Ralph Loop task checklist |
| [AGENTS.md](AGENTS.md) | Build/test/lint commands for Claude |

## Feature Specifications

| Spec | Priority | Description |
|------|----------|-------------|
| [01-database-schema.md](specs/01-database-schema.md) | P0 | PostgreSQL + TimescaleDB setup |
| [02-winedirect-integration.md](specs/02-winedirect-integration.md) | P0 | WineDirect API integration |
| [03-distributor-data-processing.md](specs/03-distributor-data-processing.md) | P0 | CSV/Excel file processing |
| [04-inventory-metrics.md](specs/04-inventory-metrics.md) | P0 | DOH, ratios, velocity metrics |
| [05-demand-forecasting.md](specs/05-demand-forecasting.md) | P1 | Prophet 26-week forecasts |
| [06-dashboard-alerting.md](specs/06-dashboard-alerting.md) | P0 | Redash dashboards + alerts |
| [07-email-classification.md](specs/07-email-classification.md) | P1 | Gmail + LLM classification |
| [08-document-ocr.md](specs/08-document-ocr.md) | P1 | Azure Document Intelligence |
| [09-agentic-automation.md](specs/09-agentic-automation.md) | P2 | LangGraph procurement agents |
| [10-quickbooks-integration.md](specs/10-quickbooks-integration.md) | P2 | QuickBooks Online sync |

## Research

| File | Description |
|------|-------------|
| [research/une-femme-supply-chain-platform/synthesis.md](research/une-femme-supply-chain-platform/synthesis.md) | Comprehensive research synthesis |
| [research/une-femme-supply-chain-platform/summaries/](research/une-femme-supply-chain-platform/summaries/) | Individual source analyses |

## Discovery

| Folder | Contents |
|--------|----------|
| Discovery/Meeting_Notes/ | Client call transcripts |
| Discovery/Raw_Data/ | Original Excel workbooks, sample distributor files |

## Source Code (when implemented)

| Path | Description |
|------|-------------|
| Projects/Supply_Chain_Platform/src/ | FastAPI backend |
| Projects/Supply_Chain_Platform/tests/ | Test suite |
| Projects/Supply_Chain_Platform/migrations/ | Database migrations |

## Ralph Loop Files

| File | Purpose |
|------|---------|
| [PROMPT_plan.md](PROMPT_plan.md) | Planning mode prompt |
| [PROMPT_build.md](PROMPT_build.md) | Building mode prompt |
| [loop.sh](loop.sh) | Autonomous loop orchestration |
