-- Forecast Overview: 26-week demand forecasts with confidence intervals
-- Shows weekly point estimates (yhat) with lower/upper bounds for all SKUs
-- Chart should display as line chart with confidence bands
SELECT
    p.sku,
    p.name as product_name,
    f.forecast_date,
    ROUND(f.yhat::NUMERIC, 0) as forecast,
    ROUND(f.yhat_lower::NUMERIC, 0) as lower_bound,
    ROUND(f.yhat_upper::NUMERIC, 0) as upper_bound,
    ROUND((f.interval_width * 100)::NUMERIC, 0) as confidence_pct,
    f.model_trained_at,
    f.mape
FROM forecasts f
JOIN products p ON f.sku_id = p.id
WHERE f.forecast_date >= NOW()
  AND f.model_trained_at = (
    SELECT MAX(model_trained_at)
    FROM forecasts f2
    WHERE f2.sku_id = f.sku_id
  )
ORDER BY p.sku, f.forecast_date;
