# Une Femme Wine Supply Chain Intelligence Platform

A supply chain intelligence platform to replace Une Femme's manual Excel workbooks and weekly PDF reports with a real-time, automated system featuring agentic forecasting capabilities.

## Quick Start

```bash
# Start Claude Code and begin development
claude

# Deploy to Railway
/railway:deploy

# Check deployment status
/railway:status
```

## Project Overview

| Attribute | Value |
|-----------|-------|
| Client | Une Femme Wines |
| Status | Planning |
| Tech Stack | Python (FastAPI), PostgreSQL (Railway), Redash, LangGraph |
| SKUs | UFBub250, UFRos250, UFRed250, UFCha250 |

## Key Documents

| Document | Description |
|----------|-------------|
| [PRD.md](PRD.md) | Product Requirements Document |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Ralph Loop task checklist |
| [specs/](specs/) | Detailed feature specifications |
| [CLAUDE.md](CLAUDE.md) | Instructions for Claude Code |

## Project Structure

```
Une Femme Supply Forecast/
├── README.md                    ← You are here
├── INDEX.md                     ← Quick reference to find files
├── CLAUDE.md                    ← Instructions for Claude Code
├── PRD.md                       ← Product Requirements Document
├── IMPLEMENTATION_PLAN.md       ← Ralph Loop task list
│
├── Discovery_and_Final_Deliverables/
│   ├── Discovery/
│   │   ├── Meeting_Notes/       ← Client call notes
│   │   └── Raw_Data/            ← Original Excel workbooks
│   └── Final_Deliverables/
│       ├── Worksheets/          ← Cost estimates, timelines
│       ├── Summaries/           ← Executive summaries
│       └── Communications/      ← Client emails, drafts
│
├── Projects/
│   └── Supply_Chain_Platform/   ← Application source code
│
├── specs/                       ← Feature specifications (Ralph)
├── research/                    ← Deep research outputs
└── Templates/                   ← Reusable templates
```

## Development Workflow

1. **Research** - See `research/` for deep research synthesis
2. **PRD** - Requirements defined in `PRD.md`
3. **Ralph Loop** - Run `./loop.sh build` to execute tasks
4. **Deploy** - Use `/railway:deploy` to ship

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Sources                              │
├─────────────────────────────────────────────────────────────────┤
│  WineDirect API  │  Distributor CSV  │  Email (Gmail)           │
└────────┬─────────┴────────┬──────────┴────────┬─────────────────┘
         │                  │                   │
         ▼                  ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│              Railway (Backend + Database)                        │
├─────────────────────────────────────────────────────────────────┤
│  FastAPI  │  PostgreSQL  │  TimescaleDB  │  Celery Workers      │
└────────┬─────────────────┬─────────────────┬───────────────────┘
         │                 │                 │
         ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Presentation Layer                            │
├─────────────────────────────────────────────────────────────────┤
│         Redash Dashboard          │      Slack/Email Alerts     │
└─────────────────────────────────────────────────────────────────┘
```

## Team

- **Supply Chain Manager** - Primary user for inventory planning
- **Operations Coordinator** - Document processing user
- **Finance Director** - Financial reporting user
