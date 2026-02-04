# Spec: Dashboard & Alerting System

## Job to Be Done
As a supply chain operator, I need real-time dashboards showing inventory KPIs with threshold-based alerts so that I'm immediately notified of stock-out risks, unusual depletion patterns, or supply chain anomalies.

## Requirements
- Deploy Redash for operational KPI dashboards
- Connect Redash to Supabase PostgreSQL
- Create dashboard widgets for core metrics (DOH, depletion rates, ratios)
- Configure threshold-based alerts for stock-out scenarios
- Set up Slack/email notifications for alerts
- Support filtering by SKU, distributor segment, date range
- Implement auto-refresh (1-minute minimum for Redash)

## Acceptance Criteria
- [ ] Redash deployed and accessible via web
- [ ] Database connection to Supabase established
- [ ] Dashboard shows DOH_T30, DOH_T90 for all 4 SKUs
- [ ] Dashboard shows shipment:depletion ratios
- [ ] Alert triggers when DOH_T30 < 14 days
- [ ] Alert triggers when A30:A90_Dep > 1.3 (rapid demand acceleration)
- [ ] Slack notification sent when alert fires
- [ ] Email notification sent when alert fires
- [ ] Dashboard refreshes automatically every 5 minutes

## Test Cases
| Input | Expected Output |
|-------|-----------------|
| DOH_T30 drops to 10 days | Alert fires, Slack message sent |
| DOH_T30 at 30 days | No alert |
| A30:A90_Dep = 1.5 (accelerating) | Alert: "Demand accelerating for [SKU]" |
| Manual refresh click | Dashboard updates with latest data |
| Filter by "Georgia (RNDC)" | Only Georgia distributor data shown |

## Technical Notes
- Redash minimum refresh: 1 minute (architectural constraint)
- For sub-minute latency, use Supabase real-time subscriptions
- Webhook integration available for custom alert routing
- Consider Retool for mobile dashboards (Phase 2)
- Elasticsearch integration possible for event-based updates

## Dashboard Queries

### DOH Overview Query
```sql
WITH current_inventory AS (
  SELECT sku_id, SUM(quantity) as on_hand
  FROM inventory_events
  WHERE event_type = 'adjustment'
  GROUP BY sku_id
),
depletion_30d AS (
  SELECT sku_id, SUM(quantity) as depleted
  FROM inventory_events
  WHERE event_type = 'depletion'
    AND time > NOW() - INTERVAL '30 days'
  GROUP BY sku_id
)
SELECT
  p.sku,
  ci.on_hand,
  d.depleted as depletion_30d,
  ROUND(ci.on_hand / NULLIF(d.depleted / 30.0, 0), 1) as doh_t30
FROM products p
JOIN current_inventory ci ON p.id = ci.sku_id
JOIN depletion_30d d ON p.id = d.sku_id
ORDER BY doh_t30 ASC;
```

### Stock-Out Alert Query
```sql
-- Alert when DOH < 14 days AND lead time > remaining days
SELECT
  p.sku,
  doh_t30,
  14 as lead_time_days,
  CASE WHEN doh_t30 < 14 THEN 'CRITICAL' ELSE 'OK' END as status
FROM (
  -- DOH calculation subquery
) metrics
JOIN products p ON metrics.sku_id = p.id
WHERE doh_t30 < 14;
```

## Alert Configuration

| Alert Name | Condition | Severity | Channel |
|------------|-----------|----------|---------|
| Stock-Out Risk | DOH_T30 < 14 | Critical | Slack + Email |
| Low Stock Warning | DOH_T30 < 30 | Warning | Slack |
| Demand Spike | A30:A90_Dep > 1.3 | Warning | Slack |
| Supply Imbalance | A30_Ship:A30_Dep > 2.0 | Info | Email |

## Source Reference
- [[dashboard-comparison]] - Redash vs alternatives analysis
- Research synthesis: "Dashboard & Visualization" section
