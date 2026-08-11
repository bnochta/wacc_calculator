import yfinance as yf
import pandas as pd
import numpy as np
import statsmodels.api as sm
import pycountry
import requests
import os
from dotenv import load_dotenv
import fredapi



load_dotenv()
fred_api_key = os.environ.get("fred_api_key")
if not fred_api_key:
    raise RuntimeError("Missing FRED_API_KEY environment variable. Create a .env file containing FRED_API_KEY=<your_api_key>.")

fred = fredapi.Fred(api_key=fred_api_key)

BASE_STRING_1 = "IRLTLT01"
BASE_STRING_2 = "M156N"
#api codes for 10y long-term gov bond benchmark

RATING_SPREAD_SERIES= {
    "AAA": "BAMLC0A1CAAA",
    "AA":  "BAMLC0A2CAA",
    "A":   "BAMLC0A3CA",
    "BBB": "BAMLC0A4CBBB",
    "BB":  "BAMLH0A1HYBB",
    "B":   "BAMLH0A2HYB",
    "CCC": "BAMLH0A3HYC"
}


#FUNCTIONS
def download_data(tickers: list[str], start_date: str, end_date:str, interval: str):
    """Download data for the given tickers from Yahoo Finance"""
    data = yf.download(tickers = tickers, start = start_date, end = end_date, interval = interval)
    return data

def save_data(data: pd.DataFrame, benchmark: str, peer_group: list[str], start_date: str, end_date: str):
    """Save data to csv file"""
    path = f"./data/{benchmark} + {peer_group}_{start_date}_-_{end_date}.csv"
    data.to_csv(path)

def extract_col(data: pd.DataFrame, field: str):
    """Extract columns from the downloaded dataframe"""
    column_data= data[field]
    return column_data

def basic_cleaning(close_data:pd.DataFrame):
    close_data.columns = close_data.columns.get_level_values(0)
    close_data = close_data.dropna()
    return close_data

def log_return_calc(return_calc:str, close_data:pd.DataFrame):
    if return_calc == "log":
        return_data = np.log(close_data / close_data.shift(1))
    elif return_calc == "linear":
        return_data = (close_data / close_data.shift(1)) -1
    else:
        raise ValueError("Return calculation must be either 'log' or 'linear'")

    return_data = return_data.dropna()
    return return_data

def beta_regression(peer_group:list[str], return_data:pd.DataFrame, benchmark:str):
    market = return_data[benchmark]
    raw_betas = []
    std_errors = []

    for ticker in peer_group:
        y = return_data[ticker]
        x = sm.add_constant(market)
        model_ = sm.OLS(y, x).fit()

        raw_betas.append(model_.params[benchmark])
        std_errors.append(model_.bse[benchmark])

    beta_results = pd.DataFrame({
        "Ticker" : peer_group,
        "Standard Error" : std_errors,
        "Raw Betas" : raw_betas,
    })

    return beta_results


def beta_adjustments(beta_results: pd.DataFrame):
    beta_mean = beta_results["Raw Betas"].mean()
    beta_cross_var = beta_results["Raw Betas"].var(ddof=1)

    vas_beta = []

    for ticker in beta_results["Ticker"]:
        se = beta_results.loc[beta_results["Ticker"] == ticker, "Standard Error"].item()
        weight = beta_cross_var / (beta_cross_var + (se ** 2))
        r_bet = beta_results.loc[beta_results["Ticker"] == ticker, "Raw Betas"].item()
        adj_beta = weight * r_bet + (1 - weight) * beta_mean
        vas_beta.append(adj_beta)

    beta_results["Blume adj. beta"] = beta_results["Raw Betas"] * (2 / 3) + (1 * (1 / 3))
    beta_results["Vasicek adj. beta"] = vas_beta

    return beta_results


def append_d_e_ratio(beta_results: pd.DataFrame, end_date:str):
    d_e_ratio = []

    for ticker in beta_results["Ticker"]:
        d_e = float(get_d_e_ratio(ticker=ticker, end_date=end_date))
        d_e_ratio.append(d_e)

    beta_results["D/E ratio"] = d_e_ratio

    return beta_results


def append_tax_rates(beta_results: pd.DataFrame):
    country_list_2 = []
    stat_tax_rates_2 = []

    for ticker in beta_results["Ticker"]:
        code = get_country_code_a1(ticker)
        country_list_2.append(code)

    beta_results["Country code_2"] = country_list_2

    for ticker in beta_results["Ticker"]:
        stat_rate = get_stat_tax_rate(ticker)
        stat_tax_rates_2.append(stat_rate)

    beta_results["Statutory tax rate"] = stat_tax_rates_2
    return  beta_results

def closest_date(ticker: str, end_date: str):
    """Find closest date relative to the valuation date in yfinance financials"""
    val_date = pd.Timestamp(end_date)
    dates = pd.to_datetime(yf.Ticker(ticker).balance_sheet.columns)
    min_diff = abs(dates - val_date).argmin()
    dates = dates.tolist()
    return dates[min_diff].strftime("%Y-%m-%d")

def get_d_e_ratio(ticker: str, end_date: str):
    """Calculates D/E ratio for given ticker from yfinance"""
    date = closest_date(ticker, end_date)
    bs = yf.Ticker(ticker).balance_sheet
    total_debt = bs.loc["Total Debt", date]
    total_equity = bs.loc["Stockholders Equity", date]
    d_e_ratio = total_debt / total_equity
    return d_e_ratio

def get_eff_tax_r(ticker: str):
    """Calculates effective tax ratio for given ticker from yfinance"""
    fin = yf.Ticker(ticker).financials
    tax_prov = fin.loc["Tax Provision"].dropna().to_list()
    pretax_inc = fin.loc["Pretax Income"].dropna().to_list()
    eff_t_rate = [a / b for a, b in zip(tax_prov, pretax_inc)]
    avg_tax = sum(eff_t_rate) / len(eff_t_rate)
    return avg_tax

def get_country_code_a1(ticker):
    """Find the alpha_3 style country code for given ticker"""
    info = yf.Ticker(ticker).info
    country = info["country"]
    country_search = pycountry.countries.get(name=country)
    if country_search is None:
        raise ValueError(f"Country not found for {country}")
    country_code = country_search.alpha_3
    return country_code

def get_country_code_a2(ticker):
    """Find the alpha_3 style country code for given ticker"""
    info = yf.Ticker(ticker).info
    country = info["country"]
    country_search = pycountry.countries.get(name=country)
    if country_search is None:
        raise ValueError(f"Country not found for {country}")
    country_code = country_search.alpha_2
    return country_code

def get_stat_tax_rate(ticker):
    """Searches the relevant statutory tax rate for given ticker from a downloaded OECD database"""
    country_code = get_country_code_a1(ticker)
    data = pd.read_excel("./data/OECD_statutory_tax_rates/oecd_rates.xlsx", usecols="B:C", names=["country_code","tax_rate"])
    statutory_tax_rates_dict = dict(zip(data["country_code"], data["tax_rate"]))
    return statutory_tax_rates_dict[country_code]

def unlevered_beta(beta_adjustment:str, beta_results:pd.DataFrame, peer_group_beta_method:str):
    if beta_adjustment == "none":
        applied_beta = "Raw Betas"
    elif beta_adjustment == "blume":
        applied_beta = "Blume adj. beta"
    elif beta_adjustment == "vasicek":
        applied_beta = "Vasicek adj. beta"
    else:
        raise ValueError("Beta adjustment must be either 'none' / 'blume' / 'vasicek'")

    unlevered_beta_list = []

    for ticker in beta_results["Ticker"]:
        levered_b = beta_results.loc[beta_results["Ticker"] == ticker, applied_beta].item()
        tax_rate = beta_results.loc[beta_results["Ticker"] == ticker, "Statutory tax rate"].item()
        peer_d_e_ratio = beta_results.loc[beta_results["Ticker"] == ticker, "D/E ratio"].item()
        unlevered_beta = levered_b /(1+(1-tax_rate)*peer_d_e_ratio)
        unlevered_beta_list.append(unlevered_beta)

    beta_results["Unlevered beta"] = unlevered_beta_list

    if peer_group_beta_method == "average":
        peer_group_beta = beta_results["Unlevered beta"].mean()
    elif peer_group_beta_method == "median":
        peer_group_beta = beta_results["Unlevered beta"].median()
    else:
        raise ValueError("Peer group beta method must be either 'average' or 'median'")

    return peer_group_beta

def get_target_levered(target:str, end_date:str, peer_group_beta: float):
    target_country_code = get_country_code_a1(target)
    target_tax_rate = get_stat_tax_rate(target)
    target_d_e = get_d_e_ratio(target, end_date)
    target_relevered_beta = peer_group_beta * (1 + (1- target_tax_rate) * target_d_e)
    return target_relevered_beta

def target_rf(target:str, BASE_STR_1:str, BASE_STR_2:str, start_date:str, end_date:str, rf_lookback:int):
    target_rf_code = get_country_code_a2(target)
    fred_rf_code = BASE_STR_1 + target_rf_code + BASE_STR_2
    rf_df = fred.get_series(fred_rf_code, observation_end=end_date, observation_start=start_date)
    rf_rate = rf_df.tail(rf_lookback).mean()
    return rf_rate

def get_rating_spread_series(rating_spread_series: dict, start_date: str, end_date: str):
    spread_data = {}
    for rating, code in rating_spread_series.items():
        spread_data[rating] = (fred.get_series(code, observation_end=end_date, observation_start=start_date)).resample("ME").mean()
    return pd.DataFrame(spread_data)

def interpolate_spreads(spread_df: pd.DataFrame):
    notches = [
        (1, "AA+"), (3, "AA-"), (4, "A+"), (6, "A-"),
        (7, "BBB+"), (9, "BBB-"), (10, "BB+"), (12, "BB-"),
        (13, "B+"), (15, "B-"),
    ]
    df = spread_df.copy()
    for pos, label in notches:
        df.insert(pos, label, np.nan)
    return df.interpolate(axis=1)

def get_target_spread(interpolated: pd.DataFrame, rating: str, lookback: int):
    target_spreads = interpolated [rating]
    debt_spread = (target_spreads.tail(lookback).mean()) / 100
    return debt_spread