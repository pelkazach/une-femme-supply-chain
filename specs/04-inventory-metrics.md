# Spec: Inventory Metrics Calculation

## Job to Be Done
As a supply chain analyst, I need calculated metrics (DOH, shipment/depletion ratios, velocity trends) so that I can identify inventory risks, forecast needs, and make informed procurement decisions.

## Requirements
- Calculate DOH_T30: Days on Hand based on trailing 30-day depletion rate
- Calculate DOH_T90: Days on Hand based on trailing 90-day depletion rate
- Calculate A30_Ship:A30_Dep: Ratio of 30-day shipments to 30-day depletions
- Calculate A90_Ship:A90_Dep: Ratio of 90-day shipments to 90-day depletions
- Calculate A30:A90_Ship: Ratio of 30-day to 90-day shipments (velocity trend)
- Calculate A30:A90_Dep: Ratio of 30-day to 90-day depletions (velocity trend)
- Support filtering by SKU, warehouse, distributor segment
- Implement as TimescaleDB continuous aggregates for performance

## Acceptance Criteria
- [ ] DOH_T30 calculation matches Excel formula within 1% variance
- [ ] DOH_T90 calculation matches Excel formula within 1% variance
- [ ] Shipment:Depletion ratios calculated correctly
- [ ] Velocity trend ratios identify acceleration/deceleration
- [ ] Metrics queryable by SKU (UFBub250, UFRos250, UFRed250, UFCha250)
- [ ] Metrics queryable by distributor segment
- [ ] Query performance <100ms for single SKU metrics
- [ ] Historical metrics available for trend analysis

## Test Cases
| Input | Expected Output |
|-------|-----------------|
| 1000 units on hand, 100/day depletion (30d) | DOH_T30 = 10 days |
| 1000 units on hand, 50/day depletion (90d) | DOH_T90 = 20 days |
| 300 shipped, 200 depleted (30d) | A30_Ship:A30_Dep = 1.5 |
| 30d velocity 100/day, 90d velocity 80/day | A30:A90_Dep = 1.25 (accelerating) |
| Zero depletion | Handle gracefully (NULL or infinity flag) |

## Technical Notes
- Use TimescaleDB continuous aggregates for performance
- Refresh aggregates on 15-minute interval
- Handle edge cases: zero depletion, missing data periods
- Align with existing Excel workbook calculations
- Support real-time and historical queries

## Metric Definitions

```sql
-- DOH_T30: Days on Hand (30-day basis)
DOH_T30 = current_inventory / (SUM(depletion_last_30_days) / 30)

-- DOH_T90: Days on Hand (90-day basis)
DOH_T90 = current_inventory / (SUM(depletion_last_90_days) / 90)

-- Shipment:Depletion Ratio (30-day)
A30_Ship_Dep = SUM(shipments_last_30_days) / SUM(depletions_last_30_days)

-- Velocity Trend (Depletion)
A30_A90_Dep = (SUM(dep_30d) / 30) / (SUM(dep_90d) / 90)
-- >1 = accelerating demand, <1 = decelerating demand
```

## Continuous Aggregate Example

```sql
CREATE MATERIALIZED VIEW metrics_30d
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 day', time) AS day,
  sku_id,
  warehouse_id,
  SUM(CASE WHEN event_type = 'shipment' THEN quantity ELSE 0 END) as shipments,
  SUM(CASE WHEN event_type = 'depletion' THEN quantity ELSE 0 END) as depletions
FROM inventory_events
GROUP BY 1, 2, 3;
```

## Source Reference
- [[timescaledb-schema]] - Continuous aggregate patterns
- Research synthesis: "Core Metrics Compatibility" section
