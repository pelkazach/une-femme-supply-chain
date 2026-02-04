-- DOH Overview (Direct Query): Days on Hand metrics calculated from inventory_events
-- Use this query if materialized views haven't been refreshed
--
-- Query Name: DOH Overview (Direct)
-- Description: Real-time DOH calculation from inventory_events table.
--              More expensive but always up-to-date.
-- Auto-refresh: 5 minutes

WITH current_inventory AS (
    -- Calculate current inventory for each SKU/warehouse
    -- Snapshots represent point-in-time inventory levels
    -- Depletions are subtracted, shipments added
    SELECT
        sku_id,
        warehouse_id,
        SUM(
            CASE
                WHEN event_type = 'snapshot' THEN quantity
                WHEN event_type = 'shipment' THEN quantity
                WHEN event_type = 'depletion' THEN -ABS(quantity)
                WHEN event_type = 'adjustment' THEN quantity
                ELSE 0
            END
        ) AS on_hand
    FROM inventory_events
    GROUP BY sku_id, warehouse_id
),
depletion_30d AS (
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
depletion_90d AS (
    -- Sum depletions over last 90 days
    SELECT
        sku_id,
        warehouse_id,
        COALESCE(SUM(ABS(quantity)), 0) as depleted
    FROM inventory_events
    WHERE event_type = 'depletion'
      AND time > NOW() - INTERVAL '90 days'
    GROUP BY sku_id, warehouse_id
)
SELECT
    p.sku,
    p.name as product_name,
    w.name as warehouse,
    ci.on_hand,
    d30.depleted as depletions_30d,
    d90.depleted as depletions_90d,
    CASE
        WHEN COALESCE(d30.depleted, 0) > 0
        THEN ROUND(ci.on_hand::NUMERIC / (d30.depleted::NUMERIC / 30), 1)
        ELSE NULL
    END as doh_t30,
    CASE
        WHEN COALESCE(d90.depleted, 0) > 0
        THEN ROUND(ci.on_hand::NUMERIC / (d90.depleted::NUMERIC / 90), 1)
        ELSE NULL
    END as doh_t90,
    CASE
        WHEN COALESCE(d30.depleted, 0) = 0 THEN 'NO SALES'
        WHEN ci.on_hand::NUMERIC / (d30.depleted::NUMERIC / 30) < 14 THEN 'CRITICAL'
        WHEN ci.on_hand::NUMERIC / (d30.depleted::NUMERIC / 30) < 30 THEN 'WARNING'
        ELSE 'OK'
    END as status,
    NOW() as calculated_at
FROM current_inventory ci
JOIN products p ON ci.sku_id = p.id
JOIN warehouses w ON ci.warehouse_id = w.id
LEFT JOIN depletion_30d d30 ON ci.sku_id = d30.sku_id AND ci.warehouse_id = d30.warehouse_id
LEFT JOIN depletion_90d d90 ON ci.sku_id = d90.sku_id AND ci.warehouse_id = d90.warehouse_id
ORDER BY
    CASE
        WHEN COALESCE(d30.depleted, 0) = 0 THEN 2
        WHEN ci.on_hand::NUMERIC / (d30.depleted::NUMERIC / 30) < 14 THEN 0
        WHEN ci.on_hand::NUMERIC / (d30.depleted::NUMERIC / 30) < 30 THEN 1
        ELSE 3
    END,
    doh_t30 ASC NULLS LAST;
