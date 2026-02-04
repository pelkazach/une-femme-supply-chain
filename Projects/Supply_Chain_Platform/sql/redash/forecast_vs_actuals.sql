-- Forecast vs Actuals: Compare historical forecasts against actual depletions
-- Useful for model evaluation and visualization
-- Shows both lines on same chart for comparison
WITH actuals AS (
    SELECT
        sku_id,
        DATE_TRUNC('week', time) as week_date,
        SUM(ABS(quantity)) as actual_quantity
    FROM inventory_events
    WHERE event_type = 'depletion'
      AND time >= NOW() - INTERVAL '26 weeks'
    GROUP BY sku_id, DATE_TRUNC('week', time)
),
forecast_data AS (
    SELECT
        sku_id,
        DATE_TRUNC('week', forecast_date) as week_date,
        AVG(yhat) as forecast,
        AVG(yhat_lower) as lower_bound,
        AVG(yhat_upper) as upper_bound
    FROM forecasts
    WHERE forecast_date < NOW()
      AND forecast_date >= NOW() - INTERVAL '26 weeks'
    GROUP BY sku_id, DATE_TRUNC('week', forecast_date)
)
SELECT
    p.sku,
    p.name as product_name,
    COALESCE(f.week_date, a.week_date) as week,
    ROUND(a.actual_quantity::NUMERIC, 0) as actual,
    ROUND(f.forecast::NUMERIC, 0) as forecast,
    ROUND(f.lower_bound::NUMERIC, 0) as lower_bound,
    ROUND(f.upper_bound::NUMERIC, 0) as upper_bound,
    CASE
        WHEN a.actual_quantity IS NOT NULL AND f.forecast IS NOT NULL
        THEN ROUND(ABS(a.actual_quantity - f.forecast) / NULLIF(a.actual_quantity, 0) * 100, 1)
        ELSE NULL
    END as error_pct
FROM products p
LEFT JOIN forecast_data f ON p.id = f.sku_id
LEFT JOIN actuals a ON p.id = a.sku_id AND f.week_date = a.week_date
WHERE f.week_date IS NOT NULL OR a.week_date IS NOT NULL
ORDER BY p.sku, week;
