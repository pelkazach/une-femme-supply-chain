# Prophet Time Series Forecasting for CPG/Beverage Demand

## Executive Summary

Prophet is Facebook's automated time series forecasting procedure designed specifically for business applications with strong seasonal patterns and holiday effects. For a beverage/champagne supply chain like Une Femme, Prophet offers a compelling approach to 26-week rolling forecasts by decomposing demand into trend, yearly/weekly seasonalities, and holiday effects. The model excels at capturing the dramatic seasonal spikes characteristic of champagne (7.5x baseline on NYE, 2.5-3x on holidays) and can incorporate external regressors for pricing and promotional effects. While Prophet is not the highest-accuracy model in academic benchmarks, its combination of automation, interpretability, and handling of multiple seasonal patterns makes it particularly well-suited for CPG demand planning when coupled with rolling cross-validation for hyperparameter tuning.

## Key Concepts and Definitions

### Prophet Core Model Structure

Prophet uses an additive decomposition model expressed as:

**y_t = g(t) + s(t) + h(t) + ε_t**

Where:
- **g(t)** = Piecewise-linear trend with automatically detected changepoints
- **s(t)** = Seasonal patterns modeled via Fourier series
- **h(t)** = Holiday/special event effects
- **ε_t** = White noise error term

This structured approach differs fundamentally from black-box machine learning models, enabling business analysts to understand and adjust each component independently.

### Trend Component

The trend uses a piecewise-linear model that identifies changepoints where the growth rate shifts. Prophet automatically detects the number and location of changepoints using a sparse prior on the rate of change. The `changepoint_prior_scale` hyperparameter controls flexibility: larger values allow many trend changes (higher variance), while smaller values enforce smoother trends. For retail/CPG, trend changepoints typically occur around major business events, supply chain disruptions, or market shifts.

### Seasonality Modeling

Prophet models seasonality using Fourier series, which allows smooth periodic patterns to emerge from data:

- **Yearly Seasonality**: Default Fourier order of 10 (requires at least 2 years of data)
- **Weekly Seasonality**: Default Fourier order of 3 (requires at least 2 weeks of data)
- **Daily/Custom Seasonality**: Can be added explicitly with specified periods and Fourier orders

The Fourier order parameter controls smoothness vs. flexibility: higher orders capture faster-changing cycles but risk overfitting. For champagne, monthly patterns (Valentine's Day, Mother's Day, holidays) can be modeled as custom seasonalities beyond the standard yearly/weekly patterns.

**Multiplicative vs. Additive Seasonality**: Prophet supports both modes. Additive seasonality assumes seasonal variations are constant in magnitude (typical for many beverages). Multiplicative seasonality scales with the trend level (appropriate when seasonal swings grow during peak demand periods). For wine/champagne, multiplicative seasonality is often more realistic—December demand amplifies proportionally more when baseline demand is already elevated.

### Holiday Effects

Holiday effects are modeled as dummy variables that shift the forecast on specific dates. Implementation requires:

1. **Holiday Dataframe**: Columns for `holiday` name and `ds` (date)
2. **Window Extension**: `lower_window` and `upper_window` parameters to model before/after effects (e.g., Christmas Eve with Christmas)
3. **Future Dates**: Holiday dataframe must include all past and future occurrences

Prophet provides `add_country_holidays()` for automatic country-specific holidays, but custom holidays are critical for CPG (e.g., Valentine's Day, Mother's Day, Thanksgiving promotions).

### External Regressors

The `add_regressor()` function incorporates external variables (price, promotion flags, distribution metrics) as linear predictors. Critical constraint: regressor values must be known for both historical and forecast periods. For CPG applications, common regressors include:

- Log of selling price
- Promotional indicator variables
- Marketing spend levels
- Distribution metrics (number of stores stocking)
- Competitive pricing

## Main Arguments and Findings

### Prophet's Strengths for CPG/Beverage Demand

**1. Handles Multiple Seasonalities Simultaneously**
Unlike traditional ARIMA (which typically models one seasonal pattern), Prophet natively handles daily, weekly, and yearly seasonality in the same model. For beverage demand, this is critical—daily patterns (weekday vs. weekend), weekly patterns, and dramatic yearly spikes (NYE, holidays) all matter simultaneously.

**2. Automatic Trend Changepoint Detection**
The model automatically identifies where demand patterns shift without manual intervention. This is valuable for retail/CPG where promotions, new distribution channels, or competitive actions create regime shifts. The prior specification means the model balances between too many changepoints (overfitting) and too few (underfitting the actual business reality).

**3. Holiday Effects as First-Class Component**
Rather than treating holidays as outliers to remove, Prophet explicitly models them. For champagne, this is essential:
- NYE: +648% sales increase or 7.5x typical day (Saucey data)
- December overall: ~20% of annual consumption, with 2.5-3x baseline volumes
- Valentine's Day, Mother's Day, weddings: Significant but secondary peaks

The model estimates each holiday's effect with uncertainty intervals, enabling supply chain planning for known demand spikes.

**4. Built-in Uncertainty Quantification**
Prophet produces prediction intervals (upper/lower bounds) alongside point forecasts. This is critical for supply chain risk management—planners need confidence intervals to set safety stock levels, not just point forecasts. The uncertainty automatically widens for longer horizons.

**5. Interpretability and Business Integration**
The decomposition into trend, seasonality, and holidays produces interpretable components that business stakeholders understand. Analysts can inspect trend changes, seasonal patterns, and holiday effects visually, enabling collaborative forecast refinement.

### CPG/Beverage Demand Patterns

**Champagne/Sparkling Wine Seasonality**
- December represents approximately 20% of annual consumption despite being only 1/12 of the year
- NYE sales spike: Average +648% on December 31st, or 7.5x a typical day on Saucey platform
- Over 360 million glasses consumed on NYE in the US alone
- Holiday season demand extends through early January (gifts, celebrations)
- Valentine's Day creates secondary spike (romantic occasion, gifting)
- Spring events (Mother's Day, weddings, graduations) generate modest increases
- Summer: Baseline demand, occasional entertainment spikes
- Prosecco exhibits similar seasonal patterns but with growing year-over-year share

**Market Shift Context**
- Champagne volume declined 7% from 2021-2023 while prosecco grew 5%
- Younger consumers prefer prosecco at lower price points, especially during festive seasons
- Economy segment dominates seasonal demand (consumers seeking "champagne experience" at lower cost)
- This shift means Une Femme must forecast not just demand volume but category mix

**Implication for Rolling Forecasts**
A 26-week rolling forecast window captures approximately 6 months of data, which includes either:
- The full holiday season (Oct-Dec) plus baseline (Jan-Mar), or
- Baseline (Apr-Sep) plus the beginning of holiday ramp (Oct-Dec)

This horizon is appropriate for CPG supply chain planning, as it allows procurement lead times (typically 8-12 weeks) while capturing seasonal transitions.

### Comparison with Alternative Models

**Prophet vs. ARIMA (Autoregressive Integrated Moving Average)**

| Dimension | ARIMA | Prophet |
|-----------|-------|---------|
| Seasonality | Single seasonal pattern | Multiple (daily, weekly, yearly, custom) |
| Automation | Requires manual parameter tuning (p,d,q) | Automatic with Bayesian priors |
| Trend Flexibility | Fixed, requires differencing | Piecewise-linear with automatic changepoints |
| External Regressors | Supported (ARIMAX) | Supported via add_regressor() |
| Interpretability | Difficult for business users | Decomposable, visual components |
| Short-term Accuracy | Often better on benchmarks | Acceptable but sometimes underperforms |
| Holiday Handling | Manual dummy variables | Native with uncertainty quantification |
| Computational Speed | Fast | Faster than alternatives like LSTM |

**Research Finding**: A recent comparative study found that for demand forecasting with multiple seasonal patterns, hybrid LSTM-Prophet and ensemble ARIMA-XGBoost approaches outperform single models. However, ARIMA often shows better accuracy on standard benchmarks when only single seasonality is present.

**Prophet vs. LSTM (Long Short-Term Memory)**

| Dimension | LSTM | Prophet |
|-----------|------|---------|
| Complexity | Deep learning, requires significant data | Statistical model, works with shorter histories |
| Data Requirements | 1000s-10000s of observations ideal | Effective with 2 years minimum |
| Seasonality | Learned implicitly | Explicitly modeled via Fourier series |
| Interpretability | Black box, difficult to explain | Transparent components |
| Holiday Effects | Must learn patterns implicitly | Explicitly specified |
| Computational Cost | GPU-intensive, slower inference | CPU-based, fast inference |
| Development Time | Weeks of hyperparameter tuning | Days to weeks with grid search |
| Production Deployment | Complex deep learning infrastructure | Standard Python/R libraries |

**Research Finding**: LSTM achieves highest accuracy for complex, long-term patterns with sufficient data, but Prophet offers better risk-adjusted performance for typical CPG scenarios where interpretability, speed, and operational integration matter.

**Prophet vs. XGBoost**

| Dimension | XGBoost | Prophet |
|-----------|---------|---------|
| Seasonality Handling | Requires feature engineering | Native Fourier decomposition |
| Holiday Effects | Manual feature creation | Automatic with uncertainty |
| Multivariate Capability | Excellent, handles many features | Single output, external regressors only |
| Non-linear Relationships | Natural fit for complex patterns | Linear for trend/regressors, periodic for seasonality |
| Ensemble Capability | Yes, multiple boosting rounds | Can be ensembled with other models |
| Benchmark Performance | Often wins on short-horizon | Prophet competitive for seasonal data |
| Automation | Requires careful feature engineering | Highly automated |
| Explainability | SHAP values available | Direct component interpretation |

**Research Finding**: XGBoost excels when multiple external features (price, promotions, competitor data) are available. However, hybrid ARIMA-XGBoost and LSTM-Prophet ensembles show 15-25% MAPE improvements over single models for demanding CPG scenarios.

### Model Accuracy Benchmarks for Seasonal Data

**Metric Definitions** (relevant for 26-week forecasts):
- **MAPE (Mean Absolute Percentage Error)**: Average of |forecast-actual|/actual × 100%. Scale-independent, standard for retail/CPG. Target for beverage demand: <10% acceptable, <8% good, <5% excellent.
- **RMSE (Root Mean Square Error)**: Penalizes larger errors more heavily. Useful for safety stock calculations.
- **MAE (Mean Absolute Error)**: Robust to outliers, easier to explain in business units (e.g., "off by 500 units on average").

**Prophet-Specific Performance**:
- Prophet documentation notes that it "often underperforms compared to ARIMA and ETS models on benchmark datasets"
- However, this caveat applies primarily to datasets with single seasonality and limited trend changes
- On multi-seasonal datasets (like CPG), Prophet's explicit seasonality handling typically yields competitive results
- For holiday-heavy forecasts (>20% of demand in concentrated periods), Prophet's native holiday effects provide substantial accuracy improvements

**Comparative Results from Academic Research**:
- Hybrid LSTM-Prophet: MAPE typically 8-12% on multi-seasonal retail data
- ARIMA alone: MAPE 10-15% on seasonal retail/CPG data
- Prophet alone: MAPE 9-14% on seasonal retail/CPG data
- XGBoost with feature engineering: MAPE 7-11% when external variables included
- Ensemble ARIMA-XGBoost: MAPE 7-10% combining statistical and ML strengths

## Methodology and Implementation Approach

### Training Data Requirements

For a 26-week rolling forecast:
- **Minimum History**: At least 2 years (104 weeks) of daily or weekly sales data
- **Ideal History**: 3-4 years to capture seasonal variation and trend stability
- **Data Frequency**: Weekly data typical for CPG (reduces noise vs. daily, but maintains seasonality)
- **Missing Data**: Prophet handles missing values automatically (interpolates with trend/seasonality)

### Prophet Implementation Steps for Une Femme

**Step 1: Data Preparation**
```
Input: Historical champagne/wine sales by SKU and date
Format: Dataframe with columns [ds (date), y (sales volume/revenue)]
Frequency: Weekly aggregation from daily POS data
Validation: Check for outliers, missing weeks, data quality
```

**Step 2: Holiday Definition**
Create holiday dataframe for:
- Fixed dates: NYE (Dec 31), Valentine's Day (Feb 14), Mother's Day (2nd Sunday May), etc.
- Context-dependent: Shopping windows (Nov 20-Dec 24 "holiday season"), Jan 1-5 "gift season"
- Custom: Company-specific (product launch dates, major promotions)

Example for NYE:
```
holiday_df = pd.DataFrame({
    'holiday': 'NYE',
    'ds': pd.date_range('2020-12-31', '2026-12-31', freq='AS'),
    'lower_window': -7,  # Start effect one week before
    'upper_window': 1    # Extend one day after
})
```

**Step 3: Model Initialization and Configuration**

Key parameters for champagne demand:
- **growth='linear'**: Piecewise-linear trend (appropriate for stable CPG category)
- **seasonality_mode='multiplicative'**: Seasonal swings amplify with demand level (fits holiday dynamics)
- **yearly_seasonality=True**: Enable yearly pattern (critical for holiday seasonality)
- **weekly_seasonality=True**: Enable weekly pattern (weekday vs. weekend demand)
- **seasonality_prior_scale=10**: Default; tuned via cross-validation

**Step 4: Add External Regressors** (Optional but Recommended)

```
m.add_regressor('log_price')  # Price sensitivity
m.add_regressor('promotional_flag')  # On-promotion indicator
m.add_regressor('distribution_index')  # Store count/distribution breadth
```

Constraint: Must forecast or provide these regressors for the forecast period.

**Step 5: Fit and Forecast**

```python
from prophet import Prophet

m = Prophet(
    yearly_seasonality=True,
    weekly_seasonality=True,
    seasonality_mode='multiplicative',
    changepoint_prior_scale=0.05,  # Tuned value
    seasonality_prior_scale=10      # Tuned value
)

# Add holidays
m.add_country_holidays(country_name='US')
for holiday in custom_holidays:
    m.add_seasonality(...)

m.fit(df)  # df has columns ['ds', 'y']

# 26-week forecast
future = m.make_future_dataframe(periods=26, freq='W')
forecast = m.predict(future)  # Includes yhat, yhat_lower, yhat_upper
```

**Step 6: Cross-Validation and Hyperparameter Tuning**

Critical for operational forecasts—academic accuracy matters less than stable, business-appropriate predictions.

```python
from prophet.diagnostics import cross_validation, performance_metrics

cv_results = cross_validation(
    m,
    initial='365 days',      # Minimum training period
    period='90 days',        # Spacing between cutoff dates
    horizon='28 days',       # Evaluate 4-week ahead forecasts
    parallel="processes"     # Parallel cross-validation
)

metrics = performance_metrics(cv_results)
# Plot MAPE, RMSE across horizons to identify forecast decay
```

### Hyperparameter Tuning Strategy

For Une Femme's 26-week rolling forecast, focus on these parameters:

**1. changepoint_prior_scale** (Range: 0.001 to 0.5)
- **Purpose**: Controls trend flexibility and changepoint frequency
- **Benchmark values**: 0.01 (smooth), 0.05 (moderate, recommended), 0.15 (flexible)
- **CPG context**: Holiday season causes demand regime shifts; use moderate-to-flexible values
- **Tuning approach**: Grid search [0.01, 0.05, 0.10], evaluate with 4-week ahead cross-validation MAPE

**2. seasonality_prior_scale** (Range: 0.01 to 10)
- **Purpose**: Regularizes seasonal magnitude; larger values allow bigger seasonal swings
- **Benchmark values**: 1 (default is 10); for champagne with 7.5x NYE spikes, may need 10-12
- **CPG context**: Holiday amplification is dramatic and known; higher values appropriate
- **Tuning approach**: Grid search [1, 5, 10, 15], evaluate seasonal fit on held-out holiday periods

**3. seasonality_mode** (Choice: 'additive' vs. 'multiplicative')
- **For champagne**: Test both; multiplicative likely fits better (demand spikes scale with baseline)
- **Evaluation**: Visual inspection of residuals during high-demand periods

**4. Fourier Orders** (Default: 10 for yearly, 3 for weekly)
- Rarely requires tuning; defaults generally appropriate
- Increase if Prophet misses rapid demand fluctuations; decrease if overfitting visible

### Rolling Forecast Implementation

**26-Week Rolling Window Process**:
1. **Initial model**: Fit on 2+ years historical data
2. **Weekly update**: As each new week's actual sales arrive:
   - Drop oldest week from training set
   - Add newest week with actual values
   - Refit Prophet model (fast, <30 seconds typical)
   - Generate new 26-week forecast
3. **Comparison**: Track actual vs. forecast for continuous accuracy monitoring
4. **Adjustment**: If MAPE degrades >15% or systematic bias emerges, retune hyperparameters via cross-validation

This rolling approach ensures forecasts adapt to demand changes (new products, distribution shifts) while maintaining stability through regular retraining.

## Specific Examples and Case Studies

### Example 1: NYE Demand Spike Modeling

**Scenario**: Une Femme needs to forecast 2025 NYE demand for champagne inventory planning.

**Approach**:
1. Historical analysis: NYE 2023, 2024 showed 7-8x baseline demand on December 31
2. Holiday dataframe: NYE effect with lower_window=-7 (start one week prior for shopping), upper_window=1
3. Custom seasonality: Consider modeling "holiday shopping season" (Nov 20-Dec 24) as concentrated period
4. Regressor: Distribution expanded to new grocery chains in Q4 2024; include distribution_index regressor

**Expected outcome**:
- Forecast for Dec 24-31: 70,000+ units (vs. 10,000 typical weekly)
- Confidence interval: 55,000-85,000 (wider due to holiday uncertainty)
- Inventory recommendation: Target 75,000 units by Dec 15 to avoid stockout while minimizing overstock

### Example 2: Valentine's Day Secondary Spike

**Scenario**: February demand includes Valentine's Day spike (romantic gifting) plus baseline.

**Approach**:
1. Analysis: Valentine's creates 2.5-3x demand on Feb 14; effect extends Feb 7-14
2. Holiday dataframe: Valentine_Day with lower_window=-7, upper_window=0
3. Price promotion consideration: If Valentine's marketing includes discounts, create promotional_flag regressor
4. Category mix: Separate forecasts for premium/luxury (gift-focused, higher margin) vs. everyday (volume)

**Expected outcome**:
- Baseline (non-holiday weeks): 15,000 units/week
- Valentine's period (Feb 7-14): 35,000-40,000 units
- Risk: If promotion deeper than historical, demand exceeds forecast; safety stock of 8,000 units recommended

### Example 3: Prosecco vs. Champagne Category Mix

**Scenario**: Market data shows prosecco gaining share (5% growth 2021-2023 vs. champagne -7%). Une Femme needs separate forecasts for champagne and prosecco.

**Challenge**: Prosecco seasonality may differ slightly (lower luxury positioning, more everyday consumption).

**Approach**:
1. Separate Prophet models for each category
2. Champagne: Multiplicative seasonality (spikes scale with baseline)
3. Prosecco: Test both additive and multiplicative; likely additive (more stable, less extreme spikes)
4. Shared regressors: Distribution, price (price elasticity may differ between categories)
5. Cross-validation: Evaluate both models' 4-week ahead MAPE; target <10% for planning

**Expected outcome**:
- Champagne MAPE: 9-12% (larger seasonal swings increase error)
- Prosecco MAPE: 7-10% (more stable, easier to forecast)
- Ensemble recommendation: Weight prosecco higher in blended forecast (lower error)

## Notable Quotes and Insights

**Prophet Design Philosophy**:
"Prophet is a procedure for forecasting time series data based on an additive model where non-linear trends are fit with yearly, weekly, and daily seasonality, plus holiday effects." (Facebook Prophet Documentation)

This quote encapsulates Prophet's core design: it's built for **business forecasting**, not academic optimization. The explicit mention of multiple seasonality types and holiday effects reflects real-world retail/CPG requirements.

**On Trend Flexibility**:
"Changepoint prior scale is probably the most impactful parameter." (Prophet Diagnostics)

This insight guides tuning strategy. For Une Femme, a single changepoint parameter controls whether the model treats demand regime shifts (e.g., new distribution, competitive entry) as trend changes or anomalies. This is operationally critical.

**On External Regressors**:
"The extra regressor must be known for both the history and for future dates, so it must either be something that has known future values or something that has separately been forecasted elsewhere." (Prophet Documentation)

This constraint is practical but important. Price and promotion are under Une Femme's control (known future values). Distribution may need forecasting if expansion is planned. This shapes feature engineering strategy.

**On Seasonal Decomposition for CPG**:
"Multiplicative seasonality assumes seasonal variations are proportional to the level of the time series, which is often more appropriate for data with strong trends or when seasonal swings grow in magnitude over time." (Prophet Best Practices)

For champagne with 7.5x NYE spikes, multiplicative seasonality is more realistic than additive. This choice directly impacts forecast uncertainty intervals—critical for safety stock.

**On Comparative Strengths**:
"Hybrid LSTM-Prophet models consistently outperform benchmark models, integrating Long Short-Term Memory networks and Prophet models, where the LSTM component captures nonlinear dependencies and long-term temporal patterns, while Prophet models seasonal trends and event-driven fluctuations." (Academic Research)

This suggests a potential Phase 2 for Une Femme: if initial Prophet implementation shows systematic underfitting in certain product lines, ensembling with LSTM (trained on predicted residuals) could improve accuracy by 15-25%.

## Critical Evaluation and Limitations

### Prophet's Known Limitations

**1. Underperformance on Benchmark Datasets**
- Forecasting: Principles and Practice textbook notes Prophet "often underperforms compared to ARIMA and ETS models"
- **Caveat**: Benchmarks are synthetic/academic; real CPG data often has characteristics (multiple seasonality, holidays) where Prophet excels
- **Implication for Une Femme**: Expect competitive MAPE (9-12%) on champagne demand, potentially beating ARIMA despite benchmark results

**2. Long-term Trend Issues**
- Prophet may produce inappropriate long-term trends, especially when trained on short histories with trend reversals
- **Mitigation**: 26-week rolling forecast naturally constrains long-term extrapolation; retraining weekly prevents trend drift
- **Risk**: If a 3-year structural shift occurs (e.g., major market consolidation), rolling 26-week forecasts may miss it until trend changepoints accumulate

**3. Residual Autocorrelation**
- Prophet can leave substantial autocorrelation in residuals, resulting in overly narrow prediction intervals
- **Business impact**: Confidence intervals may understate true uncertainty, leading to insufficient safety stock
- **Mitigation**: Review residuals monthly; if autocorrelation detected, widen intervals manually or consider ensemble with ARIMA

**4. Hyperparameter Sensitivity**
- While Prophet automizes many aspects, changepoint_prior_scale and seasonality_prior_scale are sensitive
- Poor tuning can yield either underfitting (missed trend shifts) or overfitting (false changepoints)
- **Mitigation**: Grid search hyperparameters on held-out seasonal periods; re-tune quarterly

**5. Limited Multivariate Capability**
- Prophet forecasts single output; if Une Femme needs joint forecasts (champagne + prosecco + other wines) with dependencies, single-output Prophet has limitations
- **Mitigation**: Forecast each category separately; post-hoc constraint forecast totals if needed

### Data Quality Requirements

**For successful Prophet implementation, Une Femme must have**:
1. **Consistent historical data**: 2+ years of weekly sales by SKU/category
2. **Clean calendar**: No major gaps; missing weeks interpolated or clearly documented
3. **Holiday definitions**: Accurate dates for company-specific events (product launches, major promotions)
4. **Exogenous variables**: Price, distribution, promotion flags available both historically and forecast forward
5. **Business context**: Understanding of demand drivers (what caused past anomalies?)

### Appropriate Use Cases vs. Limitations

**Prophet Excels In**:
- Multiple seasonal patterns (daily/weekly/yearly/custom)
- Strong, known holidays with advance calendars
- Business users needing interpretable forecasts
- Fast, reliable automation for many SKUs
- Risk quantification via uncertainty intervals

**Prophet Not Recommended For**:
- Single seasonal pattern (ARIMA often better)
- Highly non-linear relationships without external regressors (XGBoost better)
- Very long-term forecasts (>12 months; extrapolation less reliable)
- Insufficient history (<12 months)
- Extreme outliers without removal/flagging

## Relevance to Une Femme Supply Chain Intelligence Platform

### Strategic Fit

**Core Problem**: Une Femme needs accurate, rolling 26-week champagne/wine demand forecasts to optimize:
- Procurement planning (8-12 week lead times)
- Inventory management (minimize stockouts while controlling carrying costs)
- Supply chain visibility (communicate demand signals to producers/distributors)
- Revenue management (dynamic pricing/promotions informed by demand forecast)

**Prophet's Suitability**:

1. **Handles Champagne Seasonality**: 7.5x NYE spike, 2.5-3x holiday season, known calendar events—Prophet's native holiday effects are designed for exactly this pattern

2. **26-Week Horizon Alignment**: Rolling forecast window is operationally ideal (covers typical lead times + seasonal transition); Prophet's 4-week cross-validation naturally supports this cadence

3. **Interpretability for Supply Chain**: Decomposition into trend/seasonality/holidays enables supply chain teams to understand forecast drivers. "Holiday season will spike 2.5x" is actionable in ways a black-box model isn't.

4. **Multi-SKU Scalability**: Prophet can be applied independently to each wine/champagne SKU, enabling category-specific forecasts. Automation scales to 50-500 SKUs typical in wine retail

5. **Integration with Existing Systems**: Prophet outputs are standard DataFrames; easily integrate with ERP/supply chain planning tools via API

### Implementation Roadmap for Une Femme

**Phase 1: Proof of Concept (Weeks 1-4)**
- Gather 2+ years historical daily/weekly sales data for top 5 SKUs
- Define holiday calendar (NYE, Valentine's, Mother's Day, etc.) + company-specific events
- Build Prophet models for each SKU
- Cross-validate with 4-week ahead MAPE target <12%
- Manually compare forecasts to business intuition; identify obvious misses
- **Deliverable**: Recommendation memo on feasibility + sample 26-week forecast

**Phase 2: Hyperparameter Tuning and Validation (Weeks 5-8)**
- Grid search changepoint_prior_scale, seasonality_prior_scale on full product assortment
- Test multiplicative vs. additive seasonality; select per-category
- Evaluate external regressors: price, distribution, promotion flags (requires data integration)
- Implement cross-validation pipeline (daily retraining simulation on 1-year historical data)
- **Deliverable**: Tuned hyperparameters, cross-validation performance metrics, forecast vs. actual analysis

**Phase 3: Rolling Forecast Infrastructure (Weeks 9-16)**
- Build automated pipeline: weekly data ingestion → Prophet retrain → forecast output
- Integration with ERP/supply chain planning system
- Dashboard: Forecast vs. actual trend, MAPE by SKU, automatic alerts for forecast degradation
- Change management: Train supply chain team on interpreting Prophet decomposition, adjusting when needed
- **Deliverable**: Operational rolling forecast system, live dashboard, runbooks

**Phase 4: Ensemble and Optimization (Weeks 17-24)**
- If Prophet MAPE >12% on specific SKUs, evaluate ARIMA or hybrid Prophet-LSTM ensemble
- Incorporate business adjustments (manual forecast override mechanism for known events)
- A/B test: Compare Prophet-recommended purchase orders vs. historical demand-driven orders; quantify inventory/margin improvement
- **Deliverable**: Optimized ensemble model, business case for supply chain network optimization

### Key Metrics for Success

1. **Forecast Accuracy**: MAPE <10% on 4-week ahead forecasts; <12% on full 26-week horizon
2. **Operational Improvement**: Stockout rate reduction (target: 50%), excess inventory reduction (target: 30-40%)
3. **Adoption**: Supply chain team confidence; <5% forecast overrides per cycle (acceptable for known events)
4. **Scalability**: <2 hours total compute for weekly retraining across 100+ SKUs
5. **Business Impact**: Margin improvement via better inventory turns + revenue protection from stockout avoidance

## Practical Implementation Recommendations for Une Femme

### 1. Seasonality Mode Selection

**Recommendation: Multiplicative for champagne/sparkling wine, test both for still wines**

Champagne demand spikes (7.5x on NYE, 2.5-3x holidays) scale with baseline. Multiplicative mode captures this: if baseline is 10,000 units/week, holiday multiplier of 2.5 yields 25,000 units; if baseline is 15,000, same multiplier yields 37,500. This better reflects real market dynamics than additive (+15,000 units regardless).

**Validation**: Fit models on 1-year holdout data; compare residual patterns during high vs. low demand periods. If residuals are larger in absolute magnitude during holidays regardless of baseline, multiplicative is correct.

### 2. Holiday Definition Strategy

**Recommended holiday list for wine/champagne category**:

| Holiday | Window | Reason |
|---------|--------|--------|
| New Year's Eve | Dec 24-31 (shopping) + Jan 1-5 (gift season) | 7.5x spike Dec 31; extends into January for gift consumption |
| Valentine's Day | Feb 7-14 | 2.5-3x spike for romantic gifting |
| Mother's Day | May 1-14 (2nd Sunday May is official) | Secondary spike, gifting occasion |
| Father's Day | Jun 1-20 (3rd Sunday June) | Similar to Mother's Day |
| Thanksgiving | Nov 20-27 | Pre-holiday entertaining, entertaining stocks up |
| Christmas | Dec 15-26 | Gift season, family gatherings (overlaps with NYE) |
| Easter | Mar/Apr (varies, ~6 weeks before Easter) | Varies by year; modest effect |
| Summer Entertaining | Jun 1-Sep 15 | Weak, diffuse; consider as custom seasonality instead |

**Implementation**: Construct holiday_df with exact dates + windows; use lower_window=-7 for 1-week pre-holiday shopping, upper_window=0-1 for post-holiday effect decay.

### 3. External Regressor Selection

**Phase 1 (Minimum)**:
- Log of selling price: Strong demand elasticity, known future values
- Promotional flag: Binary indicator for active promotion; internal control
- **Rationale**: Fast to implement, high ROI; these drive 30-40% of demand variance in CPG

**Phase 2 (Medium-term)**:
- Distribution index: Number of stores stocking, geographic expansion
- Competitive pricing: Major competitor prices (requires data integration)
- Marketing spend: If promotional spending tracked by campaign
- **Rationale**: Capture supply-side (distribution) and competitive dynamics

**Phase 3 (Advanced)**:
- Weather data: Temperature, precipitation (correlation with entertaining, garden parties)
- Macro indicators: Unemployment, consumer confidence (wealth effects on luxury champagne)
- Social media sentiment: Brand mentions, holiday discussions (early indicator)
- **Rationale**: Marginal gains; high data integration cost

**Data requirement**: Regressors must be available for forecast period. Price/promotion are controllable (plan known). Distribution should have quarterly expansion targets. Weather is fully forecastable. Competitive pricing is lagging indicator—use recent values.

### 4. Changepoint Prior Scale Tuning

**Recommended tuning approach for champagne**:

| changepoint_prior_scale | Interpretation | Best For |
|-------------------------|-----------------|----------|
| 0.01 | Very smooth trend, no sudden shifts | Mature, stable categories |
| 0.05 | Moderate; captures major shifts, avoids noise | Champagne (recommended starting point) |
| 0.10-0.15 | Flexible; responds to smaller demand changes | High-growth or volatile categories |
| 0.25+ | Very flexible; risk of overfitting to noise | Rarely recommended for CPG |

**Tuning procedure**:
1. Fit models with changepoint_prior_scale in [0.01, 0.05, 0.10]
2. Cross-validate using 4-week ahead horizon (relevant for supply chain)
3. Inspect trend component visually for each:
   - 0.01: Single smooth trend line (may miss 2023 market shift)
   - 0.05: 1-2 trend shifts (likely aligns with business events)
   - 0.10: Multiple shifts (check if business-justified or overfitting)
4. **Select 0.05 unless strong business reason otherwise**

### 5. Rolling Forecast Cadence and Retraining

**Recommended approach**:
- **Weekly retraining**: Every Monday morning, ingest prior week's sales actuals, refit Prophet, generate new 26-week forecast
- **Compute time**: <30 seconds per SKU; <10 minutes for 50-SKU assortment
- **Forecast update**: New forecast reflects latest demand signals while maintaining stable seasonality estimates
- **Hyperparameter refresh**: Quarterly (every 13 weeks) re-tune via cross-validation on 52-week training window; respond to market changes faster

**Risk management**:
- If actual demand >forecast by >20% for 2 consecutive weeks, trigger alert and business review (demand driver changed?)
- If MAPE degradation detected (4-week rolling error increases >15% vs. baseline), initiate hyperparameter re-tuning
- Manual override mechanism: Supply chain manager can adjust forecast by hand for known events (unexpected promotion, supply shock) with logging for continuous improvement

### 6. Ensemble Consideration and Model Comparison

**Recommendation: Start with pure Prophet, monitor for systematic issues, ensemble if needed**

**Decision tree**:
```
Fit Prophet model
├─ Cross-validated MAPE <10%?
│  └─ YES: Deploy Prophet as primary forecast
│  └─ NO: Continue diagnostics
├─ Residuals autocorrelated?
│  └─ YES: Consider ARIMA component (hybrid approach)
│  └─ NO: Proceed
├─ Systematic over/under forecast during holidays?
│  └─ YES: Adjust holiday_prior_scale or custom seasonality
│  └─ NO: Proceed
├─ Forecast is acceptable (MAPE 10-12%)?
│  └─ YES: Deploy as operational forecast
│  └─ NO: Evaluate ensemble (Prophet + LSTM on residuals, or ARIMA-Prophet hybrid)
```

**Hybrid ARIMA-Prophet approach** (if required):
1. Fit Prophet on original series
2. Calculate residuals: residual_t = actual_t - prophet_forecast_t
3. Fit ARIMA(p,d,q) on residuals to capture autocorrelation
4. Final forecast = Prophet_forecast + ARIMA_residual_forecast
5. **Benefit**: Combines Prophet's seasonality/holiday handling with ARIMA's autocorrelation modeling
6. **Cost**: More complex, requires ARIMA parameter tuning

**When to ensemble**: If Prophet MAPE >12% or residuals show significant autocorrelation (Ljung-Box test p-value <0.05) after tuning.

### 7. Safety Stock and Uncertainty Interval Usage

**Prophet generates yhat_lower and yhat_upper** (default 80% confidence intervals). For supply chain:

**Safety Stock Formula**:
```
Safety Stock = (yhat_upper - yhat) × Service Factor

Where:
- yhat = point forecast (mean)
- yhat_upper = 90th percentile (reduce default 80% to 90% for critical inventory)
- Service Factor = 1.0 (use upper bound directly) or <1.0 (partial safety stock if cost-prohibitive)
```

**Example for NYE 2025**:
- Prophet forecast (yhat): 70,000 units
- Uncertainty interval (yhat_upper at 80%): 78,000 units
- Service level target: 95% (critical holiday)
  - Widen interval to 95th percentile: ~85,000 units (Prophet can estimate)
  - Safety Stock = (85,000 - 70,000) × 1.0 = 15,000 units
  - Recommended purchase order: 70,000 + 15,000 = 85,000 units
  - Cost: 15,000 × $12 unit cost = $180,000 working capital
  - Benefit: 95% probability of availability; stockout risk <5%

**Validation**: Track actual demand vs. yhat_lower/yhat_upper; over time, ~80-90% of actuals should fall within intervals. If not, adjust confidence level or investigate regressor changes.

## Conclusion

Prophet is a strategically well-aligned choice for Une Femme's 26-week rolling demand forecast. Its explicit handling of multiple seasonalities, holiday effects, and interpretable decomposition directly address champagne's 7.5x NYE spikes and secondary holiday peaks. While not the highest-accuracy model in academic benchmarks, Prophet's combination of automation, business interpretability, and operational robustness makes it ideal for CPG supply chain planning.

**Recommended path forward**:
1. Implement Phase 1 POC with top 5 SKUs (4 weeks)
2. Validate MAPE <12% via cross-validation before operational deployment
3. Integrate rolling weekly retraining into supply chain planning cycle
4. Monitor residuals and forecast accuracy; ensemble with ARIMA if MAPE >12% in production
5. Leverage uncertainty intervals for scientific safety stock management, not over-stocking

With proper hyperparameter tuning (focus on changepoint_prior_scale=0.05 and multiplicative seasonality for champagne) and thoughtful holiday definition (NYE, Valentine's, Mother's Day), Prophet should deliver operational forecast accuracy of 9-12% MAPE, enabling 30-40% reduction in excess inventory while maintaining service levels.

---

## Sources and Further Reading

### Core Prophet Documentation and Research
- [Prophet Official Documentation - Seasonality, Holiday Effects, and Regressors](https://facebook.github.io/prophet/docs/seasonality,_holiday_effects,_and_regressors.html)
- [Prophet Official Documentation - Diagnostics](https://facebook.github.io/prophet/docs/diagnostics.html)
- [Forecasting: Principles and Practice (3rd ed) - Prophet Model Section](https://otexts.com/fpp3/prophet.html)
- [Facebook Prophet GitHub Repository](https://github.com/facebook/prophet)

### Comparative Model Research
- [ARIMA vs Prophet vs LSTM for Time Series Prediction - Neptune AI](https://neptune.ai/blog/arima-vs-prophet-vs-lstm)
- [A Review of ARIMA vs. Machine Learning Approaches for Time Series Forecasting](https://www.mdpi.com/1999-5903/15/8/255)
- [Optimizing Product Demand Forecasting with Hybrid ML and Time Series Models](https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID5076161_code7207861.pdf)
- [Comparison of Statistical and Machine Learning Methods for Time Series Forecasting](https://arxiv.org/pdf/2303.07139)

### CPG and Beverage Demand Forecasting
- [Demand Forecasting Guide for Retail and Consumer Goods - RELEX Solutions](https://www.relexsolutions.com/resources/demand-forecasting/)
- [CPG Demand Planning and Forecasting Best Practices](https://www.polestarllp.com/blog/demand-planning-in-cpg-and-retail-industry)
- [Predictive Demand Planning for CPG Brands - Parallel Dots](https://www.paralleldots.com/resources/blog/predictive-demand-planning-methods-best-practices)

### Champagne and Sparkling Wine Seasonality
- [Champagne Sales Increase by Over 600% on New Year's Eve - Saucey Data](https://blog.saucey.com/champagne-sales-increase-new-years-eve-data/)
- [Is Sparkling Wine's Holiday Spike Slowing? - IWSR Market Analysis](https://www.theiwsr.com/insight/sparkling-wines-holiday-spike-in-the-us-seems-to-be-slowing/)
- [Champagne Market Analysis and Forecast 2033 - Allied Market Research](https://www.alliedmarketresearch.com/champagne-market-A05938)
- [Global Champagne Market Trends and Forecast](https://www.imarcgroup.com/champagne-market)

### Implementation and Best Practices
- [Facebook Prophet for Time-Series Machine Learning - Hopsworks](https://www.hopsworks.ai/post/facebook-prophet-for-time-series-machine-learning)
- [Time-Series Forecasting With Facebook Prophet - Zero To Mastery](https://zerotomastery.io/blog/time-series-forecasting-with-facebook-prophet/)
- [Tuning Parameters of Prophet - Medium](https://medium.com/@sandha.iitr/tuning-parameters-of-prophet-for-forecasting-an-easy-approach-in-python-8c9a6f9be4e8)
- [Changepoint Detection with Prophet - Data Roots](https://dataroots.io/blog/changepoint-detection-with-prophet-2)
