-- Shipment:Depletion Ratio by SKU: Aggregated supply/demand balance across all warehouses
-- Shows A30_Ship:A30_Dep, A90_Ship:A90_Dep ratios aggregated by product
--
-- Query Name: Shipment:Depletion Ratio by SKU
-- Description: Supply/demand balance ratios aggregated by SKU across all warehouses.
-- Auto-refresh: 5 minutes

SELECT
    p.sku,
    p.name as product_name,
    SUM(m.shipments_30d) as total_shipments_30d,
    SUM(m.depletions_30d) as total_depletions_30d,
    SUM(m.shipments_90d) as total_shipments_90d,
    SUM(m.depletions_90d) as total_depletions_90d,
    CASE
        WHEN SUM(m.depletions_30d) > 0
        THEN ROUND(SUM(m.shipments_30d)::NUMERIC / SUM(m.depletions_30d)::NUMERIC, 2)
        ELSE NULL
    END as a30_ship_dep_ratio,
    CASE
        WHEN SUM(m.depletions_90d) > 0
        THEN ROUND(SUM(m.shipments_90d)::NUMERIC / SUM(m.depletions_90d)::NUMERIC, 2)
        ELSE NULL
    END as a90_ship_dep_ratio,
    CASE
        WHEN SUM(m.depletions_30d) = 0 THEN 'NO SALES'
        WHEN SUM(m.shipments_30d)::NUMERIC / SUM(m.depletions_30d)::NUMERIC > 2.0 THEN 'OVERSUPPLY'
        WHEN SUM(m.shipments_30d)::NUMERIC / SUM(m.depletions_30d)::NUMERIC < 0.5 THEN 'UNDERSUPPLY'
        ELSE 'BALANCED'
    END as status_30d,
    CASE
        WHEN SUM(m.depletions_90d) = 0 THEN 'NO SALES'
        WHEN SUM(m.shipments_90d)::NUMERIC / SUM(m.depletions_90d)::NUMERIC > 2.0 THEN 'OVERSUPPLY'
        WHEN SUM(m.shipments_90d)::NUMERIC / SUM(m.depletions_90d)::NUMERIC < 0.5 THEN 'UNDERSUPPLY'
        ELSE 'BALANCED'
    END as status_90d
FROM mv_doh_metrics m
JOIN products p ON m.sku_id = p.id
GROUP BY p.sku, p.name
ORDER BY
    CASE
        WHEN SUM(m.depletions_30d) = 0 THEN 2
        WHEN SUM(m.shipments_30d)::NUMERIC / SUM(m.depletions_30d)::NUMERIC < 0.5 THEN 0
        WHEN SUM(m.shipments_30d)::NUMERIC / SUM(m.depletions_30d)::NUMERIC > 2.0 THEN 1
        ELSE 3
    END,
    a30_ship_dep_ratio ASC NULLS LAST;
