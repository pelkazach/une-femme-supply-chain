# Executive Summary: Une Femme Supply Chain Platform

## Overview

The Une Femme Wine Supply Chain Intelligence Platform replaces manual Excel workbooks with an automated, real-time system for inventory tracking, demand forecasting, and supply chain management.

## Business Value

| Metric | Current State | Target |
|--------|---------------|--------|
| Data entry time | 10+ hours/week | <1 hour/week |
| Stock-out visibility | Days (manual) | Minutes (automated alerts) |
| Forecast accuracy | N/A | <12% MAPE (26-week) |
| Report generation | Weekly manual | Real-time dashboards |

## Scope

**4 Core SKUs**:
- UFBub250 - Une Femme Brut 250ml
- UFRos250 - Une Femme Rose 250ml
- UFRed250 - Une Femme Red 250ml
- UFCha250 - Une Femme Champagne 250ml

**Key Features**:
1. WineDirect API integration for depletion data
2. Distributor file processing (RNDC, Southern Glazers, Winebow)
3. Real-time inventory metrics (DOH_T30, DOH_T90, velocity ratios)
4. Threshold-based alerting via Slack/email
5. 26-week demand forecasting with Prophet
6. Document OCR for POs, BOLs, invoices (Phase 2)
7. AI-powered procurement recommendations (Phase 3)

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python (FastAPI) |
| Database | PostgreSQL + TimescaleDB on Railway |
| Queue | Celery + Redis |
| Forecasting | Prophet |
| Dashboards | Redash |
| Hosting | Railway |

## Implementation Phases

**Phase 1: MVP (P0)**
- Database setup with TimescaleDB
- WineDirect API integration
- Distributor file processing
- Core metrics calculation
- Redash dashboards with alerting

**Phase 2: Automation (P1)**
- Prophet demand forecasting
- Email classification with LLM
- Document OCR with Azure

**Phase 3: Intelligence (P2)**
- LangGraph procurement agents
- QuickBooks integration

## Cost Estimates

| Phase | Monthly Cost |
|-------|--------------|
| MVP | ~$145/month |
| Full Production | ~$750/month |

## Key Dependencies

1. WineDirect API access (contact Jeff Carroll)
2. 2+ years historical data for forecasting
3. Sample distributor files for parser testing

## Next Steps

1. Run `./loop.sh build` to begin autonomous development
2. Monitor progress in `IMPLEMENTATION_PLAN.md`
3. Deploy to Railway using `/railway:deploy`
