# Research Plan: Une Femme Wine Supply Chain Intelligence & Automation Platform

## Metadata
- **Created**: 2026-02-03
- **Status**: Active
- **Depth**: Deep (15+ sources)
- **Approach**: Parallel research execution

---

## Research Overview

### Objective
Conduct comprehensive research to inform a PRD for building a supply chain intelligence platform for Une Femme wines. The platform will replace/augment existing Excel workbooks and weekly PDF reports with a real-time, automated system featuring agentic forecasting capabilities.

### Context
- **Brand**: Une Femme (champagne/wine)
- **Core SKUs**: UFBub250, UFRos250, UFRed250, UFCha250
- **Current State**: Master Sales and Supply Excel workbook + weekly PDF reports
- **Target State**: Real-time automated platform with AI agents

### Success Criteria
1. Define exact technical approach for pulling VIP depletion data
2. Recommend database schema for metrics and time-series analysis
3. Select and justify dashboard technology stack
4. Design email monitoring, parsing, and processing architecture
5. Select agent framework for autonomous workflows
6. Map financial system integration path
7. Estimate total infrastructure costs at scale
8. Provide realistic MVP vs. full system timeline guidance

---

## Research Angles

### Angle 1: Wine Industry Systems & Data Integration
**Core Questions:**
- How do wineries technically integrate with VIP Commerce/WineDirect for depletion data?
- What are the standard EDI protocols and data formats for wine distributor integration?
- What existing middleware/platforms bridge wine producers to distributors?

**Target Sources**: 3-4 (API docs, integration platforms, practitioner experiences)

### Angle 2: Document Processing & Email Automation
**Core Questions:**
- What is the optimal architecture for parsing POs, BOLs, and invoices from email?
- How do Document AI services compare for wine industry documents?
- What email integration patterns support compliance and audit requirements?

**Target Sources**: 2-3 (technical documentation, implementation case studies)

### Angle 3: Agentic Architecture & AI Frameworks
**Core Questions:**
- Which agent framework best supports supply chain automation workflows?
- What human-in-the-loop patterns work for procurement approval flows?
- How should agent memory and context be architected for supply chain decisions?

**Target Sources**: 3-4 (framework comparisons, enterprise implementations)

### Angle 4: Financial Forecasting & Integration
**Core Questions:**
- What time-series forecasting approaches work best for beverage seasonality?
- How do wine brands typically integrate with accounting systems (QBO, Xero)?
- What are standard DSO patterns and cash flow models for wine distributors?

**Target Sources**: 2-3 (financial integration docs, forecasting methodologies)

### Angle 5: Dashboard & Visualization Technology
**Core Questions:**
- Which dashboard stack best balances rapid development with production scalability?
- What alerting architectures prevent alert fatigue while catching anomalies?
- How should real-time KPIs be surfaced for supply chain operations?

**Target Sources**: 2-3 (platform comparisons, implementation guides)

### Angle 6: Database & Data Architecture
**Core Questions:**
- What schema design supports time-series inventory data with historical analysis?
- How should event sourcing be implemented for supply chain transactions?
- What data pipeline patterns handle both real-time and batch processing?

**Target Sources**: 2-3 (architecture guides, database comparisons)

### Angle 7: Wine Industry Software Landscape
**Core Questions:**
- What capabilities do existing wine industry platforms (VinSuite, InnoVint, GreatVines) offer?
- Where are the gaps that justify custom development vs. SaaS adoption?
- What is the realistic build vs. buy calculus for each component?

**Target Sources**: 2-3 (vendor documentation, industry analyses)

---

## Source Strategy

### Source Type Distribution
| Source Type | Target Count | Focus Areas |
|-------------|--------------|-------------|
| Technical Documentation/APIs | 5-6 | VIP, WineDirect, QBO, Email APIs, Agent Frameworks |
| Practitioner Insights | 4-5 | Reddit, HackerNews, LinkedIn on wine tech, supply chain automation |
| Industry Reports | 2-3 | Wine DTC reports, three-tier distribution analysis |
| Case Studies | 2-3 | Wine brand implementations, supply chain AI projects |
| Vendor Comparisons | 2-3 | Dashboard tools, database options, agent frameworks |

### Total Target: 16-18 sources

---

## Search Queries by Angle

### Angle 1: Wine Industry Systems (4 queries)
1. "WineDirect API documentation REST endpoints authentication"
2. "VIP Commerce wine depletion data integration Ekos Enolytics"
3. "Wine distributor EDI 850 856 810 supplier integration RNDC"
4. "Andavi Tradeparency wine distributor data automation"

### Angle 2: Document Processing (3 queries)
1. "Purchase order email parsing automation Document AI OCR comparison 2025"
2. "Bill of lading OCR extraction freight document processing"
3. "Gmail API email monitoring classification ML pipeline"

### Angle 3: Agentic Architecture (4 queries)
1. "LangGraph supply chain automation agent workflow production"
2. "CrewAI enterprise implementation procurement automation"
3. "Human-in-the-loop AI agent approval workflow patterns"
4. "AI agent memory vector database supply chain context"

### Angle 4: Financial Integration (3 queries)
1. "QuickBooks Online API inventory sync revenue recognition"
2. "Prophet time series forecasting beverage CPG seasonality"
3. "Wine distributor payment terms DSO accounts receivable"

### Angle 5: Dashboard Technology (2 queries)
1. "Retool vs Metabase vs Superset real-time dashboard comparison 2025"
2. "Supply chain KPI dashboard alerting architecture"

### Angle 6: Data Architecture (2 queries)
1. "TimescaleDB PostgreSQL inventory time series schema design"
2. "Event sourcing supply chain transactions CDC patterns"

### Angle 7: Wine Industry Software (2 queries)
1. "VinSuite InnoVint GreatVines wine software comparison"
2. "Wine brand supply chain software build vs buy analysis"

---

## Analysis Approach

### Synthesis Method: Thematic
Findings will be organized by functional capability rather than by source, enabling clear comparison of approaches for each system component.

### Theme Structure
1. **Data Ingestion Layer**: VIP integration, distributor data feeds, email processing
2. **Processing & Intelligence Layer**: Document AI, forecasting, agent orchestration
3. **Integration Layer**: Financial systems, accounting, procurement
4. **Presentation Layer**: Dashboards, alerts, reporting
5. **Infrastructure Layer**: Database, hosting, security

---

## Expected Deliverables

1. **synthesis.md**: Comprehensive thematic analysis with citations
2. **summaries/**: 16-18 individual source analysis files
3. **Appendices within synthesis**:
   - API endpoint reference tables
   - Database schema recommendations
   - Technology decision matrices
   - Cost estimation tables
   - Implementation timeline recommendations

---

## Potential Challenges

1. **VIP API Documentation**: May require reaching out to WineDirect directly; public docs may be limited
2. **Distributor EDI Specs**: Proprietary systems; may need to rely on middleware vendor documentation
3. **Pricing Information**: SaaS tool pricing often requires demo/contact
4. **Wine Industry Specifics**: Limited public case studies from wine brands on tech implementations

---

## Research Execution Plan

### Phase 1: URL Discovery & Validation
- Execute all 20 search queries
- Identify and validate specific URLs for each query
- Ensure coverage across all source types

### Phase 2: Parallel Source Research
- Spawn 16-18 researcher subagents simultaneously
- Each researcher fetches, analyzes, and summarizes one source
- Summaries saved to `summaries/` directory

### Phase 3: Synthesis
- Review all source summaries
- Identify cross-cutting themes and patterns
- Build comprehensive synthesis document
- Generate decision matrices and recommendations

---

## Metrics Compatibility

The research must account for maintaining these existing Une Femme analytical frameworks:

**SKU-Level Metrics:**
- DOH_T30, DOH_T90 (Days on Hand calculations)
- A30_Ship:A30_Dep, A90_Ship:A90_Dep (Shipment to Depletion ratios)
- A30:A90_Ship, A30:A90_Dep (Velocity trend ratios)

**Inventory Positions:**
- WSC inventory (pallets/cases)
- Available inventory, Pending shipments

**Production Planning:**
- DUP (Days Until Production)
- Seasonal indices
- YoY growth targets

**Distributor Segmentation:**
- Non-RNDC States, Georgia RNDC, Reyes 7 States, Other RNDC States
