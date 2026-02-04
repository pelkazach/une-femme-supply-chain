-- Shipment:Depletion Ratio: Supply/demand balance metrics for all SKUs
-- Shows A30_Ship:A30_Dep, A90_Ship:A90_Dep ratios with status indicators
-- Ratio > 1 means more shipments than depletions (building inventory)
-- Ratio < 1 means more depletions than shipments (drawing down inventory)
--
-- Query Name: Shipment:Depletion Ratio
-- Description: Supply/demand balance ratios for all SKUs by warehouse.
--              Shows A30 and A90 ratios with balance status (OVERSUPPLY/UNDERSUPPLY/BALANCED).
-- Auto-refresh: 5 minutes

SELECT
    p.sku,
    p.name as product_name,
    w.name as warehouse,
    m.shipments_30d,
    m.depletions_30d,
    m.shipments_90d,
    m.depletions_90d,
    m.a30_ship_dep_ratio,
    m.a90_ship_dep_ratio,
    CASE
        WHEN m.a30_ship_dep_ratio IS NULL THEN 'NO SALES'
        WHEN m.a30_ship_dep_ratio > 2.0 THEN 'OVERSUPPLY'
        WHEN m.a30_ship_dep_ratio < 0.5 THEN 'UNDERSUPPLY'
        ELSE 'BALANCED'
    END as status_30d,
    CASE
        WHEN m.a90_ship_dep_ratio IS NULL THEN 'NO SALES'
        WHEN m.a90_ship_dep_ratio > 2.0 THEN 'OVERSUPPLY'
        WHEN m.a90_ship_dep_ratio < 0.5 THEN 'UNDERSUPPLY'
        ELSE 'BALANCED'
    END as status_90d,
    m.calculated_at
FROM mv_doh_metrics m
JOIN products p ON m.sku_id = p.id
JOIN warehouses w ON m.warehouse_id = w.id
ORDER BY
    CASE
        WHEN m.a30_ship_dep_ratio IS NULL THEN 2
        WHEN m.a30_ship_dep_ratio < 0.5 THEN 0  -- UNDERSUPPLY first (most critical)
        WHEN m.a30_ship_dep_ratio > 2.0 THEN 1  -- OVERSUPPLY second
        ELSE 3  -- BALANCED last
    END,
    m.a30_ship_dep_ratio ASC NULLS LAST;
