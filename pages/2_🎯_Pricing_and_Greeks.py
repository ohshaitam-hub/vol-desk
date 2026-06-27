"""Page 2 · Pricing & Greeks — interactive Black–Scholes pricer and Greek intuition."""
import streamlit as st

from utils.state import require_data
from engine.core import bs_price, bs_greeks
from engine import viz

st.set_page_config(layout="wide", page_title="Vol Desk", page_icon="📈")
require_data()

meta = st.session_state["meta"]
r, q = meta["r"], meta["q"]
spot = meta["spot"]

st.title("🎯 Pricing & Greeks")
st.markdown("Closed-form Black–Scholes price and the full Greek set. Move the "
            "controls — every chart recomputes live from `engine.core`.")

c = st.columns(6)
S = c[0].slider("Spot S", float(0.5 * spot), float(1.5 * spot), float(spot))
K = c[1].slider("Strike K", float(0.5 * spot), float(1.5 * spot), float(round(spot)))
T = c[2].slider("Maturity T (yrs)", 0.02, 2.0, 0.25, 0.01)
sigma = c[3].slider("Vol σ", 0.05, 1.0, 0.20, 0.01)
option = c[4].radio("Type", ["call", "put"], horizontal=True)
r = c[5].number_input("r", value=float(r), step=0.005, format="%.3f")

price = float(bs_price(S, K, T, r, sigma, q, option))
g = bs_greeks(S, K, T, r, sigma, q, option)

k = st.columns(6)
k[0].metric("Price", f"{price:.3f}")
k[1].metric("Delta", f"{float(g['delta']):.3f}")
k[2].metric("Gamma", f"{float(g['gamma']):.4f}")
k[3].metric("Vega", f"{float(g['vega']):.3f}")
k[4].metric("Theta / day", f"{float(g['theta'])/365:.3f}")
k[5].metric("Rho", f"{float(g['rho']):.3f}")

st.plotly_chart(viz.price_vs_spot(K, T, r, sigma, q, option, S),
                use_container_width=True)
st.plotly_chart(viz.greeks_grid(K, T, r, sigma, q, option, S),
                use_container_width=True)

if st.toggle("Show payoff at expiry"):
    st.plotly_chart(viz.payoff_at_expiry(K, option, S, premium=price,
                    position=1.0), use_container_width=True)

with st.expander("💬 What an interviewer asks here"):
    st.markdown(
        "- **Sign of theta vs gamma?** A long option is long gamma / short theta — "
        "you pay time decay to own convexity. Short flips both.\n"
        "- **Why is vega largest ATM and for long maturities?** Vega ∝ S·φ(d1)·√T, "
        "peaking near the forward and growing with √T.\n"
        "- **Per-day theta?** The engine returns per-year theta; divide by 365 for "
        "the daily bleed a trader actually watches.")
