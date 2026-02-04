# Implementation Plan

## Status
- Total tasks: 42
- Completed: 31
- In progress: 0

## Phase 1: Foundation (P0 - MVP)

### Priority 1.1: Project Setup
- [x] **Task 1.1.1**: Initialize Python project with pyproject.toml and dependencies
  - Spec: N/A (standard setup)
  - Acceptance: `poetry install` succeeds, project structure created
  - Completed: 2026-02-03

- [x] **Task 1.1.2**: Create Railway project and add PostgreSQL database
  - Spec: specs/01-database-schema.md
  - Acceptance: Railway project exists with PostgreSQL service running
  - Completed: 2026-02-03
  - Notes: Project "une-femme-supply-chain" created at https://railway.com/project/e7663c26-3180-405c-9574-c9945ea9f643

- [x] **Task 1.1.3**: Configure Alembic for database migrations
  - Spec: specs/01-database-schema.md
  - Acceptance: `alembic init` complete, config connected to Railway database
  - Completed: 2026-02-03
  - Notes: Async template used, env.py loads DATABASE_URL from settings, greenlet added for SQLAlchemy async support

### Priority 1.2: Database Schema
- [x] **Task 1.2.1**: Create SQLAlchemy models for products, warehouses, distributors
  - Spec: specs/01-database-schema.md
  - Acceptance: Models defined with proper relationships and constraints
  - Completed: 2026-02-03
  - Notes: Created Product, Warehouse, and Distributor models with UUID primary keys, proper constraints (unique SKU/code), indexes, and nullable fields per spec

- [x] **Task 1.2.2**: Create inventory_events table with BRIN index
  - Spec: specs/01-database-schema.md
  - Acceptance: Table created with BRIN index on time column for efficient range queries
  - Completed: 2026-02-03
  - Notes: Created InventoryEvent SQLAlchemy model with BRIN index on time column, composite indexes on (sku_id, time) and (warehouse_id, time), and proper foreign key relationships with CASCADE/SET NULL delete behavior. Alembic migration creates all tables (products, warehouses, distributors, inventory_events) with proper indexes.

- [x] **Task 1.2.3**: Write migration to seed 4 product SKUs
  - Spec: specs/01-database-schema.md
  - Acceptance: UFBub250, UFRos250, UFRed250, UFCha250 exist in products table
  - Completed: 2026-02-03
  - Notes: Created Alembic migration (52fa8d4129df) that seeds 4 product SKUs with INSERT ... ON CONFLICT DO NOTHING for idempotency. Products: UFBub250 (sparkling), UFRos250 (rose), UFRed250 (red), UFCha250 (white).

- [x] **Task 1.2.4**: Create materialized views for DOH_T30 and DOH_T90
  - Spec: specs/04-inventory-metrics.md
  - Acceptance: Materialized views created, can be refreshed on schedule, query returns expected values
  - Completed: 2026-02-03
  - Notes: Created two materialized views in Alembic migration (e00126dfbb34): mv_daily_metrics (daily aggregates of shipments/depletions by SKU/warehouse) and mv_doh_metrics (DOH_T30, DOH_T90, shipment:depletion ratios, velocity trends). Uses standard PostgreSQL materialized views since TimescaleDB is not available. Added refresh_doh_metrics() function for scheduled refreshes. Views created WITH NO DATA for initial performance.

### Priority 1.3: WineDirect Integration
- [x] **Task 1.3.1**: Create WineDirect API client with Bearer Token auth
  - Spec: specs/02-winedirect-integration.md
  - Acceptance: Client authenticates successfully, token stored securely
  - Completed: 2026-02-03
  - Notes: Created async WineDirectClient in src/services/winedirect.py with Bearer Token authentication via OAuth client credentials grant. Features include automatic token refresh (with 60s buffer before expiry), 401 retry handling, and async context manager pattern. Includes get_sellable_inventory(), get_inventory_out(), and get_velocity_report() methods. 19 tests covering auth, API calls, token refresh, and error handling.

- [x] **Task 1.3.2**: Implement GET /inventory/sellable endpoint
  - Spec: specs/02-winedirect-integration.md
  - Acceptance: Returns inventory positions for all 4 SKUs
  - Completed: 2026-02-03
  - Notes: Created FastAPI endpoint GET /inventory/sellable that fetches inventory from WineDirect API and filters to tracked SKUs. Also added GET /inventory/sellable/{sku} for single SKU lookup. Created src/main.py FastAPI application entry point. 11 tests covering success, auth errors, API errors, and alternative field names.

- [x] **Task 1.3.3**: Implement GET /inventory-out endpoint for depletions
  - Spec: specs/02-winedirect-integration.md
  - Acceptance: Returns depletion events with timestamps
  - Completed: 2026-02-03
  - Notes: Created GET /inventory/out endpoint that fetches depletion events from WineDirect API. Features include: date range filtering via start_date/end_date query params (defaults to last 24 hours), filtering to tracked SKUs only, handling of multiple timestamp field formats (timestamp, date, event_date, transaction_date) and SKU field names (sku, item_code, product_code). Response includes DepletionEvent schema with sku, quantity, timestamp, order_id, customer, and warehouse. 8 new tests covering success, date range, auth errors, API errors, empty results, alternative field names, datetime objects, and Z-suffix timestamps.

- [x] **Task 1.3.4**: Implement velocity report parsing (30/60/90 day)
  - Spec: specs/02-winedirect-integration.md
  - Acceptance: Depletion rates extracted correctly
  - Completed: 2026-02-03
  - Notes: Created parse_velocity_report() function that extracts depletion rates (units_per_day) from WineDirect velocity reports for 30/60/90 day periods. Handles multiple response formats (skus/data/items keys, direct list), alternative field names (velocity, rate, depletion_rate), and calculates missing rate/total from available data. Added GET /inventory/velocity endpoint returning VelocityResponse with SkuVelocity list, and GET /inventory/velocity/{sku} for single SKU lookup. VelocityPeriod IntEnum used for type-safe period validation. 20 new tests covering parsing and endpoints.

- [x] **Task 1.3.5**: Create daily sync job with Celery
  - Spec: specs/02-winedirect-integration.md
  - Acceptance: Job runs daily, inserts data into inventory_events
  - Completed: 2026-02-03
  - Notes: Created Celery app (src/celery_app.py) with Redis broker and beat schedule for daily sync at 6 AM UTC. Implemented sync_winedirect_inventory task (src/tasks/winedirect_sync.py) that: 1) Fetches sellable inventory positions and creates snapshot events, 2) Fetches depletion events from last 24 hours and creates depletion events. Task has automatic retry (3 retries, 5 min delay) on API errors. Creates/uses WINEDIRECT warehouse. 17 tests covering sync functions, helper functions, and Celery task execution.

### Priority 1.4: Distributor File Processing
- [x] **Task 1.4.1**: Create file upload API endpoint
  - Spec: specs/03-distributor-data-processing.md
  - Acceptance: POST /upload accepts multipart/form-data CSV and Excel
  - Completed: 2026-02-03
  - Notes: Created POST /upload endpoint in src/api/upload.py accepting multipart/form-data with CSV and Excel files (.csv, .xlsx, .xls). Features include: file extension validation, content type validation, file size limit (10MB), empty file detection, optional distributor parameter (RNDC, Southern Glazers, Winebow). Returns ProcessingResult with filename, distributor, success/error counts, and validation errors. Actual file parsing will be implemented in tasks 1.4.2-1.4.5. 28 tests covering validation functions and endpoint behavior.

- [x] **Task 1.4.2**: Implement RNDC report parser
  - Spec: specs/03-distributor-data-processing.md
  - Acceptance: Parses Date, Invoice, Account, SKU, Qty Sold fields
  - Completed: 2026-02-03
  - Notes: Created src/services/distributor.py with parse_rndc_report() function supporting both CSV and Excel formats. Features include: flexible column name matching (date, ship_date, etc.), multiple date format support (YYYY-MM-DD, MM/DD/YYYY, etc.), optional field parsing (Invoice, Account, Description, Unit Price, Extended), quantity parsing with comma separators. Added openpyxl dependency for Excel support. Integrated parser with POST /upload endpoint (distributor="RNDC"). 56 tests covering parsing functions, CSV, Excel, and edge cases (empty files, missing columns, invalid data).

- [x] **Task 1.4.3**: Implement Southern Glazers report parser
  - Spec: specs/03-distributor-data-processing.md
  - Acceptance: Parses Ship Date, Customer, Item Code, Cases, Bottles fields
  - Completed: 2026-02-03
  - Notes: Created parse_southern_glazers_csv() and parse_southern_glazers_excel() functions in src/services/distributor.py. Supports flexible column name matching (Ship Date/date, Item Code/product_code, Bottles/units/qty/quantity). ParsedRow extended with cases and bottles fields. Integrated with POST /upload endpoint (distributor="Southern Glazers"). 24 new tests covering CSV, Excel, edge cases (empty files, missing columns, invalid data).

- [x] **Task 1.4.4**: Implement Winebow report parser
  - Spec: specs/03-distributor-data-processing.md
  - Acceptance: Parses transaction_date, product_code, quantity fields
  - Completed: 2026-02-03
  - Notes: Created parse_winebow_csv() and parse_winebow_excel() functions in src/services/distributor.py. Supports flexible column name matching (transaction_date/date/ship_date, product_code/sku/item_code, quantity/qty/units). Integrated with POST /upload endpoint (distributor="Winebow"). 26 new tests covering CSV, Excel, edge cases (empty files, missing columns, invalid data).

- [x] **Task 1.4.5**: Create SKU validation and error reporting
  - Spec: specs/03-distributor-data-processing.md
  - Acceptance: Invalid SKUs flagged with error message, valid rows processed
  - Completed: 2026-02-03
  - Notes: Created validate_skus() and validate_and_filter_parse_result() functions in src/services/distributor.py. VALID_SKUS constant contains 4 Une Femme SKUs (UFBub250, UFRos250, UFRed250, UFCha250). Invalid SKUs flagged with specific error messages including the unknown SKU and list of valid SKUs. Upload endpoint updated with validate_skus parameter (default True). 18 new tests covering validation functions and API endpoint behavior.

### Priority 1.5: Inventory Metrics
- [x] **Task 1.5.1**: Implement DOH_T30 calculation function
  - Spec: specs/04-inventory-metrics.md
  - Acceptance: Matches Excel formula within 1% variance
  - Completed: 2026-02-03
  - Notes: Created src/services/metrics.py with calculate_doh_t30() pure function. Formula: DOH_T30 = current_inventory / (depletion_30d / 30). Returns None for zero depletion (cannot calculate DOH with no sales). Added supporting functions: get_current_inventory() (handles snapshot + delta calculation), get_depletion_total() (sums depletions with optional warehouse/distributor filters), calculate_doh_t30_for_sku() (full SKU metrics), calculate_doh_t30_all_skus() (all 4 SKUs). DOHMetrics frozen dataclass stores results. 30 tests covering all acceptance criteria including 1% variance verification.

- [x] **Task 1.5.2**: Implement DOH_T90 calculation function
  - Spec: specs/04-inventory-metrics.md
  - Acceptance: Matches Excel formula within 1% variance
  - Completed: 2026-02-03
  - Notes: Created calculate_doh_t90() pure function with same pattern as calculate_doh_t30(). Formula: DOH_T90 = current_inventory / (depletion_90d / 90). Returns None for zero depletion. Extended DOHMetrics dataclass to include doh_t90, depletion_90d, and daily_rate_90d fields. Updated calculate_doh_t30_for_sku() to calculate both T30 and T90 metrics. Added calculate_doh_t90_for_sku() and calculate_doh_t90_all_skus() as semantic aliases. 14 new tests covering T90 calculation, 1% variance verification, and comparison with T30 for seasonal smoothing.

- [x] **Task 1.5.3**: Implement A30_Ship:A30_Dep ratio calculation
  - Spec: specs/04-inventory-metrics.md
  - Acceptance: Ratio calculated correctly for 30-day window
  - Completed: 2026-02-03
  - Notes: Created calculate_ship_dep_ratio() pure function and ShipDepRatioMetrics dataclass. Formula: A_Ship:A_Dep = shipments / depletions. Returns None for zero depletions (cannot calculate). Added get_shipment_total() helper (mirrors get_depletion_total). Created calculate_ship_dep_ratio_for_sku() and calculate_ship_dep_ratio_all_skus() async functions with warehouse_id and distributor_id filter support. Also calculates A90_Ship:A90_Dep ratio. 23 new tests covering pure function, dataclass, helper, and SKU calculation functions.

- [x] **Task 1.5.4**: Implement velocity trend ratios (A30:A90_Dep)
  - Spec: specs/04-inventory-metrics.md
  - Acceptance: >1 indicates acceleration, <1 indicates deceleration
  - Completed: 2026-02-03
  - Notes: Created calculate_velocity_trend() and calculate_velocity_trend_from_totals() pure functions. Formula: A30:A90 = (total_30d / 30) / (total_90d / 90). Returns None for zero historical data (cannot calculate trend). Created VelocityTrendMetrics dataclass with depletion and shipment velocity trends. Added calculate_velocity_trend_for_sku() and calculate_velocity_trend_all_skus() async functions with warehouse_id and distributor_id filter support. 26 new tests covering pure functions, dataclass, and SKU calculation functions.

- [x] **Task 1.5.5**: Create metrics API endpoint
  - Spec: specs/04-inventory-metrics.md
  - Acceptance: GET /metrics returns all metrics, supports SKU filter
  - Completed: 2026-02-03
  - Notes: Created src/api/metrics.py with GET /metrics (all SKUs) and GET /metrics/{sku} (single SKU) endpoints. Features include: DOH_T30/T90, shipment:depletion ratios, and velocity trends. Supports filtering by warehouse_id, warehouse_code, distributor_id, and distributor_name. Returns combined SKUMetrics with all three metric categories. 12 tests covering success, filtering, 404 errors, and edge cases (None values for zero depletions).

### Priority 1.6: Dashboard & Alerting
- [x] **Task 1.6.1**: Deploy Redash on Railway
  - Spec: specs/06-dashboard-alerting.md
  - Acceptance: Redash accessible via web URL
  - Completed: 2026-02-03
  - Notes: Created separate Railway project "une-femme-redash" (b8f5ae7c-d682-46e8-9beb-5ef77a657d15) with Redash template. Services deployed: Redash-Server (web UI on redash/redash:latest image), Scheduled Worker (query scheduling), ADHOC Worker (query execution), Postgres (database), KeyDB (Redis cache). Ran database migrations via `railway ssh "./manage.py database create_tables"`. Redash accessible at https://redash-server-production-920f.up.railway.app (initial setup page).

- [x] **Task 1.6.2**: Connect Redash to PostgreSQL database
  - Spec: specs/06-dashboard-alerting.md
  - Acceptance: Data source configured, test query succeeds
  - Completed: 2026-02-03
  - Notes: Created admin user (admin@unefemmewines.com) via Redash setup API. Configured PostgreSQL data source "Une Femme Supply Chain" pointing to Railway PostgreSQL (centerbeam.proxy.rlwy.net:22539). Also ran Alembic migrations on production database to create all tables (products, warehouses, distributors, inventory_events) and materialized views (mv_daily_metrics, mv_doh_metrics). Test query on products table returned all 4 SKUs successfully.

- [x] **Task 1.6.3**: Create DOH overview dashboard query
  - Spec: specs/06-dashboard-alerting.md
  - Acceptance: Shows DOH_T30, DOH_T90 for all 4 SKUs
  - Completed: 2026-02-03
  - Notes: Created SQL queries for DOH overview dashboard in sql/redash/: doh_overview.sql (uses mv_doh_metrics materialized view), doh_by_sku.sql (aggregated by SKU), and doh_overview_direct.sql (real-time query from inventory_events). Created scripts/setup_redash_dashboard.py to automate query creation via Redash API. Queries show SKU, warehouse, on_hand, depletions_30d/90d, doh_t30, doh_t90, and status (CRITICAL/WARNING/NO SALES/OK). Results ordered by severity. 38 tests covering SQL syntax, file existence, and script functionality.

- [x] **Task 1.6.4**: Create shipment:depletion ratio visualization
  - Spec: specs/06-dashboard-alerting.md
  - Acceptance: Chart shows ratios with color coding
  - Completed: 2026-02-03
  - Notes: Created SQL queries for ship:dep ratio dashboards: ship_dep_ratio.sql (uses mv_doh_metrics), ship_dep_ratio_by_sku.sql (aggregated by SKU), and ship_dep_ratio_direct.sql (real-time from inventory_events). Added SHIP_DEP_RATIO_QUERY and SHIP_DEP_RATIO_BY_SKU_QUERY to setup script. Created setup_ratio_visualizations() function with bar chart configuration and color coding (Red=UNDERSUPPLY <0.5, Yellow=OVERSUPPLY >2.0, Green=BALANCED). Added create_visualization() and get_query() methods to RedashClient. 42 new tests covering SQL queries and script functionality.

- [x] **Task 1.6.5**: Configure stock-out risk alert (DOH_T30 < 14)
  - Spec: specs/06-dashboard-alerting.md
  - Acceptance: Alert fires when threshold breached
  - Completed: 2026-02-03
  - Notes: Created SQL query (stockout_alert.sql) that returns SKUs with DOH_T30 < 14 days. Added alert API methods to RedashClient (get_alerts, get_alert, create_alert, update_alert, get_alert_subscriptions, add_alert_subscription, get_destinations). Created setup_stockout_alert() function that: 1) Creates/updates the alert query, 2) Creates/updates the alert with custom subject/body. Alert rearms after 1 hour to prevent spam. 21 new tests covering SQL syntax, query content, helper functions, and API methods.

- [x] **Task 1.6.6**: Configure Slack notification for alerts
  - Spec: specs/06-dashboard-alerting.md
  - Acceptance: Slack message sent when alert fires
  - Completed: 2026-02-03
  - Notes: Added Slack notification support to Redash setup script. Created create_destination() and update_destination() methods in RedashClient for managing notification destinations. Created find_destination_by_name() and find_subscription_by_destination() helper functions. Created setup_slack_notification() function that creates/updates Slack webhook destination and subscribes alerts to it. Updated main() to configure Slack notification after creating stock-out alert. Uses SLACK_WEBHOOK_URL environment variable for webhook URL. 12 new tests covering helper functions and API methods.

- [x] **Task 1.6.7**: Configure email notification for alerts
  - Spec: specs/06-dashboard-alerting.md
  - Acceptance: Email sent when alert fires
  - Completed: 2026-02-03
  - Notes: Added setup_email_notification() function to Redash setup script. Creates/updates email destination type "Email - Supply Chain Alerts" and subscribes stock-out alert to it. Uses ALERT_EMAIL_ADDRESSES environment variable for comma-separated email addresses. Pattern mirrors setup_slack_notification(). 10 new tests covering function existence, environment variable usage, destination configuration, and main() integration.

## Phase 2: Automation (P1)

### Priority 2.1: Demand Forecasting
- [x] **Task 2.1.1**: Create Prophet model training function
  - Spec: specs/05-demand-forecasting.md
  - Acceptance: Model trains on 2+ years data with multiplicative seasonality
  - Completed: 2026-02-03
  - Notes: Created src/services/forecast.py with train_forecast_model() function. Features: multiplicative seasonality (critical for champagne), linear growth, weekly/yearly seasonality, holiday calendar with NYE (7-day lead-up for 7.5x spike), Valentine's, Mother's Day, Thanksgiving. Minimum 2 years (104 weeks/728 days) training data required. Includes validate_model() for cross-validation, get_training_data() for DB retrieval, calculate_safety_stock() helper. 44 tests covering training, holidays, forecasting, and integration.

- [x] **Task 2.1.2**: Define holiday calendar (NYE, Valentine's, etc.)
  - Spec: specs/05-demand-forecasting.md
  - Acceptance: Holiday effects included with 7-day lower window
  - Completed: 2026-02-03
  - Notes: Created create_wine_holidays() function returning DataFrame with wine industry holidays for years 2020-2030. NYE has 7-day lower_window and 1-day upper_window for champagne spike. Valentine's Day has 7-day lower_window. Mother's Day (second Sunday of May) and Thanksgiving (fourth Thursday of November) also included. Holidays are automatically applied to Prophet model via train_forecast_model().

- [x] **Task 2.1.3**: Implement 26-week forecast generation
  - Spec: specs/05-demand-forecasting.md
  - Acceptance: Returns weekly predictions with 80%/95% intervals
  - Completed: 2026-02-03
  - Notes: Created generate_forecast() function that produces weekly forecasts with configurable interval_width (default 80%, supports 95%). Returns DataFrame with ds, yhat, yhat_lower, yhat_upper columns. ForecastPoint and ForecastResult dataclasses provide structured results. train_forecast_model_for_sku() combines data retrieval, training, and forecast generation in one async function.

- [x] **Task 2.1.4**: Create weekly retraining Celery job
  - Spec: specs/05-demand-forecasting.md
  - Acceptance: Job runs Mondays, updates forecasts table
  - Completed: 2026-02-03
  - Notes: Created src/tasks/forecast_retrain.py with retrain_forecasts Celery task that runs weekly on Mondays at 7 AM UTC. Task trains Prophet models for all 4 SKUs, generates 26-week forecasts, and stores results in new forecasts table. Created Forecast SQLAlchemy model with proper indexes. Created Alembic migration (a1b2c3d4e5f6) for forecasts table. Added beat schedule to celery_app.py. 23 new tests covering task functions, model, and schedule configuration.

- [ ] **Task 2.1.5**: Add forecast visualization to Redash
  - Spec: specs/05-demand-forecasting.md
  - Acceptance: Chart shows forecast with confidence bands

### Priority 2.2: Email Classification
- [ ] **Task 2.2.1**: Implement Gmail API OAuth connection
  - Spec: specs/07-email-classification.md
  - Acceptance: OAuth flow completes, token stored

- [ ] **Task 2.2.2**: Create email classification prompt with Ollama
  - Spec: specs/07-email-classification.md
  - Acceptance: Classifies PO/BOL/Invoice/General with >94% accuracy

- [ ] **Task 2.2.3**: Build email processing queue with Celery
  - Spec: specs/07-email-classification.md
  - Acceptance: Emails classified within 15 seconds

- [ ] **Task 2.2.4**: Create human review queue endpoint
  - Spec: specs/07-email-classification.md
  - Acceptance: Low-confidence classifications (<85%) flagged

### Priority 2.3: Document OCR
- [ ] **Task 2.3.1**: Integrate Azure Document Intelligence SDK
  - Spec: specs/08-document-ocr.md
  - Acceptance: Client authenticated, test document processed

- [ ] **Task 2.3.2**: Create PO extraction schema and processor
  - Spec: specs/08-document-ocr.md
  - Acceptance: Extracts PO#, vendor, items, quantities with >93% accuracy

- [ ] **Task 2.3.3**: Create BOL extraction schema and processor
  - Spec: specs/08-document-ocr.md
  - Acceptance: Extracts shipper, consignee, tracking, cargo

- [ ] **Task 2.3.4**: Create Invoice extraction using prebuilt model
  - Spec: specs/08-document-ocr.md
  - Acceptance: Extracts invoice#, amounts, line items

## Phase 3: Intelligence (P2)

### Priority 3.1: Agentic Automation
- [ ] **Task 3.1.1**: Create LangGraph state machine scaffold
  - Spec: specs/09-agentic-automation.md
  - Acceptance: Basic graph compiles and runs

- [ ] **Task 3.1.2**: Implement demand forecaster agent node
  - Spec: specs/09-agentic-automation.md
  - Acceptance: Node calls Prophet and returns forecast

- [ ] **Task 3.1.3**: Implement inventory optimizer agent node
  - Spec: specs/09-agentic-automation.md
  - Acceptance: Calculates safety stock and reorder quantity

- [ ] **Task 3.1.4**: Implement human approval interrupt node
  - Spec: specs/09-agentic-automation.md
  - Acceptance: Workflow pauses for orders >$10K

- [ ] **Task 3.1.5**: Create audit trail logging
  - Spec: specs/09-agentic-automation.md
  - Acceptance: All agent decisions logged with reasoning

### Priority 3.2: QuickBooks Integration
- [ ] **Task 3.2.1**: Implement QuickBooks OAuth 2.0 flow
  - Spec: specs/10-quickbooks-integration.md
  - Acceptance: OAuth completes, tokens stored

- [ ] **Task 3.2.2**: Create inventory sync function
  - Spec: specs/10-quickbooks-integration.md
  - Acceptance: Inventory levels match between systems (±1%)

- [ ] **Task 3.2.3**: Implement invoice pull from QuickBooks
  - Spec: specs/10-quickbooks-integration.md
  - Acceptance: Invoices retrieved and stored locally

## Discoveries

_Updated by Ralph during execution - document any findings, blockers, or spec corrections here._

- **2026-02-03**: Python 3.13 is available on the system. Poetry installed and project uses Python ^3.11 for compatibility with Prophet and other dependencies. All dependencies install successfully including FastAPI, SQLAlchemy, Celery, Prophet, LangGraph, and Azure Document Intelligence SDK.

- **2026-02-03**: Railway PostgreSQL is version 17.7. **TimescaleDB is NOT available** on Railway's standard PostgreSQL offering. The spec mentions TimescaleDB for hypertables and continuous aggregates, but these features will need to be implemented using standard PostgreSQL features:
  - Instead of hypertables: Use regular tables with time-based indexes (BRIN indexes are efficient for time-series)
  - Instead of continuous aggregates: Use materialized views with scheduled refreshes
  - Task 1.2.2 and 1.2.4 will need spec adjustments to use standard PostgreSQL alternatives

---

## Revision History
- 2026-02-03: Initial plan created from PRD.md
