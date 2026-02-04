# Spec: Database Schema & Infrastructure

## Job to Be Done
As a supply chain operator, I need a database that stores inventory events, calculates real-time metrics (DOH, depletion rates), and supports multi-tenant access so that I can make data-driven decisions about procurement and inventory management.

## Requirements
- Deploy Supabase project with PostgreSQL 15 (required for TimescaleDB compatibility)
- Enable TimescaleDB extension for time-series data
- Create core tables: products, warehouses, distributors, inventory_events
- Implement hypertables for time-series inventory tracking
- Configure continuous aggregates for DOH_T30 and DOH_T90 metrics
- Set up Row Level Security (RLS) for multi-tenant data isolation
- Create views for Une Femme's existing metrics (A30_Ship:A30_Dep, etc.)

## Acceptance Criteria
- [ ] Supabase project deployed with TimescaleDB extension enabled
- [ ] `products` table exists with SKU fields (UFBub250, UFRos250, UFRed250, UFCha250)
- [ ] `inventory_events` hypertable created with time-based partitioning
- [ ] Continuous aggregate `doh_t30` returns 30-day rolling days-on-hand
- [ ] Continuous aggregate `doh_t90` returns 90-day rolling days-on-hand
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
- Use PostgreSQL 15 (TimescaleDB deprecated in v17)
- Chunk interval: 1 day for inventory_events
- Compression policy: 30 days
- Supabase Pro plan ($25/month) sufficient for MVP
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

-- Time-series inventory events (hypertable)
CREATE TABLE inventory_events (
  time TIMESTAMPTZ NOT NULL,
  sku_id UUID NOT NULL REFERENCES products(id),
  warehouse_id UUID NOT NULL REFERENCES warehouses(id),
  distributor_id UUID REFERENCES distributors(id),
  event_type VARCHAR(20) NOT NULL, -- 'shipment', 'depletion', 'adjustment'
  quantity INTEGER NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('inventory_events', 'time');
```

## Source Reference
- [[supabase-platform]] - Supabase configuration and RLS patterns
- [[timescaledb-schema]] - Hypertable and continuous aggregate design
