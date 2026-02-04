# Product Requirements Document
## Une Femme Wine Supply Chain Intelligence & Automation Platform

**Version**: 1.0
**Date**: February 3, 2026
**Author**: Product Team
**Status**: Draft

---

## 1. Executive Summary

### 1.1 Product Vision
Build a supply chain intelligence platform that replaces Une Femme's manual Excel workbooks and weekly PDF reports with a real-time, automated system featuring agentic forecasting capabilities for their four core champagne/wine SKUs (UFBub250, UFRos250, UFRed250, UFCha250).

### 1.2 Problem Statement
Une Femme currently manages supply chain operations through:
- A Master Sales and Supply Excel workbook with manual data entry
- Weekly PDF reports compiled manually from multiple distributor sources
- No automated alerting for stock-out risks
- Limited forecasting beyond historical averages
- Manual processing of purchase orders, bills of lading, and invoices

This creates operational inefficiency, delayed decision-making, and missed opportunities to optimize inventory levels.

### 1.3 Success Metrics
| Metric | Current State | Target |
|--------|---------------|--------|
| Data entry time | 10+ hours/week | <1 hour/week (automated) |
| Stock-out incidents | Unknown | Track and reduce by 50% |
| Forecast accuracy | N/A | MAPE <12% on 26-week horizon |
| Alert response time | Days (manual discovery) | Minutes (automated alerts) |
| Report generation | Weekly manual | Real-time dashboards |

---

## 2. User Personas & Jobs to Be Done

### 2.1 Primary Personas

**Supply Chain Manager (Sarah)**
- Responsible for inventory planning across all distributors
- Needs visibility into depletion rates and stock levels
- Makes procurement decisions based on forecasts

**Operations Coordinator (Mike)**
- Processes incoming POs, BOLs, and invoices
- Manages warehouse inventory adjustments
- Coordinates with distributors on shipments

**Finance Director (Lisa)**
- Tracks revenue recognition and COGS
- Manages cash flow based on AR/AP
- Needs forecast data for financial planning

### 2.2 Jobs to Be Done

| Job | Persona | Frequency |
|-----|---------|-----------|
| View current inventory levels by SKU and distributor | Sarah | Daily |
| Identify SKUs at risk of stock-out | Sarah | Daily |
| Generate 26-week demand forecast | Sarah | Weekly |
| Process incoming purchase orders | Mike | As received |
| Process bills of lading and track shipments | Mike | As received |
| Review inventory positions for financial reporting | Lisa | Weekly |
| Forecast cash flow based on sales projections | Lisa | Monthly |

---

## 3. Functional Requirements

### 3.1 Data Ingestion

#### 3.1.1 WineDirect API Integration
**Priority**: P0 (MVP Required)

**Description**: Automatically pull depletion and inventory data from WineDirect's ANWD REST APIs.

**Functional Requirements**:
- FR-1.1: Authenticate with WineDirect using Bearer Token
- FR-1.2: Pull inventory positions daily (sellable inventory endpoint)
- FR-1.3: Pull depletion events (inventory-out endpoint)
- FR-1.4: Pull 30/60/90-day velocity reports
- FR-1.5: Store all data in PostgreSQL with timestamps
- FR-1.6: Handle API errors with exponential backoff

**Acceptance Criteria**:
- Daily sync completes within 15 minutes
- All 4 SKUs have inventory and depletion data
- Velocity metrics match WineDirect dashboard (±1%)

**Technical Notes**:
- Contact Jeff Carroll (jeff.carroll@winedirect.com) for API access
- HTTPS required (mandatory after Feb 16, 2026)
- Use Inventory Velocity reports for depletion rate calculations

#### 3.1.2 Distributor File Processing
**Priority**: P0 (MVP Required)

**Description**: Process CSV/Excel files from distributors (RNDC, Southern Glazers, Winebow) to capture depletion and shipment data.

**Functional Requirements**:
- FR-2.1: Accept CSV file uploads via web interface
- FR-2.2: Accept Excel (.xlsx) file uploads
- FR-2.3: Parse RNDC report format
- FR-2.4: Parse Southern Glazers report format
- FR-2.5: Parse Winebow report format
- FR-2.6: Validate SKU codes against product master
- FR-2.7: Flag invalid rows with error messages
- FR-2.8: Insert valid data into inventory_events table

**Acceptance Criteria**:
- 100-row CSV processes in <5 seconds
- Invalid rows clearly identified with reason
- Successful imports reflected in dashboard within 1 minute

**Technical Notes**:
- Distributor APIs are limited; file-based is industry standard
- Support custom templates for additional distributors
- Distributor segments: Non-RNDC States, Georgia RNDC, Reyes 7 States, Other RNDC

### 3.2 Inventory Metrics

#### 3.2.1 Days on Hand Calculation
**Priority**: P0 (MVP Required)

**Description**: Calculate Days on Hand metrics based on trailing depletion rates.

**Functional Requirements**:
- FR-3.1: Calculate DOH_T30 (30-day trailing depletion rate)
- FR-3.2: Calculate DOH_T90 (90-day trailing depletion rate)
- FR-3.3: Update metrics automatically when new data arrives
- FR-3.4: Support filtering by SKU, warehouse, distributor segment
- FR-3.5: Handle zero-depletion edge cases gracefully

**Acceptance Criteria**:
- DOH calculations match Excel formulas within 1% variance
- Query response time <100ms for single SKU
- Historical DOH available for trend analysis

**Formula**:
```
DOH = Current Inventory / (Total Depletion over Period / Days in Period)
```

#### 3.2.2 Shipment/Depletion Ratios
**Priority**: P0 (MVP Required)

**Description**: Calculate ratios comparing shipments to depletions to identify supply/demand imbalances.

**Functional Requirements**:
- FR-4.1: Calculate A30_Ship:A30_Dep (30-day ratio)
- FR-4.2: Calculate A90_Ship:A90_Dep (90-day ratio)
- FR-4.3: Calculate A30:A90_Ship (shipment velocity trend)
- FR-4.4: Calculate A30:A90_Dep (depletion velocity trend)
- FR-4.5: Flag ratios indicating acceleration or deceleration

**Acceptance Criteria**:
- Ratios match Excel calculations within 1%
- Velocity trends correctly identify acceleration (>1.0) vs deceleration (<1.0)

### 3.3 Demand Forecasting

#### 3.3.1 26-Week Rolling Forecast
**Priority**: P1 (Phase 2)

**Description**: Generate 26-week demand forecasts using Prophet with champagne-specific seasonality.

**Functional Requirements**:
- FR-5.1: Train Prophet model on 2+ years historical data
- FR-5.2: Configure multiplicative seasonality for holiday spikes
- FR-5.3: Define holiday calendar (NYE, Valentine's, Mother's Day, Thanksgiving)
- FR-5.4: Generate weekly forecasts with point estimates
- FR-5.5: Generate 80% and 95% confidence intervals
- FR-5.6: Retrain models weekly with new data
- FR-5.7: Store forecasts in database for dashboard consumption

**Acceptance Criteria**:
- MAPE <12% on 26-week horizon (cross-validated)
- NYE forecast shows 5-8x baseline demand
- Weekly retraining completes in <5 minutes per SKU

**Technical Notes**:
- Prophet configuration: multiplicative seasonality, changepoint_prior_scale=0.05
- Minimum training data: 2 years (104 weeks)
- Champagne shows 7.5x demand spike on NYE (648% increase)

#### 3.3.2 Safety Stock Recommendations
**Priority**: P1 (Phase 2)

**Description**: Calculate recommended safety stock levels based on forecast uncertainty.

**Functional Requirements**:
- FR-6.1: Calculate safety stock from forecast intervals
- FR-6.2: Support configurable service level (default 95%)
- FR-6.3: Factor in supplier lead times
- FR-6.4: Generate reorder point recommendations

**Acceptance Criteria**:
- Safety stock recommendations reduce stock-outs by 50%
- Recommendations displayed in dashboard with justification

### 3.4 Dashboard & Visualization

#### 3.4.1 Operational KPI Dashboard
**Priority**: P0 (MVP Required)

**Description**: Real-time dashboard showing inventory KPIs with drill-down capabilities.

**Functional Requirements**:
- FR-7.1: Display DOH_T30, DOH_T90 for all 4 SKUs
- FR-7.2: Display shipment:depletion ratios
- FR-7.3: Display velocity trend indicators
- FR-7.4: Support filtering by SKU, distributor segment, date range
- FR-7.5: Auto-refresh every 5 minutes
- FR-7.6: Visual indicators for critical thresholds (red/yellow/green)

**Acceptance Criteria**:
- Dashboard loads in <3 seconds
- All metrics update within 5 minutes of data change
- Mobile-responsive design

**Technical Notes**:
- Use Redash for operational dashboards (superior alerting)
- 1-minute minimum refresh (Redash architectural constraint)

#### 3.4.2 Threshold-Based Alerting
**Priority**: P0 (MVP Required)

**Description**: Automated alerts when metrics cross defined thresholds.

**Functional Requirements**:
- FR-8.1: Alert when DOH_T30 < 14 days (stock-out risk)
- FR-8.2: Alert when DOH_T30 < 30 days (low stock warning)
- FR-8.3: Alert when A30:A90_Dep > 1.3 (demand acceleration)
- FR-8.4: Send alerts via Slack
- FR-8.5: Send alerts via email
- FR-8.6: Include SKU, current value, threshold in alert message

**Acceptance Criteria**:
- Alerts fire within 5 minutes of threshold breach
- No duplicate alerts for same condition
- Alert history viewable in dashboard

### 3.5 Document Processing

#### 3.5.1 Email Classification
**Priority**: P1 (Phase 2)

**Description**: Automatically classify incoming emails as POs, BOLs, invoices, or general correspondence.

**Functional Requirements**:
- FR-9.1: Connect to Gmail API for email retrieval
- FR-9.2: Classify emails using LLM (Ollama/Mixtral)
- FR-9.3: Route classified emails to appropriate processing queue
- FR-9.4: Extract attachments for OCR processing
- FR-9.5: Flag uncertain classifications for human review (<85% confidence)

**Acceptance Criteria**:
- Classification accuracy >94%
- Processing latency <15 seconds per email
- Human review queue accessible via dashboard

**Technical Notes**:
- Use local Ollama for cost efficiency (~50ms inference)
- RabbitMQ + Celery for distributed processing

#### 3.5.2 Document OCR & Extraction
**Priority**: P1 (Phase 2)

**Description**: Extract structured data from POs, BOLs, and invoices using OCR.

**Functional Requirements**:
- FR-10.1: Integrate with Azure Document Intelligence
- FR-10.2: Extract fields from purchase orders (PO#, vendor, items, quantities)
- FR-10.3: Extract fields from BOLs (shipper, consignee, tracking, cargo)
- FR-10.4: Extract fields from invoices (invoice#, amounts, line items)
- FR-10.5: Validate extracted data against business rules
- FR-10.6: Store extracted data in database with source document link

**Acceptance Criteria**:
- Field extraction accuracy >93%
- Processing time <3 seconds per document
- Invalid extractions flagged for human review

**Technical Notes**:
- Azure Document Intelligence: 93% field accuracy, 87% table accuracy
- Fallback to GPT-4o for edge cases (98% accuracy but 33s/page)

### 3.6 Procurement Automation

#### 3.6.1 AI Agent Orchestration
**Priority**: P2 (Phase 3)

**Description**: LangGraph-based agents for automated procurement workflows with human oversight.

**Functional Requirements**:
- FR-11.1: Implement demand forecaster agent
- FR-11.2: Implement inventory optimizer agent
- FR-11.3: Implement vendor analyzer agent
- FR-11.4: Implement orchestrator to coordinate agents
- FR-11.5: Implement approval gates for human review
- FR-11.6: Support workflow pause/resume/rewind

**Acceptance Criteria**:
- Agents generate procurement recommendations
- High-value orders (>$10K) require human approval
- Complete audit trail of agent decisions

**Technical Notes**:
- LangGraph for state machine architecture
- Native human-in-the-loop with interrupt/approve/resume
- Confidence-based routing: >85% auto-approve, 60-85% human review

#### 3.6.2 Purchase Order Generation
**Priority**: P2 (Phase 3)

**Description**: Generate draft purchase orders based on agent recommendations.

**Functional Requirements**:
- FR-12.1: Generate PO based on forecast and inventory position
- FR-12.2: Include safety stock buffer in quantity
- FR-12.3: Select vendor based on lead time and pricing
- FR-12.4: Route PO for approval based on value threshold
- FR-12.5: Track PO status (draft, pending approval, approved, sent)

**Acceptance Criteria**:
- PO quantities align with forecast + safety stock
- Approval workflow completes within configured SLA
- Sent POs tracked through fulfillment

### 3.7 Financial Integration

#### 3.7.1 QuickBooks Sync
**Priority**: P2 (Phase 3)

**Description**: Sync inventory and financial data with QuickBooks Online.

**Functional Requirements**:
- FR-13.1: Authenticate with QuickBooks via OAuth 2.0
- FR-13.2: Sync inventory levels to QuickBooks
- FR-13.3: Pull invoice and payment data from QuickBooks
- FR-13.4: Calculate revenue recognition from shipments
- FR-13.5: Support bi-directional sync

**Acceptance Criteria**:
- Inventory levels match between systems (±1%)
- Sync completes within 15 minutes of trigger
- OAuth token refresh handled automatically

**Technical Notes**:
- Use python-quickbooks library
- Rate limits: 500 req/min, 10 concurrent
- Optimize for write-heavy patterns (new pricing model)

---

## 4. Non-Functional Requirements

### 4.1 Performance
- Dashboard load time: <3 seconds
- API response time: <500ms (p95)
- Daily sync completion: <15 minutes
- Forecast generation: <5 minutes per SKU

### 4.2 Reliability
- System uptime: 99.5%
- Data durability: Daily backups with 30-day retention
- Failover: Automatic retry with exponential backoff

### 4.3 Security
- Authentication: OAuth 2.0 / JWT
- Authorization: Role-based access control (RBAC)
- Data encryption: TLS in transit, AES-256 at rest
- Audit logging: All data modifications logged

### 4.4 Scalability
- Support 4 SKUs initially, scalable to 50+
- Support 5 distributors initially, scalable to 20+
- Database: Handle 1M+ inventory events
- Real-time: Support 100 concurrent dashboard users

---

## 5. Technical Architecture

### 5.1 Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Database** | Supabase (PostgreSQL 15) | Real-time, RLS, Edge Functions |
| **Time-Series** | TimescaleDB | Hypertables, continuous aggregates |
| **Backend** | Python (FastAPI) | Prophet integration, async support |
| **Agent Framework** | LangGraph | State machines, HITL, production-ready |
| **Dashboard** | Redash | Threshold alerting, SQL-native |
| **Mobile Dashboard** | Retool | Bidirectional, native mobile |
| **Document AI** | Azure Document Intelligence | 93% accuracy, fast processing |
| **Email Processing** | Gmail API + Ollama | Cost-effective LLM classification |
| **Hosting** | Railway | Simple deployment, good pricing |

### 5.2 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Sources                              │
├─────────────────────────────────────────────────────────────────┤
│  WineDirect API  │  Distributor CSV  │  Email (Gmail)  │  QBO   │
└────────┬─────────┴────────┬──────────┴────────┬─────────┴───────┘
         │                  │                   │
         ▼                  ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Ingestion Layer                               │
├─────────────────────────────────────────────────────────────────┤
│  API Client  │  File Processor  │  Email Classifier  │  Doc OCR │
└────────┬─────────────────┬─────────────────┬───────────────────┘
         │                 │                 │
         ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Supabase (PostgreSQL)                         │
├─────────────────────────────────────────────────────────────────┤
│  products  │  inventory_events  │  forecasts  │  documents      │
│            │   (TimescaleDB)    │             │                 │
└────────┬─────────────────┬─────────────────┬───────────────────┘
         │                 │                 │
         ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Processing Layer                              │
├─────────────────────────────────────────────────────────────────┤
│  Metrics Engine  │  Prophet Forecasting  │  LangGraph Agents    │
└────────┬─────────────────┬─────────────────┬───────────────────┘
         │                 │                 │
         ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Presentation Layer                            │
├─────────────────────────────────────────────────────────────────┤
│  Redash Dashboard  │  Retool Mobile  │  Slack/Email Alerts      │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 Database Schema

```sql
-- Core entities
products (id, sku, name, category)
warehouses (id, name, code)
distributors (id, name, segment, state)

-- Time-series (hypertable)
inventory_events (time, sku_id, warehouse_id, distributor_id, event_type, quantity)

-- Forecasts
forecasts (id, sku_id, forecast_date, target_date, yhat, yhat_lower, yhat_upper)

-- Documents
documents (id, type, source_email_id, extracted_data, status, created_at)
```

---

## 6. Implementation Roadmap

### Phase 1: MVP (Weeks 1-8)
**Goal**: Core data pipeline + basic dashboards

| Week | Deliverable |
|------|-------------|
| 1-2 | Supabase setup, schema creation, WineDirect API integration |
| 3-4 | Distributor file processing, inventory metrics calculations |
| 5-6 | Redash dashboard deployment, threshold alerting |
| 7-8 | Testing, bug fixes, user acceptance |

**Exit Criteria**:
- All 4 SKUs visible in dashboard with DOH metrics
- Alerts firing for stock-out risks
- Daily data sync from WineDirect operational

### Phase 2: Automation (Weeks 9-16)
**Goal**: Email processing + document extraction + forecasting

| Week | Deliverable |
|------|-------------|
| 9-10 | Prophet forecasting implementation and validation |
| 11-12 | Email classification with Gmail API |
| 13-14 | Document OCR with Azure Document Intelligence |
| 15-16 | Integration testing, performance optimization |

**Exit Criteria**:
- 26-week forecasts generating with <12% MAPE
- Emails auto-classified and routed
- POs/BOLs extracted with >93% accuracy

### Phase 3: Intelligence (Weeks 17-24)
**Goal**: Full agentic capabilities + financial integration

| Week | Deliverable |
|------|-------------|
| 17-18 | LangGraph agent implementation |
| 19-20 | Retool mobile dashboard |
| 21-22 | QuickBooks integration |
| 23-24 | Production hardening, documentation |

**Exit Criteria**:
- Agents generating procurement recommendations
- Mobile dashboards operational
- Financial data syncing with QuickBooks

---

## 7. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| WineDirect API access delayed | Medium | High | Early contact with Jeff Carroll; file-based fallback |
| Prophet accuracy <12% MAPE | Medium | Medium | Ensemble with ARIMA; quarterly re-tuning |
| Distributor data format changes | Medium | Medium | Flexible parser; custom template support |
| User adoption resistance | Medium | Medium | Phased rollout; champion users; training |
| TimescaleDB deprecation (Postgres 17) | Medium | Low | Stay on Postgres 15; plan migration |

---

## 8. Cost Estimates

### Infrastructure (Monthly)
| Component | MVP | Production |
|-----------|-----|------------|
| Supabase Pro | $25 | $100 |
| Railway hosting | $50 | $200 |
| Azure Document AI | $50 | $100 |
| Email processing | $20 | $50 |
| Dashboard tools | $0 | $200 |
| Agent orchestration | $0 | $100 |
| **Total** | **$145** | **$750** |

### Annual Estimates
- MVP: ~$1,750/year
- Full Production: ~$9,000/year

---

## 9. Open Questions

1. **WineDirect Access**: Has contact been made with Jeff Carroll for API credentials?
2. **Historical Data**: How many years of historical data are available for forecasting?
3. **Distributor Formats**: Are sample files available from each distributor?
4. **Approval Thresholds**: What dollar amount triggers manager vs. executive approval?
5. **QuickBooks Setup**: Is QuickBooks Online currently in use, and what chart of accounts structure?

---

## 10. Appendix

### A. Metric Definitions

| Metric | Formula | Description |
|--------|---------|-------------|
| DOH_T30 | Inventory / (30-day depletion / 30) | Days of inventory at current depletion rate |
| DOH_T90 | Inventory / (90-day depletion / 90) | Days of inventory at 90-day average rate |
| A30_Ship:A30_Dep | 30-day shipments / 30-day depletions | Supply vs demand balance |
| A30:A90_Dep | (30-day dep rate) / (90-day dep rate) | Demand acceleration indicator |

### B. Distributor Segments

| Segment | Description |
|---------|-------------|
| Non-RNDC States | States with non-RNDC distribution |
| Georgia (RNDC) | RNDC Georgia division |
| Reyes 7 States | States covered by Reyes Beverage Group |
| Other RNDC States | RNDC divisions outside Georgia |

### C. Source Research
See `/research/une-femme-supply-chain-platform/synthesis.md` for complete technical research.
