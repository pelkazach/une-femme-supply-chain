# Spec: Database Schema & Infrastructure

## Job to Be Done
As a supply chain operator, I need a database that stores inventory events, calculates real-time metrics (DOH, depletion rates), and supports multi-tenant access so that I can make data-driven decisions about procurement and inventory management.

## Requirements
- Deploy Railway project with PostgreSQL 17
- Create core tables: products, warehouses, distributors, inventory_events
- Use BRIN indexes for time-series query performance (TimescaleDB not available on Railway)
- Create materialized views for DOH_T30 and DOH_T90 metrics (instead of continuous aggregates)
- Set up Row Level Security (RLS) for multi-tenant data isolation
- Create views for Une Femme's existing metrics (A30_Ship:A30_Dep, etc.)

## Acceptance Criteria
- [ ] Railway project deployed with PostgreSQL database
- [ ] `products` table exists with SKU fields (UFBub250, UFRos250, UFRed250, UFCha250)
- [ ] `inventory_events` table created with BRIN index on time column
- [ ] Materialized view `doh_t30_mv` returns 30-day rolling days-on-hand
- [ ] Materialized view `doh_t90_mv` returns 90-day rolling days-on-hand
- [ ] RLS policies prevent cross-tenant data access
- [ ] Sample data inserted and queries return expected results

## Test Cases
| Input | Expected Output |
|-------|-----------------|
| Insert 1000 units for UFBub250 | inventory_events row created with timestamp |
| Query DOH_T30 with 100 units/day depletion | Returns ~10 days |
| Query as unauthorized user | RLS blocks access, returns empty |
| Query shipment:depletion ratio | Returns calculated A30_Ship:A30_Dep |

## Technical Notes
- Using PostgreSQL 17 on Railway (TimescaleDB not available)
- BRIN index on `time` column for efficient range queries
- Materialized views with scheduled refresh (instead of continuous aggregates)
- Railway Hobby plan sufficient for MVP
- Schema must support 4 core SKUs initially, scalable to 50+

## Database Schema

```sql
-- Core tables
CREATE TABLE products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sku VARCHAR(20) UNIQUE NOT NULL,
  name VARCHAR(255) NOT NULL,
  category VARCHAR(50),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE warehouses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  code VARCHAR(10) UNIQUE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE distributors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  segment VARCHAR(50), -- 'RNDC', 'Reyes', 'Non-RNDC'
  state VARCHAR(2),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Time-series inventory events (standard table with BRIN index)
CREATE TABLE inventory_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  time TIMESTAMPTZ NOT NULL,
  sku_id UUID NOT NULL REFERENCES products(id),
  warehouse_id UUID NOT NULL REFERENCES warehouses(id),
  distributor_id UUID REFERENCES distributors(id),
  event_type VARCHAR(20) NOT NULL, -- 'shipment', 'depletion', 'adjustment'
  quantity INTEGER NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- BRIN index for efficient time-range queries (replaces hypertable)
CREATE INDEX idx_inventory_events_time_brin ON inventory_events USING BRIN (time);

-- Materialized view for 30-day DOH (replaces continuous aggregate)
CREATE MATERIALIZED VIEW doh_t30_mv AS
SELECT
  sku_id,
  warehouse_id,
  SUM(CASE WHEN event_type = 'shipment' THEN quantity ELSE 0 END) as inventory,
  SUM(CASE WHEN event_type = 'depletion' THEN quantity ELSE 0 END) as depletions_30d,
  CASE
    WHEN SUM(CASE WHEN event_type = 'depletion' THEN quantity ELSE 0 END) > 0
    THEN (SUM(CASE WHEN event_type = 'shipment' THEN quantity ELSE 0 END)::float /
          (SUM(CASE WHEN event_type = 'depletion' THEN quantity ELSE 0 END)::float / 30))
    ELSE NULL
  END as days_on_hand
FROM inventory_events
WHERE time > NOW() - INTERVAL '30 days'
GROUP BY sku_id, warehouse_id;
```

## Source Reference
- Railway PostgreSQL documentation

## Revision History
- 2026-02-03: Changed from Supabase/TimescaleDB to Railway/PostgreSQL 17 - discovered during Task 1.1.2 that TimescaleDB is not available on Railway. Updated to use BRIN indexes instead of hypertables, materialized views instead of continuous aggregates.
