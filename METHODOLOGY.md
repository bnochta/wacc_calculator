# WACC Calculation Methodology

This document describes the formulas and calculation logic implemented in `functions.py`.

## 1. Overview

The WACC (Weighted Average Cost of Capital) is calculated as:

$$
WACC = \frac{E}{D+E} \cdot R_e \;+\; \frac{D}{D+E} \cdot R_d \cdot (1 - T_c)
$$

Where:
- $E$ = market value of equity
- $D$ = market value of debt
- $R_e$ = cost of equity
- $R_d$ = cost of debt
- $T_c$ = statutory (or effective) corporate tax rate

## 2. Data collection & return calculation

### 2.1 Price data

Historical closing prices for the peer group, benchmark, and target are downloaded via `yfinance` (`download_data`), then cleaned (`basic_cleaning`): multi-index columns are flattened and missing values dropped.

### 2.2 Periodic returns

Two return methods are supported (`return_calc_comb`):

**Linear return:**

$$
r_t = \frac{P_t}{P_{t-1}} - 1
$$

**Logarithmic return:**

$$
r_t = \ln\left(\frac{P_t}{P_{t-1}}\right)
$$

### 2.3 Cumulative returns (for charting)

`cumulative_returns` compounds the periodic returns:

**Linear:**

$$
Cumulative_t = \prod_{i=1}^{t}(1 + r_i) - 1
$$

**Logarithmic (as implemented — log-cumulative sum, not compounded return):**

$$
Cumulative_t = \sum_{i=1}^{t} r_i
$$


## 3. Beta estimation

### 3.1 Raw (levered) peer betas

For each peer ticker, an OLS regression is run against the benchmark returns (`beta_regression`):

$$
r_{i,t} = \alpha_i + \beta_i \cdot r_{m,t} + \varepsilon_{i,t}
$$

Where:
- $r_{i,t}$ = peer stock return at time $t$  
- $\alpha_i$ = intercept (constant term) — the peer's average return independent of market movement
- $r_{m,t}$ = benchmark (market) return at time $t$
- $\beta_i$ = raw (levered) beta for peer $i$


### 3.2 Beta adjustment (`beta_adjustments`)

**Blume adjustment** — shrinks raw beta toward the market beta of 1:

$$
\beta_{Blume} = \frac{2}{3} \cdot \beta_{raw} + \frac{1}{3} \cdot 1
$$

**Vasicek adjustment** — Bayesian shrinkage weighted by estimation precision:

$$
w_i = \frac{\sigma^2_{cross}}{\sigma^2_{cross} + SE(\beta_i)^2}
$$

$$
\beta_{Vasicek,i} = w_i \cdot \beta_{raw,i} + (1 - w_i) \cdot \bar{\beta}_{cross}
$$

Where:
- $\sigma^2_{cross}$ = cross-sectional variance of raw peer betas
- $\bar{\beta}_{cross}$ = cross-sectional mean of raw peer betas
- $SE(\beta_i)$ = standard error of peer $i$'s regression beta

A peer with a more precisely estimated beta (lower $SE$) gets more weight on its own raw beta; a peer with a noisier estimate is pulled more toward the peer-group average.

### 3.3 Unlevering peer betas (`unlevered_beta`)

Each peer's (raw / Blume / Vasicek — per user selection) beta is unlevered using the Hamada formula:

$$
\beta_{unlevered,i} = \frac{\beta_{levered,i}}{1 + (1 - T_{c,i}) \cdot \left(\dfrac{D}{E}\right)_i}
$$

Where $\left(\dfrac{D}{E}\right)_i$ is peer $i$'s debt-to-equity ratio and $T_{c,i}$ is peer $i$'s statutory tax rate.

The peer-group unlevered beta is then the **average** or **median** across peers (user-selected):

$$
\beta_{unlevered,peer\_group} = \text{mean}(\beta_{unlevered}) \quad \text{or} \quad \text{median}(\beta_{unlevered})
$$

### 3.4 Relevering to the target company (`get_target_levered`)

The peer-group unlevered beta is relevered using the target's own tax rate and D/E ratio:

$$
\beta_{relevered,target} = \beta_{unlevered,peer\_group} \cdot \left(1 + (1 - T_{c,target}) \cdot \left(\frac{D}{E}\right)_{target}\right)
$$

## 4. Cost of equity ($R_e$)

$$
R_e = r_f + \beta_{relevered} \cdot ERP + SP + CSRP
$$

Where:
- $r_f$ = risk-free rate (country-specific, see §5)
- $ERP$ = Equity Risk Premium (user input)
- $SP$ = Size Premium (user input)
- $CSRP$ = Company-Specific Risk Premium (user input)

## 5. Risk-free rate (`target_rf`)

The risk-free rate is derived from the target company's home-country long-term government bond yield, fetched from FRED using a code built as:

$$
\text{FRED code} = \texttt{"IRLTLT01"} + \langle\text{alpha-2 country code}\rangle + \texttt{"M156N"}
$$

The rate used is the mean of the last `rf_lookback_months` observations ending at the valuation date:

$$
r_f = \frac{1}{k}\sum_{t=T-k+1}^{T} r_{f,t}
$$

## 6. Cost of debt ($R_d$) and debt spread

$$
R_d = r_f + \text{Debt Spread}
$$

### 6.1 Credit spread interpolation (`interpolate_spreads`)

FRED publishes ICE BofA credit spread indices for a limited set of major rating buckets:

| Rating | FRED Series |
|---|---|
| AAA | BAMLC0A1CAAA |
| AA  | BAMLC0A2CAA |
| A   | BAMLC0A3CA |
| BBB | BAMLC0A4CBBB |
| BB  | BAMLH0A1HYBB |
| B   | BAMLH0A2HYB |
| CCC | BAMLH0A3HYC |

Intermediate notches (AA+, AA-, A+, A-, BBB+, BBB-, BB+, BB-, B+, B-) are not directly published, so they are **linearly interpolated** between the adjacent known rating columns (pandas `interpolate(axis=1)` across the rating scale, monthly-resampled).

### 6.2 Applied spread (`get_target_spread`)

The spread for the target's chosen S&P long-term rating is taken as the mean of the last `debt_spread_lookback_months` monthly observations, converted from percentage points to decimal:

$$
\text{Debt Spread} = \frac{1}{k}\sum_{t=T-k+1}^{T} \frac{\text{spread}_{rating,t}}{100}
$$

## 7. Capital structure weights

Weights are derived from the target's own D/E ratio (`get_d_e_ratio`, market value of equity from `yfinance` valuation measures, total debt from the balance sheet):

$$
\text{Equity weight} = \frac{E}{D+E} = \frac{1}{1 + D/E}
$$

$$
\text{Debt weight} = \frac{D}{D+E} = 1 - \text{Equity weight}
$$

## 8. Final WACC formula (`get_wacc`)

$$
WACC = w_E \cdot R_e + w_D \cdot R_d \cdot (1 - T_{c,target})
$$

Where $w_E$ and $w_D$ are the equity and debt weights, and $T_{c,target}$ is the target company's statutory tax rate, looked up from the OECD database by country code.

## 9. Tax rates (`append_tax_rates`, `get_stat_tax_rate`)

Each peer's (and the target's) country is identified via `yfinance`'s company info (`info["country"]`), mapped to an ISO alpha-3 code via `pycountry`, and matched against the OECD statutory tax rate table (`oecd_rates.xlsx`). This statutory rate is used throughout (both for unlevering/relevering beta and for the final WACC tax shield), rather than a company-specific effective tax rate.

## 10. Summary of the full pipeline

\`\`\`
1. Download prices (peer group + benchmark)             → download_data
2. Clean & compute periodic returns                       → basic_cleaning, log_return_calc
3. Regress each peer against benchmark                    → beta_regression
4. Adjust betas (Blume / Vasicek)                          → beta_adjustments
5. Attach peer D/E ratios and tax rates                    → append_d_e_ratio, append_tax_rates
6. Unlever peer betas → aggregate peer-group beta           → unlevered_beta
7. Relever to target's capital structure & tax rate         → get_target_levered
8. Fetch target risk-free rate                              → target_rf
9. Fetch & interpolate credit spreads → target spread        → get_rating_spread_series,
                                                                 interpolate_spreads, get_target_spread
10. Compute Re, Rd, weights → final WACC                     → get_wacc
\`\`\`