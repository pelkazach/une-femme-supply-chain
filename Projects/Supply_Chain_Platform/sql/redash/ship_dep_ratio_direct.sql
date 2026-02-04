-- Shipment:Depletion Ratio (Direct Query): Real-time supply/demand balance metrics
-- Use this query if materialized views haven't been refreshed
--
-- Query Name: Shipment:Depletion Ratio (Direct)
-- Description: Real-time supply/demand balance calculation from inventory_events table.
--              More expensive but always up-to-date.
-- Auto-refresh: 5 minutes

WITH shipments_30d AS (
    -- Sum shipments over last 30 days
    SELECT
        sku_id,
        warehouse_id,
        COALESCE(SUM(quantity), 0) as shipped
    FROM inventory_events
    WHERE event_type = 'shipment'
      AND time > NOW() - INTERVAL '30 days'
    GROUP BY sku_id, warehouse_id
),
depletions_30d AS (
    -- Sum depletions over last 30 days
    SELECT
        sku_id,
        warehouse_id,
        COALESCE(SUM(ABS(quantity)), 0) as depleted
    FROM inventory_events
    WHERE event_type = 'depletion'
      AND time > NOW() - INTERVAL '30 days'
    GROUP BY sku_id, warehouse_id
),
shipments_90d AS (
    -- Sum shipments over last 90 days
    SELECT
        sku_id,
        warehouse_id,
        COALESCE(SUM(quantity), 0) as shipped
    FROM inventory_events
    WHERE event_type = 'shipment'
      AND time > NOW() - INTERVAL '90 days'
    GROUP BY sku_id, warehouse_id
),
depletions_90d AS (
    -- Sum depletions over last 90 days
    SELECT
        sku_id,
        warehouse_id,
        COALESCE(SUM(ABS(quantity)), 0) as depleted
    FROM inventory_events
    WHERE event_type = 'depletion'
      AND time > NOW() - INTERVAL '90 days'
    GROUP BY sku_id, warehouse_id
),
all_sku_warehouse AS (
    -- Get all unique SKU/warehouse combinations from all CTEs
    SELECT DISTINCT sku_id, warehouse_id FROM shipments_30d
    UNION
    SELECT DISTINCT sku_id, warehouse_id FROM depletions_30d
    UNION
    SELECT DISTINCT sku_id, warehouse_id FROM shipments_90d
    UNION
    SELECT DISTINCT sku_id, warehouse_id FROM depletions_90d
)
SELECT
    p.sku,
    p.name as product_name,
    w.name as warehouse,
    COALESCE(s30.shipped, 0) as shipments_30d,
    COALESCE(d30.depleted, 0) as depletions_30d,
    COALESCE(s90.shipped, 0) as shipments_90d,
    COALESCE(d90.depleted, 0) as depletions_90d,
    CASE
        WHEN COALESCE(d30.depleted, 0) > 0
        THEN ROUND(COALESCE(s30.shipped, 0)::NUMERIC / d30.depleted::NUMERIC, 2)
        ELSE NULL
    END as a30_ship_dep_ratio,
    CASE
        WHEN COALESCE(d90.depleted, 0) > 0
        THEN ROUND(COALESCE(s90.shipped, 0)::NUMERIC / d90.depleted::NUMERIC, 2)
        ELSE NULL
    END as a90_ship_dep_ratio,
    CASE
        WHEN COALESCE(d30.depleted, 0) = 0 THEN 'NO SALES'
        WHEN COALESCE(s30.shipped, 0)::NUMERIC / d30.depleted::NUMERIC > 2.0 THEN 'OVERSUPPLY'
        WHEN COALESCE(s30.shipped, 0)::NUMERIC / d30.depleted::NUMERIC < 0.5 THEN 'UNDERSUPPLY'
        ELSE 'BALANCED'
    END as status_30d,
    CASE
        WHEN COALESCE(d90.depleted, 0) = 0 THEN 'NO SALES'
        WHEN COALESCE(s90.shipped, 0)::NUMERIC / d90.depleted::NUMERIC > 2.0 THEN 'OVERSUPPLY'
        WHEN COALESCE(s90.shipped, 0)::NUMERIC / d90.depleted::NUMERIC < 0.5 THEN 'UNDERSUPPLY'
        ELSE 'BALANCED'
    END as status_90d,
    NOW() as calculated_at
FROM all_sku_warehouse a
JOIN products p ON a.sku_id = p.id
JOIN warehouses w ON a.warehouse_id = w.id
LEFT JOIN shipments_30d s30 ON a.sku_id = s30.sku_id AND a.warehouse_id = s30.warehouse_id
LEFT JOIN depletions_30d d30 ON a.sku_id = d30.sku_id AND a.warehouse_id = d30.warehouse_id
LEFT JOIN shipments_90d s90 ON a.sku_id = s90.sku_id AND a.warehouse_id = s90.warehouse_id
LEFT JOIN depletions_90d d90 ON a.sku_id = d90.sku_id AND a.warehouse_id = d90.warehouse_id
ORDER BY
    CASE
        WHEN COALESCE(d30.depleted, 0) = 0 THEN 2
        WHEN COALESCE(s30.shipped, 0)::NUMERIC / d30.depleted::NUMERIC < 0.5 THEN 0
        WHEN COALESCE(s30.shipped, 0)::NUMERIC / d30.depleted::NUMERIC > 2.0 THEN 1
        ELSE 3
    END,
    a30_ship_dep_ratio ASC NULLS LAST;
