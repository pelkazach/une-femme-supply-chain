-- DOH by SKU: Aggregated DOH metrics across all warehouses
-- Use this query for a summary view by product
--
-- Query Name: DOH by SKU
-- Description: Days on Hand metrics aggregated by SKU across all warehouses.
-- Auto-refresh: 5 minutes

SELECT
    p.sku,
    p.name as product_name,
    SUM(m.current_inventory) as total_on_hand,
    SUM(m.depletions_30d) as total_depletions_30d,
    SUM(m.depletions_90d) as total_depletions_90d,
    CASE
        WHEN SUM(m.depletions_30d) > 0
        THEN ROUND(SUM(m.current_inventory)::NUMERIC / (SUM(m.depletions_30d)::NUMERIC / 30), 1)
        ELSE NULL
    END as doh_t30,
    CASE
        WHEN SUM(m.depletions_90d) > 0
        THEN ROUND(SUM(m.current_inventory)::NUMERIC / (SUM(m.depletions_90d)::NUMERIC / 90), 1)
        ELSE NULL
    END as doh_t90,
    CASE
        WHEN SUM(m.depletions_30d) = 0 THEN 'NO SALES'
        WHEN SUM(m.current_inventory)::NUMERIC / (SUM(m.depletions_30d)::NUMERIC / 30) < 14 THEN 'CRITICAL'
        WHEN SUM(m.current_inventory)::NUMERIC / (SUM(m.depletions_30d)::NUMERIC / 30) < 30 THEN 'WARNING'
        ELSE 'OK'
    END as status
FROM mv_doh_metrics m
JOIN products p ON m.sku_id = p.id
GROUP BY p.sku, p.name
ORDER BY
    CASE
        WHEN SUM(m.depletions_30d) = 0 THEN 2
        WHEN SUM(m.current_inventory)::NUMERIC / (SUM(m.depletions_30d)::NUMERIC / 30) < 14 THEN 0
        WHEN SUM(m.current_inventory)::NUMERIC / (SUM(m.depletions_30d)::NUMERIC / 30) < 30 THEN 1
        ELSE 3
    END,
    doh_t30 ASC NULLS LAST;
