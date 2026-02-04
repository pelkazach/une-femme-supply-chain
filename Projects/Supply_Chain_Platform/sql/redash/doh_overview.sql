-- DOH Overview: Days on Hand metrics for all SKUs
-- Shows current inventory, 30-day and 90-day DOH, plus status indicators
--
-- Query Name: DOH Overview
-- Description: Days on Hand overview for all SKUs by warehouse.
--              Shows DOH_T30, DOH_T90, and status indicators (CRITICAL/WARNING/OK).
-- Auto-refresh: 5 minutes

SELECT
    p.sku,
    p.name as product_name,
    w.name as warehouse,
    m.current_inventory as on_hand,
    m.depletions_30d,
    m.depletions_90d,
    m.doh_t30,
    m.doh_t90,
    CASE
        WHEN m.doh_t30 IS NULL THEN 'NO SALES'
        WHEN m.doh_t30 < 14 THEN 'CRITICAL'
        WHEN m.doh_t30 < 30 THEN 'WARNING'
        ELSE 'OK'
    END as status,
    m.calculated_at
FROM mv_doh_metrics m
JOIN products p ON m.sku_id = p.id
JOIN warehouses w ON m.warehouse_id = w.id
ORDER BY
    CASE
        WHEN m.doh_t30 IS NULL THEN 2
        WHEN m.doh_t30 < 14 THEN 0
        WHEN m.doh_t30 < 30 THEN 1
        ELSE 3
    END,
    m.doh_t30 ASC NULLS LAST;
