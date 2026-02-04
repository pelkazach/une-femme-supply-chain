-- Stock-Out Risk Alert: Triggers when DOH_T30 < 14 days
-- Alert fires when any SKU has less than 14 days of inventory on hand
--
-- Query Name: Stock-Out Risk Alert
-- Description: Returns SKUs at critical stock-out risk (DOH_T30 < 14 days).
--              Used for Redash alert configuration.
-- Alert Condition: Fires when query returns rows (count > 0)

SELECT
    p.sku,
    p.name as product_name,
    w.name as warehouse,
    m.current_inventory as on_hand,
    m.depletions_30d,
    ROUND(m.doh_t30, 1) as doh_t30,
    14 as threshold_days,
    ROUND(14 - m.doh_t30, 1) as days_below_threshold,
    m.calculated_at
FROM mv_doh_metrics m
JOIN products p ON m.sku_id = p.id
JOIN warehouses w ON m.warehouse_id = w.id
WHERE
    m.doh_t30 IS NOT NULL
    AND m.doh_t30 < 14
ORDER BY
    m.doh_t30 ASC;
