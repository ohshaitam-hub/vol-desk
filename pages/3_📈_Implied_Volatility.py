"""Page 3 · Implied Volatility — invert market prices to IV and show the smiles."""
import streamlit as st

from utils.state import require_data
from engine.core import implied_vol
from engine import viz

st.set_page_config(layout="wide", page_title="Vol Desk", page_icon="📈")
require_data()

meta = st.session_state["meta"]
iv_panel = st.session_state["iv_panel"]
r, q, spot = meta["r"], meta["q"], meta["spot"]

st.title("📈 Implied Volatility")
st.markdown("Every quoted mid-price is inverted to a Black–Scholes implied vol "
            "with a robust Brent solver, then plotted against log-moneyness "
            "`ln(K/F)` — the raw market smile before any model fit.")

expiries = sorted(iv_panel["expiry_dte"].unique())
dte = st.selectbox("Expiry (days to expiry)", expiries)
g = iv_panel[iv_panel["expiry_dte"] == dte]

c = st.columns(3)
c[0].metric("Quotes in slice", len(g))
c[1].metric("ATM IV (nearest k≈0)",
            f"{g.iloc[(g['log_moneyness'].abs()).argmin()]['iv']*100:.2f}%")
c[2].metric("Skew (25Δ proxy)",
            f"{(g['iv'].max()-g['iv'].min())*100:.2f} vp")

st.plotly_chart(viz.iv_market_scatter(iv_panel, dte), use_container_width=True)

st.dataframe(
    g[["type", "strike", "log_moneyness", "iv", "mid", "volume"]]
    .assign(iv_pct=(g["iv"] * 100).round(2))
    .round({"log_moneyness": 4, "mid": 2}),
    use_container_width=True, height=300)

st.subheader("Single-option IV calculator")
cc = st.columns(4)
px = cc[0].number_input("Option price", min_value=0.0, value=10.0, step=0.5)
strike = cc[1].number_input("Strike", min_value=1.0, value=float(round(spot)), step=1.0)
T_in = cc[2].number_input("Maturity (yrs)", min_value=0.01, value=float(dte / 365), step=0.01)
typ = cc[3].radio("Type", ["call", "put"], horizontal=True)
iv_calc = implied_vol(px, spot, strike, T_in, r, q, typ)
st.metric("Implied volatility",
          f"{iv_calc*100:.2f}%" if iv_calc == iv_calc else "n/a (outside no-arb bounds)")

with st.expander("💬 What an interviewer asks here"):
    st.markdown(
        "- **Why can IV be NaN?** The price violated no-arbitrage bounds "
        "(below intrinsic / above the discounted underlying) or the root wasn't "
        "bracketed — the solver refuses to invent a vol from a bad quote.\n"
        "- **Why mid-price?** Bid/ask each embed a spread; the mid is the least-biased "
        "single point for inversion.\n"
        "- **Smile vs skew?** Equity indices show a downward skew (OTM puts bid for "
        "crash protection); a symmetric U is a 'smile'.")
