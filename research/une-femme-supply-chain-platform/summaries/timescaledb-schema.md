---
created: 2026-02-03
source_url: https://www.slingacademy.com/article/best-practices-for-schema-design-in-postgresql-with-timescaledb/ | https://supabase.com/docs/guides/database/extensions/timescaledb
source_type: industry/documentation
research_focus: TimescaleDB schema design for inventory time-series data in wine supply chain
tags: [timescaledb, schema-design, time-series-database, inventory-analytics, continuous-aggregates, data-compression]
---

# TimescaleDB Schema Design Best Practices for Inventory Time-Series Analytics

**Primary Sources:**
1. https://www.slingacademy.com/article/best-practices-for-schema-design-in-postgresql-with-timescaledb/
2. https://supabase.com/docs/guides/database/extensions/timescaledb

## Citation

Sling Academy. "Best Practices for Schema Design in PostgreSQL with TimescaleDB." Accessed 2026-02-03.

Supabase Documentation. "TimescaleDB Extension Guide." Accessed 2026-02-03. https://supabase.com/docs/guides/database/extensions/timescaledb

## Executive Summary

TimescaleDB is a specialized PostgreSQL extension designed to optimize time-series data management, employing "a time-series-aware storage model and indexing techniques" to enhance performance when handling temporal datasets at scale. For the Une Femme wine supply chain platform, TimescaleDB's hypertable architecture enables efficient storage and querying of inventory movements, stock levels, and depletion metrics across SKUs and warehouse locations. The extension automatically partitions data into time-based chunks, enabling parallel processing and write-heavy optimization critical for real-time inventory tracking. This source provides the foundational schema design principles, hypertable configuration strategies, and continuous aggregates implementation required to build a scalable inventory analytics system that can track days-on-hand (DOH), depletion rates, and SKU-level metrics without compromising query performance as data volumes grow.

## Key Concepts & Definitions

- **Hypertable**: TimescaleDB's core abstraction that functions as a "partitioned virtual table structure" automatically dividing time-series data into time-based chunks. Unlike standard PostgreSQL tables, hypertables transparently manage data lifecycle and optimize queries across all chunks simultaneously. Created via `SELECT create_hypertable('metrics', 'time');` with time column as the primary partitioning key.

- **Chunks**: Automatic time-based partitions of hypertable data, typically spanning hours to days depending on data ingestion volume. TimescaleDB manages chunk creation, compression, and lifecycle automatically, allowing developers to query the hypertable as a single logical table while gaining partitioning performance benefits.

- **Continuous Aggregates**: Pre-computed materialized views that incrementally update as new data arrives, enabling efficient computation of rolling aggregations (e.g., inventory changes, depletion rates) without rescanning all historical data. Critical for real-time analytics on inventory trends.

- **Chunk Interval**: The time duration each chunk spans before a new chunk is created (e.g., 1 day, 7 days). Proper sizing balances query performance, compression efficiency, and memory usage. Misaligned chunk intervals can lead to inefficient data organization and slower range queries.

- **Data Compression**: TimescaleDB's native compression feature reduces storage footprint for older, less-frequently-queried chunks through columnar storage and dictionary encoding. Can achieve 80-90% storage reduction on time-series data.

- **Time Zone-Aware Timestamps (TIMESTAMPTZ)**: Recommended data type for temporal columns to ensure consistent time handling across warehouse locations and supply chain operations, preventing ambiguity in inventory event timestamps.

- **Strategic Indexing**: Creating indexes on frequently queried columns (especially descending indexes on time columns: `CREATE INDEX ON metrics (time DESC);`) optimizes ordering and filtering operations, particularly important for DOH and depletion rate calculations.

## Main Arguments / Insights / Features

### 1. Data Model Foundation: Understanding Entities and Relationships for Inventory Tracking

Effective TimescaleDB schema design begins with clarifying the core entities and their temporal relationships. For wine supply chain inventory, the primary entities are:
- **Stock Events** (inventory movements with precise timestamps)
- **SKUs** (stock-keeping units with product hierarchies)
- **Warehouse Locations** (distribution centers and retail points)
- **Depletion Metrics** (calculated rates of stock reduction)

The source emphasizes: "Begin by clarifying your entities and relationships, particularly important for time-series scenarios where temporal structure matters significantly." This foundational step determines hypertable design, foreign key relationships, and continuous aggregate definitions.

For Une Femme, this translates to designing a schema where each inventory movement (receipt, sale, adjustment) becomes a discrete time-series event with associated SKU, location, and quantity attributes. The temporal structure should enable efficient queries of inventory state at any point in time and calculation of depletion rates within specific periods.

### 2. Appropriate Data Types: TIMESTAMPTZ for Temporal Accuracy and SERIAL for Identity

The guide emphasizes choosing correct data types as "crucial for time-series analysis." For inventory systems:

**TIMESTAMPTZ (Timestamp with Time Zone)**: All inventory event timestamps must use this type to handle operations across multiple warehouse locations and time zones. This prevents ambiguity when comparing events and calculating rates across geographies. The source states this choice is "crucial for time-series analysis."

**SERIAL or BIGSERIAL**: For unique event identifiers, providing immutable identity for inventory movements. Important for audit trails and referential integrity.

**NUMERIC for Quantities**: For inventory counts and depletion calculations, NUMERIC provides precision without floating-point rounding errors. Critical when tracking precise stock levels and calculating rates to multiple decimal places.

**TEXT or VARCHAR for SKU Codes**: For product identifiers, allowing variable-length wine SKU codes with alphanumeric characters.

Example schema foundation:
```sql
CREATE TABLE inventory_events (
  id BIGSERIAL PRIMARY KEY,
  time TIMESTAMPTZ NOT NULL,
  sku_id INTEGER NOT NULL,
  warehouse_id INTEGER NOT NULL,
  quantity_change NUMERIC NOT NULL,
  event_type TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

### 3. Hypertable Partitioning: Automatic Time-Based Optimization

TimescaleDB's hypertable mechanism handles the complexity of partitioning transparently. The source emphasizes that "hypertables help balance both concerns through automatic partitioning," referring to the tension between normalization and query complexity.

Conversion to hypertable:
```sql
SELECT create_hypertable('inventory_events', 'time');
```

This single operation transforms the table into a hypertable partitioned by the time column, automatically creating new chunks as data arrives. The extension then "enables query performance for time-series workloads" through:

- **Parallel Processing**: Queries automatically execute across multiple chunks in parallel
- **Chunk Elimination**: Range queries on time automatically filter out irrelevant chunks before scanning
- **Compression Pipeline**: Old chunks can be automatically compressed, reducing storage while maintaining query capability

For inventory tracking, hypertables eliminate manual partitioning logic. Queries for "inventory state on February 1" automatically scan only the relevant day's chunk(s), rather than full table scans.

### 4. Efficient Normalization Balanced with Query Complexity

The source cautions that "extreme normalization can lead to complex join operations," a key tradeoff in inventory schema design. The recommended approach:

**Denormalized Event Tables**: Store frequently-joined attributes directly in the hypertable rather than requiring joins for every query. For inventory events, this means including warehouse_id, sku_id, and event_type directly rather than forcing lookups to reference tables.

**Normalized Dimension Tables**: Maintain separate tables for slowly-changing dimensions (products, warehouses, locations) with foreign key relationships for data integrity, but avoid normalizing the high-cardinality time-series fact table.

Example schema:
```sql
-- Denormalized time-series events
CREATE TABLE inventory_events (
  id BIGSERIAL PRIMARY KEY,
  time TIMESTAMPTZ NOT NULL,
  sku_id INTEGER NOT NULL,
  warehouse_id INTEGER NOT NULL,
  quantity_change NUMERIC NOT NULL,
  event_type TEXT NOT NULL
);

-- Normalized dimensions (referenced via FK, not joined in queries)
CREATE TABLE skus (
  id INTEGER PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,
  name TEXT,
  category TEXT,
  min_stock NUMERIC
);

CREATE TABLE warehouses (
  id INTEGER PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,
  name TEXT,
  location TEXT
);

-- FK constraints maintain integrity
ALTER TABLE inventory_events
  ADD CONSTRAINT fk_sku FOREIGN KEY (sku_id) REFERENCES skus(id),
  ADD CONSTRAINT fk_warehouse FOREIGN KEY (warehouse_id) REFERENCES warehouses(id);
```

This balances normalization benefits (single source of truth for SKU/warehouse data) with query efficiency (no expensive joins on every event query).

### 5. Strategic Indexing: Accelerating Inventory Queries

The source recommends: "Creating indexes on frequently queried columns improves performance, particularly on time columns: `CREATE INDEX ON metrics (time DESC);` optimizes ordering and filtering operations."

For inventory analytics, essential indexes include:

**Time-Based Indexes (Descending)**:
```sql
CREATE INDEX ON inventory_events (time DESC);
```
Optimizes queries filtering by recent events or calculating latest inventory state, a dominant access pattern for real-time supply chain visibility.

**Composite Indexes for Common Queries**:
```sql
CREATE INDEX ON inventory_events (warehouse_id, time DESC);
CREATE INDEX ON inventory_events (sku_id, time DESC);
CREATE INDEX ON inventory_events (warehouse_id, sku_id, time DESC);
```
Enable efficient queries like "get depletion rate for SKU X at warehouse Y over the last 30 days" without full table scans.

**BRIN Indexes** (Block Range Indexes): TimescaleDB's documentation notes these are particularly effective on hypertables due to time-ordered data:
```sql
CREATE INDEX ON inventory_events USING BRIN (time);
```
Dramatically reduces index size compared to B-tree indexes while maintaining performance for range queries.

The source emphasizes that these indexes directly enable "extensive analytic workloads efficiently and reliably."

### 6. Data Integrity: Constraints Maintaining Accuracy

The source notes constraints like `CHECK`, `UNIQUE`, and `FOREIGN KEY` "maintain accuracy, though balance constraints against complexity."

For inventory systems, critical constraints include:

**NOT NULL Constraints**: Ensure all events have timestamps, SKUs, and warehouses. A NULL warehouse_id makes the event unmappable to a location.

**CHECK Constraints**: Enforce business logic:
```sql
ALTER TABLE inventory_events
  ADD CONSTRAINT valid_event_type CHECK (event_type IN ('receipt', 'sale', 'adjustment', 'transfer'));
```

**FOREIGN KEY Constraints**: Ensure referential integrity to SKU and warehouse dimensions:
```sql
ALTER TABLE inventory_events
  ADD CONSTRAINT fk_sku FOREIGN KEY (sku_id) REFERENCES skus(id);
```

**Tradeoff Consideration**: The source cautions against excessive constraints as they increase insert complexity. For high-volume inventory streams (potentially millions of events daily), minimize constraint overhead by validating in the application layer while maintaining critical FK relationships.

### 7. Continuous Aggregates for Real-Time Inventory Analytics

While the source introduces continuous aggregates conceptually, this is critical for Une Femme's analytics needs. TimescaleDB's continuous aggregates pre-compute rolling metrics as new data arrives.

**Days-on-Hand (DOH) Aggregates**:
```sql
CREATE MATERIALIZED VIEW inventory_doh_daily AS
SELECT
  time_bucket('1 day', time) AS day,
  sku_id,
  warehouse_id,
  AVG(quantity_on_hand) AS avg_quantity,
  MIN(quantity_on_hand) AS min_quantity,
  MAX(quantity_on_hand) AS max_quantity,
  COUNT(*) AS event_count
FROM inventory_events
GROUP BY 1, 2, 3
WITH DATA;

CREATE INDEX ON inventory_doh_daily (day DESC, sku_id, warehouse_id);
```

**Depletion Rate Aggregates**:
```sql
CREATE MATERIALIZED VIEW inventory_depletion_weekly AS
SELECT
  time_bucket('1 week', time) AS week,
  sku_id,
  warehouse_id,
  FIRST(quantity_on_hand, time) - LAST(quantity_on_hand, time) AS units_depleted,
  (FIRST(quantity_on_hand, time) - LAST(quantity_on_hand, time)) / NULLIF(FIRST(quantity_on_hand, time), 0) AS depletion_rate,
  COUNT(*) AS events_per_week
FROM inventory_events
WHERE event_type = 'sale'
GROUP BY 1, 2, 3
WITH DATA;

CREATE INDEX ON inventory_depletion_weekly (week DESC, sku_id, warehouse_id);
```

These views automatically update as new events arrive, enabling dashboard displays of DOH and depletion rates without expensive recalculation. The materialized view approach eliminates the need to scan raw events for every analytics query.

### 8. Chunk Interval Sizing: Balancing Performance and Storage

The sources indicate chunk intervals must be tuned based on data ingestion patterns. Key considerations:

**Daily Chunk Intervals**: Appropriate for inventory systems with moderate event volume (thousands of events per day per warehouse). Provides:
- Fine granularity for recent data analysis
- Efficient compression scheduling for older chunks
- Manageable memory consumption during queries

**Weekly Chunk Intervals**: For very high-volume operations (millions of events daily), larger chunks reduce overhead but may slow compression and extend memory usage during complex queries.

Configuration:
```sql
SELECT set_chunk_time_interval('inventory_events', interval '1 day');
```

**Sizing Recommendation for Une Femme**: Assume 10,000-50,000 inventory events daily across all warehouses and SKUs. A **1-day chunk interval** balances:
- Daily granularity for DOH tracking
- Manageable chunk size (1-100MB per day depending on event density)
- Automatic compression triggers on chunks older than 30 days

If event volume exceeds 100,000 daily, consider 7-day intervals with more frequent compression scheduling.

### 9. Compression Strategies for Historical Data

Supabase documentation notes TimescaleDB offers "compression, write-heavy workload optimization, and parallel processing capabilities." Compression strategies:

**Automatic Compression on Schedule**:
```sql
SELECT add_compression_policy('inventory_events', INTERVAL '30 days');
```

Automatically compresses chunks older than 30 days, reducing storage from ~100MB to ~10-20MB per chunk through columnar storage and dictionary encoding.

**Compression Benefits**:
- 80-90% storage reduction on time-series data
- Maintained query capability on compressed chunks (transparent decompression)
- Reduced I/O during range queries spanning compressed historical data
- Cost reduction for cloud database storage

**Tradeoff**: Compressed chunks are slightly slower to query than uncompressed chunks due to decompression overhead. Critical pattern: keep recent 30-90 days uncompressed for fast real-time analytics; compress older historical data accessed infrequently.

### 10. Documentation and Schema Evolution

The source emphasizes "maintaining schema documentation facilitates future development and scaling efforts." For Une Femme supply chain platform:

**Documentation Should Include**:
- Hypertable column definitions with business semantics (what does quantity_change represent?)
- Chunk interval rationale and review schedule
- Continuous aggregate definitions and refresh rates
- Compression policy justification
- Index design decisions for specific query patterns
- FK relationships and referential integrity constraints

**Schema Version Control**: Store DDL scripts in version control with migration tracking for:
- Adding new event types (e.g., 'transfer' events between warehouses)
- Creating new continuous aggregates for emerging metrics
- Modifying chunk intervals if data volume patterns change
- Adjusting compression policies based on storage/query performance tradeoffs

## Methodology / Approach

The sources employ a **prescriptive best-practices methodology** combining:

1. **Design Principles**: Starting with data model understanding before implementation
2. **PostgreSQL/TimescaleDB Feature Walkthroughs**: Introducing each TimescaleDB capability with SQL examples
3. **Tradeoff Analysis**: Acknowledging tensions (normalization vs. join complexity, constraints vs. insert performance) rather than prescribing one-size-fits-all solutions
4. **Practical Examples**: Concrete SQL patterns for hypertable creation, indexing, and aggregation
5. **Configuration Guidance**: Chunk interval sizing, compression policies, and index strategies with rationale

The Sling Academy source provides foundational PostgreSQL schema design principles applied to TimescaleDB context. The Supabase documentation offers implementation guidance specific to cloud-hosted TimescaleDB with deprecation warnings for future planning.

## Specific Examples & Case Studies

### Example 1: Wine Inventory Event Schema

Based on source principles, a practical schema for wine supply chain inventory:

```sql
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb WITH SCHEMA extensions;

-- Dimension tables (slowly changing)
CREATE TABLE skus (
  id INTEGER PRIMARY KEY,
  code VARCHAR(50) UNIQUE NOT NULL,
  name VARCHAR(255) NOT NULL,
  category VARCHAR(50),
  vintage INTEGER,
  price_point NUMERIC(10, 2),
  min_stock_threshold INTEGER DEFAULT 100
);

CREATE TABLE warehouses (
  id INTEGER PRIMARY KEY,
  code VARCHAR(20) UNIQUE NOT NULL,
  name VARCHAR(255),
  location VARCHAR(100),
  max_capacity INTEGER
);

-- Time-series fact table (high cardinality)
CREATE TABLE inventory_events (
  id BIGSERIAL PRIMARY KEY,
  time TIMESTAMPTZ NOT NULL,
  sku_id INTEGER NOT NULL,
  warehouse_id INTEGER NOT NULL,
  quantity_change INTEGER NOT NULL,
  event_type VARCHAR(20) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  CONSTRAINT fk_sku FOREIGN KEY (sku_id) REFERENCES skus(id),
  CONSTRAINT fk_warehouse FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
  CONSTRAINT valid_event_type CHECK (event_type IN ('receipt', 'sale', 'adjustment', 'return')),
  CONSTRAINT non_zero_quantity CHECK (quantity_change <> 0)
);

-- Create hypertable
SELECT create_hypertable('inventory_events', 'time', if_not_exists => TRUE);

-- Set chunk interval to 1 day
SELECT set_chunk_time_interval('inventory_events', INTERVAL '1 day');

-- Add compression policy
SELECT add_compression_policy('inventory_events', INTERVAL '30 days');

-- Strategic indexes
CREATE INDEX idx_time_desc ON inventory_events (time DESC);
CREATE INDEX idx_warehouse_time ON inventory_events (warehouse_id, time DESC);
CREATE INDEX idx_sku_time ON inventory_events (sku_id, time DESC);
CREATE INDEX idx_warehouse_sku_time ON inventory_events (warehouse_id, sku_id, time DESC);

-- Days-on-Hand continuous aggregate
CREATE MATERIALIZED VIEW inventory_status_hourly AS
SELECT
  time_bucket('1 hour', time) AS hour,
  sku_id,
  warehouse_id,
  SUM(quantity_change) AS net_change,
  COUNT(*) AS event_count
FROM inventory_events
GROUP BY 1, 2, 3
WITH DATA;

-- Depletion rate weekly aggregate
CREATE MATERIALIZED VIEW depletion_metrics_weekly AS
SELECT
  time_bucket('1 week', time) AS week,
  sku_id,
  warehouse_id,
  ABS(SUM(CASE WHEN event_type = 'sale' THEN quantity_change ELSE 0 END)) AS units_sold,
  COUNT(CASE WHEN event_type = 'sale' THEN 1 END) AS sale_events,
  COUNT(*) AS total_events
FROM inventory_events
GROUP BY 1, 2, 3
WITH DATA;

-- Current inventory view (latest snapshot)
CREATE MATERIALIZED VIEW current_inventory AS
SELECT
  sku_id,
  warehouse_id,
  (SELECT SUM(quantity_change) FROM inventory_events ie
   WHERE ie.sku_id = inventory_events.sku_id
   AND ie.warehouse_id = inventory_events.warehouse_id) AS quantity_on_hand,
  (SELECT MAX(time) FROM inventory_events ie
   WHERE ie.sku_id = inventory_events.sku_id
   AND ie.warehouse_id = inventory_events.warehouse_id) AS last_event_time
FROM inventory_events
GROUP BY 1, 2
WITH DATA;
```

This schema directly applies the sources' recommendations: TIMESTAMPTZ for accuracy, appropriate data types, strategic indexes, hypertable partitioning, and continuous aggregates for analytics.

### Example 2: Query Patterns Enabled by Schema

**Query 1: DOH Trend for Specific SKU at Warehouse**
```sql
SELECT
  hour,
  net_change,
  SUM(net_change) OVER (ORDER BY hour) AS cumulative_on_hand
FROM inventory_status_hourly
WHERE sku_id = 42 AND warehouse_id = 5
  AND hour >= NOW() - INTERVAL '90 days'
ORDER BY hour;
```

Leverages hourly continuous aggregate, avoiding raw event table scan.

**Query 2: Depletion Rate Comparison Across Locations**
```sql
SELECT
  w.name,
  AVG(units_sold) AS avg_weekly_depletion,
  AVG(units_sold / NULLIF((SELECT AVG(q) FROM current_inventory WHERE warehouse_id = w.id), 0)) AS avg_depletion_rate
FROM depletion_metrics_weekly d
JOIN warehouses w ON d.warehouse_id = w.id
WHERE d.sku_id = 42
  AND d.week >= DATE_TRUNC('week', NOW()) - INTERVAL '12 weeks'
GROUP BY w.id, w.name
ORDER BY avg_weekly_depletion DESC;
```

Combines continuous aggregates with dimension tables for business intelligence.

**Query 3: Low-Stock Alerts**
```sql
SELECT
  s.code,
  s.name,
  w.name,
  ci.quantity_on_hand,
  s.min_stock_threshold,
  (s.min_stock_threshold - ci.quantity_on_hand) AS units_below_threshold
FROM current_inventory ci
JOIN skus s ON ci.sku_id = s.id
JOIN warehouses w ON ci.warehouse_id = w.id
WHERE ci.quantity_on_hand < s.min_stock_threshold
ORDER BY s.code, w.name;
```

Uses materialized view for instant low-stock detection without scanning events.

## Notable Quotes

- "Begin by clarifying your entities and relationships, particularly important for time-series scenarios where temporal structure matters significantly." - Sling Academy

- "Appropriate Data Types... choosing correct types... [TIMESTAMPTZ] is crucial for time-series analysis." - Sling Academy

- "While normalization reduces redundancy, extreme normalization can lead to complex join operations. TimescaleDB hypertables help balance both concerns through automatic partitioning." - Sling Academy

- "Creating indexes on frequently queried columns improves performance, particularly on time columns: CREATE INDEX ON metrics (time DESC); optimizes ordering and filtering operations." - Sling Academy

- "Hypertable Partitioning: TimescaleDB automatically handles partitioning through hypertables... which enhances query performance for time-series workloads." - Sling Academy

- "TimescaleDB is a specialized PostgreSQL extension for time-series data management. It employs a time-series-aware storage model and indexing techniques to enhance performance when handling temporal datasets at scale." - Supabase

- "The extension divides time-series data into time-based chunks, enabling efficient scaling for large datasets. It offers compression, write-heavy workload optimization, and parallel processing capabilities alongside specialized functions and operators for temporal analysis." - Supabase

## Evidence Quality Assessment

**Strength of Evidence**: Moderate to Strong

**Evidence Types Present**:
- [x] Empirical data / statistics (Supabase mentions 80-90% compression ratios)
- [x] Case studies / real-world examples (Sensor monitoring, analytical workloads)
- [x] Expert testimony / citations (Sling Academy and Supabase as recognized PostgreSQL/TimescaleDB authorities)
- [x] Theoretical reasoning (Hypertable partitioning logic, index optimization tradeoffs)
- [ ] Anecdotal evidence

**Credibility Indicators**:

- **Author/Source Authority**: High credibility. Sling Academy is an established tech education platform with PostgreSQL expertise. Supabase is a production-ready PostgreSQL-as-a-service platform with significant industry adoption, making their documentation authoritative for practical implementation guidance.

- **Currency**: Moderate to Good. Sling Academy article is timely on schema design principles. Supabase documentation is current but includes important note: "TimescaleDB is deprecated for Postgres 17 but remains supported on Postgres 15 until upgrade." This indicates sources recognize deprecation implications for future planning.

- **Transparency**: Good. Both sources clearly explain design tradeoffs (e.g., normalization vs. join complexity), acknowledge constraints, and provide concrete SQL examples. Sources admit when guidance depends on specific workload characteristics rather than prescribing universal rules.

- **Peer Review/Validation**: Moderate. Not formal academic peer review, but Supabase's documentation reflects validated production experience with thousands of users. Sling Academy reflects industry consensus on schema design principles.

## Critical Evaluation

**Strengths**:

1. **Practical Implementation Focus**: Both sources provide concrete SQL examples immediately applicable to Une Femme's platform, not just theoretical concepts.

2. **Tradeoff Transparency**: Sources acknowledge tensions (normalization vs. query complexity, constraints vs. insert performance, chunk size vs. compression efficiency) rather than suggesting universal solutions, enabling context-appropriate decisions.

3. **Complete Feature Coverage**: Sources cover the full TimescaleDB feature set relevant to inventory analytics: hypertables, continuous aggregates, compression, and indexing strategies.

4. **Schema Design Principles**: Foundational guidance on entities, relationships, and data types provides framework for designing custom inventory-specific schemas.

5. **Deprecation Warning**: Supabase explicitly flags TimescaleDB's Postgres 17 deprecation status, enabling informed planning for platform modernization.

**Limitations**:

1. **Limited Performance Benchmarking**: Sources provide general compression ratios (80-90%) but lack detailed benchmarks for specific query patterns (DOH queries, depletion rate calculations) or chunk interval tradeoff analysis.

2. **Workload-Specific Gaps**: No guidance tailored to high-frequency inventory updates (millions of SKU-location combinations, constant receipt/sale events) versus periodic aggregation workloads.

3. **Operational Considerations**: Limited discussion of monitoring, alerting, and troubleshooting hypertable performance in production (e.g., detecting suboptimal chunk intervals, compression bottlenecks).

4. **Migration Path Underexplored**: Sources don't address migrating existing inventory systems to TimescaleDB hypertables without downtime or data loss.

5. **Continuous Aggregate Refresh Strategy**: Conceptually introduced but lacks guidance on refresh frequency, staleness tolerance, and incremental update strategies.

**Potential Biases**:

1. **TimescaleDB Promotion**: Supabase benefits commercially from TimescaleDB adoption on their platform, potentially biasing recommendations toward TimescaleDB even where native PostgreSQL partitioning might suffice.

2. **Cloud-Hosted Perspective**: Supabase's documentation assumes cloud-hosted PostgreSQL; some deprecation/version concerns may not apply to self-hosted deployments.

3. **Schema Design Orthodoxy**: Sources reflect conventional PostgreSQL schema design wisdom; may not address wine supply chain-specific requirements (e.g., vintage tracking, region-specific regulations).

## Relevance to Research Focus

**Primary Research Angle(s) Addressed**:

1. **Hypertable Design for Inventory Movements** - Directly addresses with practical schema examples, partitioning strategies, and real-world tradeoffs.

2. **Chunk Interval Sizing Recommendations** - Provides guidance (1-day intervals for moderate volume, 7-day for high volume) with rationale based on data ingestion patterns.

3. **Continuous Aggregates for Analytics (DOH, Depletion Rates)** - Covers materialized view patterns for DOH tracking and depletion rate calculations with specific SQL examples.

4. **Compression Strategies** - Discusses automatic compression policies, storage reduction (80-90%), and query implications for historical data.

5. **Schema Design for SKU-Level Metrics** - Provides normalized dimension table patterns for SKU attributes while maintaining denormalized time-series event tables for performance.

**Specific Contributions to Research**:

- **Inventory Hypertable Foundation**: The schema example (inventory_events table with time, sku_id, warehouse_id, quantity_change) provides direct blueprint for Une Femme's fact table, immediately applicable to implementation.

- **Continuous Aggregate Patterns**: Specific materialized view definitions for hourly status snapshots and weekly depletion metrics offer starting point for analytics layer.

- **Performance Framework**: Strategic indexing recommendations (time DESC, composite warehouse+time, SKU+time) directly optimize queries required for supply chain visibility dashboards.

- **Operational Decisions**: Chunk interval (1 day), compression (30-day threshold), and constraint design recommendations are immediately actionable without further research.

- **Deprecation Planning**: Explicit warning about Postgres 17 deprecation enables informed decision on platform evolution timeline.

**Gaps This Source Fills**:

- Sources provide complete PostgreSQL/TimescaleDB framework for time-series inventory schema design, filling gap between high-level supply chain concepts and concrete database implementation.

- Practical continuous aggregate patterns address how to efficiently compute DOH and depletion metrics for analytics without custom application logic.

**Gaps Still Remaining**:

1. **Wine Supply Chain Specificity**: No guidance on how to model wine-specific attributes (vintage, region, varietals, regulatory compliance tracking) alongside inventory movement tracking.

2. **Multi-Warehouse Optimization**: Limited guidance on distributed inventory across geographically dispersed warehouses with potential replication/consistency considerations.

3. **Forecasting Integration**: Sources don't address schema design for integrating predictive inventory models, demand forecasting, or reconciliation processes.

4. **Audit and Compliance**: Limited discussion of audit trail requirements, regulatory compliance tracking, or maintaining immutable records of inventory movements.

5. **Performance Benchmarking**: No quantitative benchmarks for query performance with specific data volumes, chunk configurations, or continuous aggregate refresh rates relevant to Une Femme's scale.

## Practical Implications

**For Une Femme Supply Chain Platform Development**:

1. **Immediate Implementation Path**: Use the provided inventory_events schema and hypertable structure as foundation for inventory tracking system. The denormalized event table with foreign keys to SKU and warehouse dimensions balances normalization with query performance.

2. **Analytics Foundation**: Implement hourly and weekly continuous aggregates for DOH and depletion metrics immediately after basic event tracking operational, enabling real-time dashboard without complex aggregation queries.

3. **Chunk Interval Selection**: Start with 1-day chunks based on estimated 10,000-50,000 daily events. Monitor chunk size and query performance; adjust to 7-day intervals if storage/memory becomes bottleneck or to smaller intervals if event volume exceeds 100,000 daily.

4. **Compression Strategy**: Enable 30-day automatic compression policy. This maintains fast queries on recent 30 days (operational analytics) while compressing older data (historical trends and auditing) to 10-20% of original size.

5. **Index Prioritization**: Implement time DESC, warehouse+time, and SKU+time indexes immediately. These optimize dominant query patterns (recent events, location-specific trends, SKU depletion). BRIN indexes reduce index footprint compared to B-tree on time-ordered data.

6. **Continuous Monitoring**: Establish alerts on:
   - Chunk count (unusual growth indicates misconfigured chunk interval)
   - Compression effectiveness (80-90% reduction target)
   - Query performance on materialized views (staleness indicates refresh rate tuning needed)

7. **Deprecation Contingency**: Timeline for Postgres 17 migration (if adopted) should include evaluation of native PostgreSQL partitioning vs. TimescaleDB vs. alternative time-series solutions. Plan 12-18 month technical assessment cycle.

8. **Schema Documentation**: Maintain detailed documentation of:
   - Why inventory_events is denormalized (join performance vs. normalization tradeoff)
   - Continuous aggregate refresh frequency (hourly, weekly) and staleness tolerance
   - Chunk interval sizing rationale and review schedule
   - Compression policy (30 days) justification based on query patterns

## Open Questions & Further Research Directions

1. **Workload-Specific Performance**: What are quantitative query performance benchmarks for typical Une Femme queries (DOH trends, depletion rates, low-stock alerts) with 1M events/month, 1K+ SKUs, 10+ warehouse locations? How does performance scale to 100M events/month?

2. **Continuous Aggregate Refresh Strategy**: What refresh frequency (hourly, every 6 hours, daily) for continuous aggregates balances analytical freshness against materialization cost? How should this change based on workload characteristics?

3. **Wine Supply Chain Specifics**: How should vintage, region, varietals, and regulatory compliance attributes be integrated into the hypertable schema without denormalization explosion?

4. **Multi-Warehouse Optimization**: For geographically distributed warehouses with potential replication, how should hypertables be partitioned by both time and warehouse location? Should each location maintain local hypertables with central aggregation?

5. **Forecasting Integration**: How should predictive inventory models be integrated with the time-series fact table? Should forecasts be stored as synthetic events alongside actual movements, or maintained separately?

6. **Operator Consideration**: Should Une Femme implement continuous aggregates vs. on-demand aggregation in the application layer? What are operational complexity tradeoffs?

7. **Data Quality and Auditing**: How should data quality constraints, business rule validation, and audit trails be maintained in high-volume event insertion? What's the performance cost of comprehensive constraint validation?

8. **Long-Term Platform Evolution**: Given TimescaleDB's Postgres 17 deprecation, what's the 3-5 year evaluation timeline for migration to native Postgres partitioning, ClickHouse, or other time-series specialized solutions?
