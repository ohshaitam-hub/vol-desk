"""
app.py — VOL DESK · Page 1 · Market Data & Cockpit Home
Landing page: orients the user, loads the data foundation every other page
depends on, and shows the live surface KPIs as the cockpit "hero".
"""
import streamlit as st

from utils.state import render_sidebar, load_data, source_badge

st.set_page_config(layout="wide", page_title="Vol Desk", page_icon="📈")

render_sidebar()

# Auto-load on first visit so the cockpit is populated immediately (synthetic
# fallback guarantees this never blocks, even with no network / no API keys).
if not st.session_state.get("data_ready"):
    with st.spinner("Loading market data & fitting the volatility surface…"):
        load_data()

meta = st.session_state["meta"]
iv_panel = st.session_state["iv_panel"]
surface = st.session_state["surface"]

# ----------------------------------------------------------------------
# Hero
# ----------------------------------------------------------------------
st.title("📈 Vol Desk — Options Volatility & Market-Making Cockpit")
st.markdown(
    "An end-to-end options-research desk: it pulls an options chain, builds an "
    "**arbitrage-free SVI volatility surface**, validates it, screens **relative "
    "value**, simulates **delta-hedged P&L** and the **variance risk premium**, and "
    "quotes as an **Avellaneda–Stoikov market maker**. Live Yahoo Finance when "
    "available, deterministic synthetic surface otherwise — it always runs.")

st.markdown(f"**Data source:** {source_badge()}  ·  "
            f"as-of `{meta['asof']:%Y-%m-%d %H:%M UTC}`")

# ----------------------------------------------------------------------
# 9-step workflow map
# ----------------------------------------------------------------------
st.subheader("Workflow")
dot = """
digraph {
  rankdir=LR; bgcolor="#0d1117";
  node [shape=box style="rounded,filled" fillcolor="#161b22" color="#283039"
        fontcolor="#e6edf3" fontname="monospace" fontsize=10 margin=0.12];
  edge [color="#58a6ff" arrowsize=0.7];
  d1 [label="1 · Market Data"]; d2 [label="2 · Pricing & Greeks"];
  d3 [label="3 · Implied Vol"]; d4 [label="4 · Vol Surface (SVI)"];
  d5 [label="5 · No-Arbitrage"]; d6 [label="6 · Relative Value"];
  d7 [label="7 · Delta-Hedged P&L"]; d8 [label="8 · Variance Risk Prem."];
  d9 [label="9 · Market Making"];
  d1->d2->d3->d4->d5->d6->d7->d8->d9;
}
"""
st.graphviz_chart(dot, use_container_width=True)

# ----------------------------------------------------------------------
# KPI row
# ----------------------------------------------------------------------
c = st.columns(4)
c[0].metric("Spot", f"{meta['spot']:.2f}")
c[1].metric("# expiries fitted", len(surface))
c[2].metric("# clean quotes", len(iv_panel))
c[3].metric("Source", "Live" if meta["source"].startswith("yfinance") else "Synthetic")

# ----------------------------------------------------------------------
# Cleaned IV panel
# ----------------------------------------------------------------------
st.subheader("Cleaned implied-vol panel")
st.caption("Mid-price implied vol and log-moneyness ln(K/F) for every surviving "
           "option after liquidity & no-arbitrage filtering.")
show = iv_panel.copy()
show["iv_%"] = (show["iv"] * 100).round(2)
cols = ["expiry_dte", "type", "strike", "log_moneyness", "iv_%", "mid",
        "bid", "ask", "volume", "open_interest"]
st.dataframe(show[cols].round({"log_moneyness": 4, "mid": 2, "bid": 2, "ask": 2}),
             use_container_width=True, height=380)

with st.expander("💬 What an interviewer asks here"):
    st.markdown(
        "- **Why log-moneyness vs the forward, not strike?** It standardises smiles "
        "across maturities and centres ATM at `k=0` (the forward, not spot).\n"
        "- **Why a synthetic fallback?** A recruiter must be able to open the app "
        "with no API keys and still see a full, arbitrage-free surface.\n"
        "- **What did the cleaning remove?** Crossed/stale quotes, illiquid wings, "
        "and any price outside no-arbitrage bounds (the IV solver returns NaN there).")

with st.expander("🔭 Where a desk takes this next"):
    st.markdown(
        "- **SSVI / eSSVI** global calibration enforcing no static arbitrage across "
        "the *whole* surface (not slice-by-slice).\n"
        "- **Heston / SABR** cross-check and vega hedging **with transaction costs**.\n"
        "- A **live broker feed** (IBKR / Polygon) with Greek & inventory risk limits.\n"
        "- A **multi-name dispersion / skew scanner** with out-of-sample validation.")

st.caption("Navigate the 8 analytical modules from the sidebar →. "
           "This cockpit is the live counterpart of the research notebook (the lab).")
