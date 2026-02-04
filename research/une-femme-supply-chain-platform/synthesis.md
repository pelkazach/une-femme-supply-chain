# Research Synthesis: Une Femme Wine Supply Chain Intelligence Platform

## Metadata
---
title: Une Femme Supply Chain Platform Research Synthesis
created: 2026-02-03
status: Complete
source_count: 18
themes: [data-integration, agent-orchestration, document-processing, forecasting, dashboards, infrastructure]
---

## Executive Summary

This research synthesis provides comprehensive technical guidance for building Une Femme's supply chain intelligence platform. Based on analysis of 18 sources across wine industry systems, AI agent frameworks, document processing, forecasting methodologies, dashboard technologies, and infrastructure options, we can definitively answer the key research questions:

### Key Findings

1. **VIP/WineDirect Integration**: WineDirect offers REST APIs with 30/60/90-day depletion velocity reports. Access requires contacting Jeff Carroll (jeff.carroll@winedirect.com). Critical deadline: HTTPS-only migration by February 16, 2026.

2. **Distributor Data Integration**: Direct distributor APIs are limited. Pragmatic approach uses CSV/Excel file uploads (Tradeparency model) with RNDC, Southern Glazers, and Winebow. EDI integration (850/856/810) possible but complex (6-16 weeks, $15K-$200K).

3. **Dashboard Recommendation**: **Redash** for operational KPIs with threshold-based alerting + **Retool** for mobile warehouse dashboards with bidirectional operations.

4. **Agent Framework**: **LangGraph** for production supply chain workflows with state machine architecture, native human-in-the-loop support, and multi-agent orchestration.

5. **Database Architecture**: **Supabase** (PostgreSQL + real-time) at $25-100/month, with TimescaleDB for time-series inventory data and Row Level Security for multi-tenant isolation.

6. **Forecasting**: **Prophet** with multiplicative seasonality, targeting <12% MAPE on 26-week rolling forecasts. Handles champagne's 7.5x NYE demand spikes natively.

7. **Infrastructure Costs**: $300-900/year for MVP on Railway/Supabase. Full production system: $5,000-15,000/year including all components.

8. **Build Timeline**: MVP in 8-12 weeks; full system in 20-28 weeks.

---

## Theme 1: Data Ingestion Layer

### 1.1 VIP Commerce / WineDirect Integration

**Technical Approach**: WineDirect provides three API pathways: [[winedirect-api]]

1. **All-New WineDirect (ANWD) REST APIs** - Modern, wine-specific endpoints
   - Access: Contact Jeff Carroll, VP Partnerships (jeff.carroll@winedirect.com)
   - Authentication: Bearer Token via AccessToken endpoint
   - Key endpoints: Orders (GET/POST), Inventory (GET sellable, inventory-out tracking)

2. **Inventory Velocity Reports** - Critical for depletion forecasting
   - 30/60/90-day lookback windows
   - "Approximates the rate you will deplete your remaining inventory"
   - Directly aligned with Une Femme's DOH_T30, DOH_T90 metrics

3. **Data Lake** - Historical analysis
   - ANWD data: Hourly refresh
   - Classic data: Daily refresh
   - Supports batch analytics and BI integration

**Critical Deadline**: Non-HTTPS API calls will receive HTTP 302 redirects after **February 16, 2026**. All integrations must migrate to HTTPS.

**Implementation Effort**: 2-3 weeks initial integration; 4-6 weeks for full depletion forecasting.

### 1.2 Distributor Data Feeds (RNDC, Southern Glazers, Winebow)

**Key Finding**: Direct distributor API access is limited. The wine industry has converged on **file-based integration** as the pragmatic approach. [[andavi-tradeparency]] [[edi-wine-distribution]]

**Tradeparency Model** (Existing Solution):
- Accepts CSV/Excel files from RNDC, Southern Glazers, Winebow
- Automates billback and depletion allowance verification
- AI Invoice Manager pre-trained on major distributor formats
- Custom templates for additional distributors

**EDI Integration** (Alternative Path):
- Core documents: EDI 850 (PO), 856 (ASN), 810 (Invoice)
- Implementation: 6-8 weeks (managed services) to 12-16 weeks (in-house)
- Cost: $15K-$50K (managed) to $80K-$200K (in-house)
- Compliance requirements: 96-99% accuracy, 48-hour advance notification

**Recommendation**: Start with file-based integration (Tradeparency model or custom CSV processor). Consider EDI as Phase 2 for high-volume distributors.

### 1.3 Ekos/Enolytics Pattern

The Ekos-VIP integration demonstrates successful wine industry data integration: [[ekos-vip-integration]] [[enolytics-depletion]]

- **Daily batch synchronization** (not real-time)
- **Authorized data sharing** with explicit customer permission
- **Multi-dimensional metrics**: Product, distributor, packaging type
- **Key metrics available**:
  - On-hand inventory by distributor
  - Projected daily sales rate
  - Days on hand calculations
  - 90-day historical trends + YoY comparisons

**Implication**: Daily batch sync is industry-standard and sufficient for wine production planning cycles (weekly/monthly horizons).

### 1.4 Three-Tier Compliance Considerations

The three-tier system creates specific data sharing constraints: [[three-tier-compliance]]

- **Vertical integration prohibited**: Cannot assume direct system access across tiers
- **Platform must function as voluntary data aggregation layer**
- **State-by-state variations**: Control states vs. open states require different regulatory models
- **Equitable design required**: Features must not concentrate information advantage

---

## Theme 2: Document Processing & Email Automation

### 2.1 Document AI / OCR for POs, BOLs, Invoices

**Recommendation: Azure Document Intelligence** as primary platform [[ocr-document-ai]] [[bol-ocr]]

| Platform | Accuracy | Cost | Speed | Best For |
|----------|----------|------|-------|----------|
| Azure Document Intelligence | 93% field, 87% table | ~$0.01/page | Fast | Complex wine industry documents |
| AWS Textract | 78% | ~$0.01/page | Fast | AWS-native deployments |
| Google Document AI | 72% | ~$0.01/page | Fast | Google Cloud environments |
| GPT-4o | 98% | ~$0.01/page | 33s/page | High-value edge cases only |

**Bill of Lading Extraction**: Specialized BOL OCR vendors (Mindee, Nanonets, Veryfi) achieve 95%+ accuracy with 2-3 second processing:
- Key fields: Shipper, consignee, BOL number, tracking, cargo description, quantities
- Processing improvement: 47 minutes → 2 minutes per document
- ROI: 32% operational cost reduction, 20 hours/week labor savings

### 2.2 Email Classification & Routing

**Architecture Pattern**: LLM-based classification with distributed processing [[email-classification]]

```
Email Arrival → IMAP Polling → RabbitMQ Queue → Celery Workers
     → LLM Classification (Mixtral/Qwen) → Department Routing
     → Attachment Extraction → OCR Processing → Database Storage
```

**Performance Benchmarks**:
- 80% latency reduction (15 seconds for 10 emails vs. 3-5 minutes)
- 94-97% classification accuracy with LLM
- Local Ollama inference: ~50ms vs. 2-3 seconds for API calls

**Recommended Stack**:
- Gmail API or IMAP for email retrieval
- RabbitMQ + Celery for distributed processing
- Local Ollama (Qwen 4b or Mixtral 8x7b) for classification
- Human-in-the-loop for uncertain classifications (<85% confidence)

---

## Theme 3: Agentic Architecture

### 3.1 Agent Framework Selection

**Recommendation: LangGraph** for production supply chain workflows [[langgraph-agents]]

| Framework | Production Ready | HITL Support | State Management | Best For |
|-----------|-----------------|--------------|------------------|----------|
| **LangGraph** | Yes | Native | Excellent | Complex workflows with human oversight |
| CrewAI | Moderate | Limited | Basic | Prototyping, simple multi-agent |
| AutoGen | Limited | Manual | Basic | Research/experimentation |
| Native Claude | Yes | Manual | None | Simple single-agent tasks |

**Why LangGraph for Supply Chain**:
1. **State Machine Architecture**: Explicit control flow matches supply chain processes (request → approval → execution → tracking)
2. **Human-in-the-Loop**: Native interrupt/approve/resume without custom implementation
3. **Multi-Agent Orchestration**: Orchestrator-worker pattern for specialized agents
4. **Production Resilience**: Fault tolerance, persistence, horizontal scaling

### 3.2 Recommended Agent Architecture

```
graph:
  nodes:
    - demand_forecast: Prophet-based demand forecasting
    - inventory_check: Inventory optimization agent
    - vendor_evaluation: Vendor analysis and selection
    - orchestrator: Coordinates agents, produces recommendations
    - approval_gate: Routes to appropriate approver
    - order_execution: Creates purchase orders
    - fulfillment_tracking: Monitors shipment and receipt

  human_touchpoints:
    - approval_gate: High-value orders require human approval
    - fulfillment_tracking: Human confirms receipt, flags issues
    - rewind: Human can rewind to earlier state with instructions
```

### 3.3 Human-in-the-Loop Patterns

**Five Critical Patterns** for procurement automation: [[hitl-patterns]]

1. **Confidence-Based Routing**: Auto-approve >85% confidence; route 60-85% to human review
2. **Approval Gates**: High-risk functions require explicit human approval
3. **Multi-Stage Approval**: Automated filter → confidence triage → human review → escalation
4. **Policy-Driven Approvals**: Authorization engines (Permit.io) for dynamic thresholds
5. **SLA-Enforced Escalation**: Defined response windows prevent bottlenecks

**Supply Chain Application**:
- Auto-approve routine replenishment from verified suppliers
- Route new suppliers, price deviations, policy exceptions to human reviewers
- Confidence-scored risk assessments inform approval decisions

### 3.4 Agent Memory Architecture

**Multi-Layer Memory Required**: [[agent-memory]]

| Memory Type | Purpose | Implementation |
|-------------|---------|----------------|
| Short-term | Current conversation/task context | LangGraph state object |
| Semantic | Product/supplier knowledge | Vector database (pgvector) |
| Episodic | Historical orders/patterns | PostgreSQL + TimescaleDB |
| Relational | Supplier networks, compliance chains | Neo4j (Phase 2) |

**Recommendation**: Start with semantic (MongoDB Atlas or pgvector) + episodic (PostgreSQL). Add graph-based memory in Phase 2 for complex supplier relationship reasoning.

---

## Theme 4: Financial Forecasting & Integration

### 4.1 26-Week Rolling Forecast with Prophet

**Prophet is strategically aligned** for champagne demand forecasting: [[prophet-forecasting]]

**Why Prophet**:
- Native handling of 7.5x NYE demand spikes (648% increase on Dec 31)
- Multiple seasonality (yearly, weekly, custom holidays)
- Explicit holiday effects with uncertainty quantification
- Interpretable decomposition for business stakeholders

**Implementation Specifications**:
```python
Prophet Configuration:
- growth='linear'
- seasonality_mode='multiplicative'  # Critical for champagne
- changepoint_prior_scale=0.05       # Recommended starting point
- yearly_seasonality=True
- weekly_seasonality=True

Holiday Calendar:
- NYE: Dec 24-31 (lower_window=-7)
- Valentine's Day: Feb 7-14
- Mother's Day: May 1-14
- Thanksgiving: Nov 20-27
```

**Target Accuracy**: MAPE <10% on 4-week forecasts; <12% on 26-week horizon

**Safety Stock Formula**:
```
Safety Stock = (yhat_upper_95 - yhat) × Service Factor

Example (NYE 2025):
- Point forecast: 70,000 units
- 95th percentile: 85,000 units
- Safety stock: 15,000 units
- Total order: 85,000 units
- Cost: $180K working capital for 95% service level
```

### 4.2 QuickBooks Integration

**Technical Approach**: [[quickbooks-api]]

- **Library**: python-quickbooks (PyPI)
- **Authentication**: OAuth 2.0 with intuit-oauth
- **Rate Limits**: 500 requests/minute, 10 concurrent
- **Batch Operations**: 12.5x improvement (40 req/min effective)

**Key Endpoints**:
- Inventory sync via Change Data Capture (CDC)
- Invoice/payment tracking
- Revenue recognition integration

**2025 Pricing Impact**: Intuit's new model offers unlimited free data creation/update but usage-based pricing for retrieval. Optimize for write-heavy patterns.

---

## Theme 5: Dashboard & Visualization

### 5.1 Dashboard Technology Recommendation

**Multi-Tool Strategy**: [[dashboard-comparison]]

| Use Case | Recommended Tool | Rationale |
|----------|-----------------|-----------|
| **Operational KPIs** | Redash | Superior threshold-based alerting |
| **Mobile Warehouse** | Retool | Native mobile + bidirectional operations |
| **Self-Service Exploration** | Metabase | Non-technical user friendly |
| **Advanced Analytics** | Superset | Geospatial, LDAP integration |

### 5.2 Redash for Operational Monitoring

**Why Redash for Supply Chain KPIs**:
- Custom threshold alerts: "Alert when stock < X AND lead time > Y days"
- Webhook integration for automated notifications
- Superior performance on large datasets
- Elasticsearch integration for event-based updates

**Alerting Example**:
```sql
-- Alert: Low Pinot Noir with long lead time
SELECT sku, current_stock, lead_time_days
FROM inventory
WHERE sku LIKE 'UFRed%'
  AND current_stock < 500
  AND lead_time_days > 7
```

### 5.3 Retool for Mobile Operations

**Unique Capabilities**:
- Full mobile app support (all tiers)
- Bidirectional data flow (read AND write)
- Workflow automation on alert conditions
- Sub-second refresh via WebSockets

**Wine Supply Chain Example**: Warehouse staff views inventory → identifies stock-out risk → clicks "Create PO" → system writes to purchase order system AND triggers supplier notification—all from mobile dashboard.

### 5.4 Real-Time Refresh Limitation

**Critical Finding**: All open-source tools (Metabase, Superset, Redash) limited to **1-minute minimum** refresh intervals. For sub-minute latency:
- Use Retool WebSockets
- Implement streaming architecture (Kafka/Kinesis)
- Supabase real-time subscriptions

---

## Theme 6: Data Architecture

### 6.1 Database Recommendation: Supabase + TimescaleDB

**Why Supabase**: [[supabase-platform]] [[timescaledb-schema]]

- PostgreSQL foundation with ACID compliance
- Real-time subscriptions via WebSocket (150K+ msgs/sec)
- Row Level Security for multi-tenant isolation
- Edge Functions for serverless integrations
- $25/month Pro plan + compute upgrades

**TimescaleDB for Time-Series**:
```sql
-- Hypertable for inventory events
CREATE TABLE inventory_events (
  time TIMESTAMPTZ NOT NULL,
  sku_id UUID NOT NULL,
  warehouse_id UUID NOT NULL,
  quantity_change INTEGER,
  event_type TEXT
);

SELECT create_hypertable('inventory_events', 'time');

-- Continuous aggregate for DOH metrics
CREATE MATERIALIZED VIEW daily_doh AS
SELECT time_bucket('1 day', time) AS day,
       sku_id,
       SUM(quantity_change) as net_change
FROM inventory_events
GROUP BY 1, 2
WITH (timescaledb.continuous);
```

**Scalability Considerations**:
- Database-triggered Realtime effective to ~50K concurrent users
- Single-writer PostgreSQL architecture
- TimescaleDB deprecated in PostgreSQL 17 (stay on Postgres 15)

### 6.2 Schema Design for Une Femme Metrics

**Core Metrics Compatibility**:

| Une Femme Metric | Database Implementation |
|------------------|------------------------|
| DOH_T30 | Continuous aggregate: 30-day rolling depletion |
| DOH_T90 | Continuous aggregate: 90-day rolling depletion |
| A30_Ship:A30_Dep | Ratio query on shipment/depletion aggregates |
| Inventory at WSC | Real-time inventory table with RLS |
| DUP | Production schedule table with lead time calculations |
| Seasonal Index | Historical monthly averages with Prophet integration |

---

## Theme 7: Infrastructure & Deployment

### 7.1 Hosting Recommendation: Railway

**Railway Pricing**: [[railway-hosting]]

| Scenario | Monthly Cost | Notes |
|----------|-------------|-------|
| MVP | $16-25 | Pro plan, minimal compute |
| Small Production | $100-150 | Medium compute, 50GB database |
| Full System | $300-500 | Large compute, multiple services |

**Cost Comparison**:
- Railway: $300/month for production
- AWS equivalent: $500-700/month
- Heroku equivalent: $600-800/month

**Critical Gap**: Railway does not provide automated PostgreSQL backups. Implement pg_dump automation or use Supabase managed backups.

### 7.2 Total Infrastructure Cost Estimates

**MVP (4 core SKUs, 1 distributor)**:
- Supabase Pro: $25/month
- Railway hosting: $50/month
- Document AI: $50/month (5,000 documents)
- Email processing: $20/month
- **Total: $145/month (~$1,750/year)**

**Production (Full feature set)**:
- Supabase + compute: $100/month
- Railway hosting: $200/month
- Document AI: $100/month
- Email processing: $50/month
- Dashboard tools: $200/month
- Agent orchestration: $100/month
- **Total: $750/month (~$9,000/year)**

---

## Decision Matrices

### Dashboard Technology Comparison

| Feature | Redash | Retool | Metabase | Superset |
|---------|--------|--------|----------|----------|
| Setup Speed | 20-30 min | 15 min | 5-15 min | 15-30 min |
| Real-time Refresh | 1 min | Sub-second | 1 min | 1 min |
| Alerting | **Superior** | Strong | Basic | Basic |
| Mobile | Responsive | **Native** | Responsive | Responsive |
| Bidirectional | No | **Yes** | No | No |
| Monthly Cost | $200-400 | $300-500 | $0-200 | $200-500 |

### Agent Framework Comparison

| Feature | LangGraph | CrewAI | AutoGen | Native Claude |
|---------|-----------|--------|---------|---------------|
| Production Readiness | **Excellent** | Good | Limited | Good |
| Human-in-Loop | **Native** | Manual | Manual | Manual |
| State Management | **Excellent** | Basic | Basic | None |
| Multi-Agent | **Orchestrator-Worker** | Role-based | Emergent | N/A |
| Learning Curve | Moderate | Easy | Moderate | Easy |

### Database Options Comparison

| Feature | Supabase | Railway PostgreSQL | Neon | PlanetScale |
|---------|----------|-------------------|------|-------------|
| Real-time | **Native** | Manual | Limited | No |
| Time-series | TimescaleDB | TimescaleDB | Limited | No |
| Row-Level Security | **Native** | Manual | Manual | No |
| Monthly Cost | $25-100 | $50-150 | $29-99 | $29-99 |
| Edge Functions | **Yes** | No | No | No |

---

## Implementation Recommendations

### Phase 1: MVP (Weeks 1-8)
**Goal**: Core data pipeline + basic dashboards

1. **Week 1-2**: WineDirect API integration
   - Contact Jeff Carroll for ANWD access
   - Implement Bearer Token authentication
   - Pull initial inventory and velocity data

2. **Week 3-4**: Database setup
   - Deploy Supabase with TimescaleDB
   - Create inventory_events hypertable
   - Configure continuous aggregates for DOH metrics

3. **Week 5-6**: Dashboard deployment
   - Deploy Redash for operational KPIs
   - Configure threshold alerts for stock-outs
   - Connect to Supabase PostgreSQL

4. **Week 7-8**: Basic forecasting
   - Implement Prophet model for top 4 SKUs
   - Configure 26-week rolling forecast
   - Validate against historical data

### Phase 2: Automation (Weeks 9-16)
**Goal**: Email processing + document extraction

1. **Week 9-10**: Email classification
   - Gmail API integration
   - LLM-based classification (Ollama/Mixtral)
   - Routing for POs, BOLs, invoices

2. **Week 11-12**: Document extraction
   - Azure Document Intelligence integration
   - PO and BOL field extraction
   - Validation and error handling

3. **Week 13-14**: Agent implementation
   - LangGraph workflow for procurement
   - Human-in-the-loop approval gates
   - Basic demand/inventory agents

4. **Week 15-16**: Integration testing
   - End-to-end workflow testing
   - Performance optimization
   - User acceptance testing

### Phase 3: Intelligence (Weeks 17-24)
**Goal**: Full agentic capabilities + advanced analytics

1. **Week 17-18**: Multi-agent orchestration
   - Demand forecaster agent
   - Inventory optimizer agent
   - Vendor analyzer agent
   - Orchestrator coordination

2. **Week 19-20**: Mobile deployment
   - Retool warehouse dashboards
   - Bidirectional inventory operations
   - Mobile-first workflows

3. **Week 21-22**: Financial integration
   - QuickBooks API connection
   - Revenue recognition sync
   - Cash flow forecasting

4. **Week 23-24**: Optimization
   - Prophet ensemble if MAPE >12%
   - Advanced alerting rules
   - Production hardening

---

## Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| WineDirect API access delays | Medium | High | Early contact with Jeff Carroll; parallel file-based approach |
| TimescaleDB deprecation in Postgres 17 | Medium | Medium | Stay on Postgres 15; plan migration path |
| Supabase real-time scaling limits | Low | Medium | Implement public table strategy at 40K users |
| Prophet forecast accuracy <12% MAPE | Medium | Medium | Ensemble with ARIMA; quarterly re-tuning |

### Business Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Distributor data access restrictions | Medium | High | Tradeparency partnership; file-based fallback |
| Three-tier compliance violations | Low | High | Legal review; equitable feature design |
| User adoption resistance | Medium | Medium | Phased rollout; champion users; training |

---

## Success Criteria Answers

Based on this research, we can definitively answer the eight success criteria:

1. **VIP Depletion Data**: Contact Jeff Carroll (jeff.carroll@winedirect.com) for ANWD REST API access. Use Inventory Velocity reports for 30/60/90-day depletion. HTTPS required by Feb 16, 2026.

2. **Database Schema**: Supabase PostgreSQL with TimescaleDB hypertables for inventory events. Continuous aggregates for DOH metrics. Row-Level Security for multi-tenant access.

3. **Dashboard Stack**: Redash for operational KPIs with threshold alerting + Retool for mobile warehouse operations.

4. **Email Processing**: Gmail API → RabbitMQ/Celery → Ollama LLM classification → Azure Document AI extraction.

5. **Agent Framework**: LangGraph for state machine workflows with native human-in-the-loop, multi-agent orchestration via orchestrator-worker pattern.

6. **Financial Integration**: QuickBooks API via python-quickbooks with OAuth 2.0. CDC for inventory sync. Write-heavy optimization for new pricing model.

7. **Infrastructure Costs**: MVP ~$1,750/year; Full production ~$9,000/year (Supabase + Railway + Document AI + Dashboard tools).

8. **Build Timeline**: MVP in 8 weeks; Full system in 24 weeks (6 months).

---

## Sources

### Wine Industry Systems
- [[winedirect-api]] - WineDirect API documentation and integration patterns
- [[ekos-vip-integration]] - Ekos-VIP partnership and data synchronization
- [[enolytics-depletion]] - Enolytics depletion analytics platform
- [[andavi-tradeparency]] - Tradeparency distributor automation
- [[edi-wine-distribution]] - EDI protocols for wine distribution
- [[three-tier-compliance]] - Three-tier regulatory requirements

### Document Processing
- [[ocr-document-ai]] - Document AI/OCR comparison (Azure, AWS, Google, GPT-4o)
- [[email-classification]] - Email classification and routing architecture
- [[bol-ocr]] - Bill of Lading OCR extraction

### Agentic Systems
- [[langgraph-agents]] - LangGraph production agent orchestration
- [[hitl-patterns]] - Human-in-the-loop approval patterns
- [[agent-memory]] - AI agent memory architecture

### Data & Infrastructure
- [[supabase-platform]] - Supabase real-time PostgreSQL platform
- [[timescaledb-schema]] - TimescaleDB schema design patterns
- [[railway-hosting]] - Railway deployment and pricing
- [[dashboard-comparison]] - Dashboard tools comparison
- [[prophet-forecasting]] - Prophet time-series forecasting
- [[quickbooks-api]] - QuickBooks Online API integration
