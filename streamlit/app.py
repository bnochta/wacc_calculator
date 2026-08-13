import hashlib
import json
import streamlit as st
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from functions import *

st.set_page_config(layout="wide")

left_col, right_col = st.columns(2)

with left_col:
    st.title("WACC Calculator")
    run_clicked = st.button("Run Calcuation")
    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)

with right_col:
    st.latex(r'''WACC = \frac{E}{D+E} \cdot R_e \;+\; \frac{D}{D+E} \cdot R_d \cdot (1 - T_c)''')
    st.latex(r'''R_e = r_f + \beta_{relevered} \cdot ERP + SP + CSRP ''')
    st.latex(r''' R_d = r_f + Debt \ Spread''')

with right_col:
    st.header("Results")
    results_placeholder = st.empty()

with left_col:
    st.header("Inputs")
    with st.container(border=True):
        st.write("Tickers")
        col1, col2, col3 = st.columns(3)
        target_ticker = col1.text_input(label="Target ticker", placeholder="Enter ticker symbol")
        benchmark = col2.text_input(label="Benchmark ticker", placeholder="Enter ticker symbol")
        peer_group = col3.multiselect(label="Peer Group", options=[], accept_new_options=True,
                                      placeholder="Select Peer Group tickers")
        col1.write("Only works with active, publicly listed tickers (data from Yahoo Finance).")
        col2.markdown("S&P500 - ^GSPCI")
        col2.markdown("MSCI WORLD - URTH")
        col2.markdown("MSCI ACWI - ACWI")

    with st.container(border=True):
        st.write("Return Calculation")
        end_date = str(st.date_input(label="Valuation Date"))
        col1, col2, col3 = st.columns(3)
        start_date = str(col1.date_input(label="Query Start Date"))
        interval = col2.selectbox(label="Interval", options=["1d", "5d", "1wk", "1mo", "3mo"])
        return_calc = col3.selectbox(label="Return Calculation Method", options=["Linear", "Logarithmic"])

    with st.container(border=True):
        st.write("Beta Calculation")
        col1, col2 = st.columns(2)
        beta_adjustment = col1.selectbox(label="Beta Adjustment Method", options=["None", "Blume", "Vasicek"])
        peer_group_beta_method = col2.selectbox(label="Peer Beta Method", options=["Average", "Median"])

    with st.container(border=True):
        st.write("Other WACC Indicies")
        col1, col2 = st.columns(2)
        target_longt_sp_rating = col1.selectbox(label="S&P Long-Term Rating",
                                                options=["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB",
                                                         "BBB-", "BB+", "BB", "BB-", "B+", "B", "B-", "CCC or lower"])

        debt_spread_lookback_months = col1.number_input("Debt-spread lookback months", value=1, min_value=1, step=1,
                                                        format="%d")  # from valuation date or latest available data

        rf_lookback_months = col1.number_input("Risk-free rate lookback months", value=1, min_value=1, step=1,
                                               format="%d")  # from valuation date or latest available data

        equity_risk_premium = (col2.number_input("Equity Risk Premium (%)", value=5.5, min_value=0.0, step=0.1,
                                                 format="%.1f")) / 100

        size_premium = (col2.number_input("Size Premium (%)", value=0.0, min_value=0.0, step=0.1, format="%.1f")) / 100

        comp_spec_risk_premium = (col2.number_input("Company Specific Risk Premium (%)", value=0.0, min_value=0.0,
                                                    step=0.1, format="%.1f")) / 100



current_inputs = {
    "target_ticker": target_ticker,
    "benchmark": benchmark,
    "peer_group": sorted(peer_group),
    "start_date": start_date,
    "end_date": end_date,
    "interval": interval,
    "return_calc": return_calc,
    "beta_adjustment": beta_adjustment,
    "peer_group_beta_method": peer_group_beta_method,
    "target_longt_sp_rating": target_longt_sp_rating,
    "debt_spread_lookback_months": debt_spread_lookback_months,
    "rf_lookback_months": rf_lookback_months,
    "equity_risk_premium": equity_risk_premium,
    "size_premium": size_premium,
    "comp_spec_risk_premium": comp_spec_risk_premium,
}

current_hash = hashlib.md5(json.dumps(current_inputs, sort_keys=True, default=str).encode()).hexdigest()

if run_clicked:
    if not target_ticker or not benchmark or not peer_group:
            st.error("Fill out the Target, Benchmark and Peer Group before the calculation.")
    else:
        with st.spinner("Calculating WACC..."):
            ticker_package = peer_group + [benchmark]
            data_package = download_data(tickers= ticker_package, start_date= start_date, end_date= end_date, interval= interval)
            save_data(data = data_package, benchmark= benchmark, peer_group= peer_group, start_date= start_date, end_date= end_date)
            close_data = extract_col(data = data_package, field= "Close")

            close_data = basic_cleaning(close_data=close_data)
            
            return_data = log_return_calc(return_calc=return_calc, close_data= close_data)

            beta_results = beta_regression(peer_group=peer_group, return_data=return_data, benchmark=benchmark)

            beta_adj = beta_adjustments(beta_results)

            beta_res = append_d_e_ratio(beta_results=beta_adj, end_date= end_date)

            beta_results = append_tax_rates(beta_results=beta_res)

            peer_group_beta = unlevered_beta(beta_adjustment=beta_adjustment, beta_results=beta_results, peer_group_beta_method=peer_group_beta_method)

            target_levered_beta = get_target_levered(target=target_ticker, end_date=end_date, peer_group_beta=peer_group_beta)

            target_rf_rate = (target_rf(target=target_ticker, BASE_STR_1=BASE_STRING_1, BASE_STR_2=BASE_STRING_2,start_date=start_date, end_date=end_date, rf_lookback=rf_lookback_months)) / 100

            spread_series = get_rating_spread_series(rating_spread_series=RATING_SPREAD_SERIES, start_date=start_date, end_date=end_date)

            interpolated_series = interpolate_spreads(spread_series)

            target_spread = get_target_spread(interpolated_series, target_longt_sp_rating, lookback=debt_spread_lookback_months)

            d_e = get_d_e_ratio(target_ticker, end_date= end_date)

            target_tax = get_stat_tax_rate(target_ticker)

            wacc = get_wacc(target_ticker=target_ticker, end_date=end_date, rf=target_rf_rate,
                            debt_spread=target_spread, relevered_beta=target_levered_beta, erp=equity_risk_premium,
                            sp=size_premium, csrp=comp_spec_risk_premium)

            st.session_state["wacc_results"] = {
                "beta_results": beta_results,
                "peer_group_beta": peer_group_beta,
                "target_levered_beta": target_levered_beta,
                "target_rf_rate": target_rf_rate,
                "target_spread": target_spread,
                "d_e": d_e,
                "target_tax": target_tax,
                "wacc": wacc,
            }
            st.session_state["wacc_input_hash"] = current_hash

if "wacc_results" in st.session_state:
    res = st.session_state["wacc_results"]

    if st.session_state["wacc_input_hash"] != current_hash:
        st.warning("Stale result! - Run calculation!")

    with results_placeholder.container():
        st.markdown("""<style>.big-font {font-size:24px !important; font-style:italic;} </style>""", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        col1.subheader(f"WACC = {res['wacc']:.2%}")
        col1, col2, col3 = st.columns(3)
        col1.markdown(f"##  ")
        col1.markdown(f"### Weight")
        col1.markdown(f"### Risk-free rate")
        col1.markdown(f"### Debt spread")
        col1.markdown(f"### Stat. tax rate")
        col1.markdown(f"### Re-levered beta")
        col1.markdown(f"### ERP")
        col1.markdown(f"### SP")
        col1.markdown(f"### CSRP")

        col2.markdown(f"## Cost of Equity")
        col2.markdown(f"### {(1 / (1 + res['d_e'])):.2f}")
        col2.markdown(f"### {res['target_rf_rate']:.2%}")
        col2.markdown(f"###     -")
        col2.markdown(f"###     -")
        col2.markdown(f"### {res['target_levered_beta']:.3}")
        col2.markdown(f"### {equity_risk_premium * 100}%")
        col2.markdown(f"### {size_premium * 100}%")
        col2.markdown(f"### {comp_spec_risk_premium * 100}%")
        col2.divider()
        col2.markdown(f"### {(1 / (1 + res['d_e'])) * (res['target_rf_rate'] + res['target_levered_beta'] * equity_risk_premium + size_premium + comp_spec_risk_premium):.2%}")

        col3.markdown(f"## Cost of Debt")
        col3.markdown(f"### {(1 - (1 / (1 + res['d_e']))):.2f}")
        col3.markdown(f"### {res['target_rf_rate']:.2%}")
        col3.markdown(f"### {res['target_spread']:.2%}")
        col3.markdown(f"### {res['target_tax']:.2%}")
        col3.markdown(f"###      ")
        col3.markdown(f"###      ")
        col3.markdown(f"###      ")
        col3.markdown(f"###      ")
        col3.divider()
        col3.markdown(f"### {(1 -(1 / (1 + res['d_e']))) * (res['target_rf_rate'] + res['target_spread']) * (1- res['target_tax']):.2%}")






