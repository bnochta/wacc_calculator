# WACC Calculator

A Python + Streamlit tool that calculates the WACC (Weighted Average Cost of Capital) for a target company, using a peer-group-based beta estimation, market data (Yahoo Finance), macroeconomic data (FRED), and the OECD statutory tax rate database.

## Features

- Download historical price data from Yahoo Finance (`yfinance`)
- Return calculation (linear or logarithmic)
- Peer group beta regression (OLS) against the benchmark
- Beta adjustment (Blume / Vasicek method)
- Unlevering the peer betas and relevering to the target company's capital structure
- Risk-free rate lookup from FRED, country-specific (via long-term government bond benchmark series)
- Credit-rating-based debt spread interpolation (FRED credit spread series)
- Statutory tax rate assignment from the OECD database
- WACC, cost of equity (Re), and cost of debt (Rd) calculation
- Interactive Streamlit UI with Plotly chart (cumulative peer/benchmark returns)
- Jupyter notebook (`main2.ipynb`) walking through each calculation step

## Requirements

- Python 3.10+
- Packages: `yfinance`, `pandas`, `numpy`, `statsmodels`, `pycountry`, `python-dotenv`, `fredapi`, `streamlit`, `plotly`, `openpyxl`

## Setup

1. **FRED API key** — Create a `.env` file in the project root:
2.    Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html
3. **OECD tax rate file** — Place `oecd_rates.xlsx` under `./data/OECD_statutory_tax_rates/`, with columns B:C containing `country_code` (ISO alpha-3) and `tax_rate` (as decimal, e.g. 0.25).
4. **Data folder** — Ensure a `./data/` directory exists (used to auto-save downloaded price data).

## Usage

### Option A — Jupyter Notebook

Open `main.ipynb` and set the input parameters in the second cell:  
**Example input:**
```python
target_ticker = "ADS.DE"
benchmark = "URTH"
start_date = "2020-12-31"
end_date = "2026-08-01"
interval = "1wk"
return_calc = "linear"          # "linear" / "log"
beta_adjustment = "blume"        # "blume" / "vasicek" / "none"
peer_group_beta_method = "median"  # "average" / "median"
rf_lookback_months = 1
equity_risk_premium = 0.055
size_premium = 0.015
comp_spec_risk_premium = 0.00
target_longt_sp_rating = "A"
debt_spread_lookback_months = 1
peer_group = ["NKE", "PUM.DE", "ONON", "DECK", "CROX"]
```

Then run all cells sequentially to obtain the final `wacc` value.

### Option B — Streamlit App

```bash
streamlit run streamlit/wacc_calculator.py
```

Fill in the Target ticker, Benchmark ticker, and Peer Group tickers, set the return-calculation and beta-calculation options, choose the credit rating and premiums, and click **Run Calculation**. Results (WACC, cost of equity/debt breakdown, and a cumulative-return chart) render on the right.
## Known limitations / things to check

- Only works with **active, publicly listed tickers** available on Yahoo Finance.
- `get_d_e_ratio` relies on the closest available balance-sheet date to the valuation date — for illiquid reporting periods this may introduce a lag.
- Country mapping (`pycountry`) requires yfinance's `info["country"]` field to exactly match a recognized country name; some tickers may fail here.
- FRED series codes for risk-free rate (`IRLTLT01<CC>M156N`) and credit spreads are US Fed-published series — availability/history varies by country.
