# Spec: Demand Forecasting with Prophet

## Job to Be Done
As a supply chain planner, I need 26-week rolling demand forecasts with confidence intervals so that I can plan procurement, manage safety stock, and prepare for seasonal demand spikes (especially NYE champagne demand).

## Requirements
- Implement Prophet forecasting model for each SKU
- Configure multiplicative seasonality for champagne's 7.5x NYE spikes
- Define holiday calendar (NYE, Valentine's, Mother's Day, Thanksgiving)
- Generate 26-week rolling forecasts with weekly retraining
- Calculate prediction intervals (80% and 95% confidence)
- Support external regressors (price, promotions) in Phase 2
- Target MAPE <12% on 26-week horizon

## Acceptance Criteria
- [ ] Prophet model trains successfully on 2+ years historical data
- [ ] Multiplicative seasonality captures holiday spikes
- [ ] Holiday effects modeled for NYE, Valentine's, Mother's Day, Thanksgiving
- [ ] 26-week forecast generated with point estimates and intervals
- [ ] Weekly retraining pipeline executes automatically
- [ ] Cross-validation MAPE <12% on held-out data
- [ ] Forecasts stored in database for dashboard consumption

## Test Cases
| Input | Expected Output |
|-------|-----------------|
| 2 years historical data, UFBub250 | Model trains in <60 seconds |
| Forecast for Dec 31 (NYE) | 5-8x baseline demand predicted |
| Forecast for Feb 14 (Valentine's) | 2-3x baseline demand predicted |
| 26-week forecast request | 26 weekly predictions with intervals |
| Cross-validation (90-day horizon) | MAPE <12% |

## Technical Notes
- Prophet Configuration:
  - growth='linear'
  - seasonality_mode='multiplicative' (critical for champagne)
  - changepoint_prior_scale=0.05
  - yearly_seasonality=True
  - weekly_seasonality=True
- Minimum training data: 2 years (104 weeks)
- Retraining frequency: Weekly (every Monday)
- Holiday windows: 7 days before, 1 day after

## Holiday Calendar

```python
holidays = pd.DataFrame({
    'holiday': 'NYE',
    'ds': pd.date_range('2020-12-31', '2028-12-31', freq='YE'),
    'lower_window': -7,
    'upper_window': 1
})

# Additional holidays
valentines = pd.DataFrame({
    'holiday': 'Valentines',
    'ds': pd.date_range('2020-02-14', '2028-02-14', freq='YS') + pd.DateOffset(months=1, days=13),
    'lower_window': -7,
    'upper_window': 0
})

mothers_day = # Second Sunday of May
thanksgiving = # Fourth Thursday of November
```

## Model Training Pipeline

```python
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics

def train_forecast_model(df: pd.DataFrame, sku: str) -> Prophet:
    """
    Train Prophet model for a single SKU.
    df must have columns: ds (date), y (quantity)
    """
    model = Prophet(
        growth='linear',
        seasonality_mode='multiplicative',
        changepoint_prior_scale=0.05,
        yearly_seasonality=True,
        weekly_seasonality=True
    )

    model.add_country_holidays(country_name='US')
    # Add custom holidays

    model.fit(df)
    return model

def generate_forecast(model: Prophet, periods: int = 26) -> pd.DataFrame:
    """Generate 26-week forecast with intervals"""
    future = model.make_future_dataframe(periods=periods, freq='W')
    forecast = model.predict(future)
    return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
```

## Safety Stock Calculation

```python
def calculate_safety_stock(forecast: pd.DataFrame, service_level: float = 0.95) -> float:
    """
    Calculate safety stock from forecast intervals.

    For 95% service level:
    safety_stock = yhat_upper_95 - yhat
    """
    # Prophet default is 80% interval, need to regenerate for 95%
    return forecast['yhat_upper'] - forecast['yhat']
```

## Source Reference
- [[prophet-forecasting]] - Complete Prophet implementation guide
- Research synthesis: "26-Week Rolling Forecast with Prophet" section
