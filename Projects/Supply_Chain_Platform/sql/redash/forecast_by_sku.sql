-- Forecast by SKU: Weekly demand forecast for a single SKU
-- Use with SKU parameter filter in Redash
-- Designed for time series chart with confidence bands
SELECT
    f.forecast_date,
    ROUND(f.yhat::NUMERIC, 0) as forecast,
    ROUND(f.yhat_lower::NUMERIC, 0) as lower_bound,
    ROUND(f.yhat_upper::NUMERIC, 0) as upper_bound,
    ROUND((f.yhat_upper - f.yhat_lower)::NUMERIC, 0) as band_width,
    f.mape as model_mape
FROM forecasts f
JOIN products p ON f.sku_id = p.id
WHERE p.sku = '{{ sku }}'
  AND f.forecast_date >= NOW()
  AND f.model_trained_at = (
    SELECT MAX(model_trained_at)
    FROM forecasts f2
    WHERE f2.sku_id = f.sku_id
  )
ORDER BY f.forecast_date;
