"""Page 9 · Market Making (Avellaneda–Stoikov) + consolidated desk scorecard."""
import numpy as np
import pandas as pd
import streamlit as st

from utils.state import require_data, get_score
from engine.core import svi_implied_vol
from engine.strategy import (avellaneda_stoikov_quotes, simulate_market_making,
                             relative_value_screen, vrp_monte_carlo)
from engine import viz

st.set_page_config(layout="wide", page_title="Vol Desk", page_icon="📈")
require_data()

meta = st.session_state["meta"]
surface = st.session_state["surface"]
iv_panel = st.session_state["iv_panel"]
r, q, spot = meta["r"], meta["q"], meta["spot"]

st.title("🏦 Market Making — Avellaneda–Stoikov")
st.markdown("Inventory-aware optimal quoting: the **reservation price** skews "
            "against current inventory (a long book quotes lower to offload), and "
            "the **spread** widens with risk-aversion γ, volatility σ and horizon. "
            "Order arrivals follow `λ = A·e^(−κδ)`.")

mid_dte = sorted(surface.keys())[len(surface) // 2]
atm_sigma = float(svi_implied_vol(0.0, surface[mid_dte]["T"], surface[mid_dte]["params"]))

c = st.columns(6)
gamma = c[0].slider("γ risk-aversion", 0.01, 1.0, 0.10, 0.01)
kappa = c[1].slider("κ arrival decay", 0.2, 5.0, 1.5, 0.1)
A = c[2].slider("A base intensity", 20.0, 400.0, 140.0, 10.0)
sigma = c[3].slider("σ volatility", 0.05, 1.0, round(atm_sigma, 3), 0.005)
T = c[4].slider("Horizon T (yrs)", 0.1, 2.0, 1.0, 0.1)
n_steps = c[5].select_slider("# steps", [200, 350, 500, 800], value=500)

# Quote-skew snapshot for representative inventories.
skew_rows = []
for inv in (0, 10, -10):
    qd = avellaneda_stoikov_quotes(spot, inv, sigma, T, gamma, kappa)
    skew_rows.append(dict(inventory=inv, reservation=round(qd["reservation"], 3),
                          bid=round(qd["bid"], 3), ask=round(qd["ask"], 3),
                          spread=round(qd["spread"], 3), skew=round(qd["skew"], 3)))
st.subheader("Quote skew vs inventory")
st.dataframe(pd.DataFrame(skew_rows).set_index("inventory"), use_container_width=True)

mm = simulate_market_making(spot, sigma, T=T, n_steps=n_steps, gamma=gamma,
                            kappa=kappa, arrival_A=A, seed=3)
k = st.columns(2)
k[0].metric("Final inventory", f"{mm['inventory'].iloc[-1]:.0f}")
k[1].metric("Final P&L", f"{mm['pnl'].iloc[-1]:+.2f}")
st.plotly_chart(viz.market_making(mm), use_container_width=True)

# ----------------------------------------------------------------------
# Consolidated research scorecard (aggregates prior pages via session_state)
# ----------------------------------------------------------------------
st.markdown("---")
st.subheader("🧮 Consolidated research scorecard")
sc = get_score()

# Fill any gaps so the scorecard is complete even if a page wasn't visited.
if "rv_sell" not in sc:
    rv = relative_value_screen(iv_panel, surface,
                               z_threshold=float(st.session_state.get("cfg_z_threshold", 1.5)))
    vc = rv["signal"].value_counts()
    sc.update(rv_sell=int(vc.get("SELL_VOL", 0)), rv_buy=int(vc.get("BUY_VOL", 0)),
              rv_fair=int(vc.get("FAIR", 0)))


@st.cache_data(show_spinner=False)
def _quick_vrp(spot, K, T, r, q, iv):
    pnl, _ = vrp_monte_carlo(spot, K, T, r, q, iv, iv * 0.85, n_paths=600, n_steps=63)
    return float(np.mean(pnl)), float(np.mean(pnl > 0)), float(np.percentile(pnl, 5))


if "vrp_mean" not in sc:
    s = surface[mid_dte]
    m_, w_, t_ = _quick_vrp(spot, s["forward"], s["T"],
                            r, q, float(svi_implied_vol(0.0, s["T"], s["params"])))
    sc.update(vrp_mean=m_, vrp_winrate=w_, vrp_tail5=t_)

g1 = st.columns(4)
g1[0].metric("Source", "Live" if str(sc.get("source", "")).startswith("yfinance") else "Synthetic")
g1[1].metric("Spot", f"{sc.get('spot', spot):.2f}")
g1[2].metric("# expiries", sc.get("n_expiries", len(surface)))
g1[3].metric("Mean SVI RMSE", f"{sc.get('mean_rmse', float('nan'))*100:.2f} vp")

g2 = st.columns(4)
g2[0].metric("Butterfly-arb-free", "✅" if sc.get("butterfly_ok") else "❌")
g2[1].metric("Calendar violations", sc.get("calendar_violations", 0))
g2[2].metric("RV rich / cheap", f"{sc.get('rv_sell', 0)} / {sc.get('rv_buy', 0)}")
g2[3].metric("VRP mean (win%)", f"{sc.get('vrp_mean', 0):+.2f} ({sc.get('vrp_winrate', 0)*100:.0f}%)")

st.caption(f"VRP 5% tail: {sc.get('vrp_tail5', float('nan')):+.2f}  ·  "
           "Scorecard aggregates every prior module through `st.session_state`.")

with st.expander("💬 What an interviewer asks here"):
    st.markdown(
        "- **What is the reservation price?** The inventory-adjusted fair value the "
        "MM is *indifferent* to trading at: `r = s − q·γ·σ²·(T−t)`.\n"
        "- **Why skew quotes?** To mean-revert inventory — a long book lowers both "
        "quotes to get hit on the offer and lifted less on the bid.\n"
        "- **What sets the optimal spread?** `γσ²(T−t) + (2/γ)ln(1+γ/κ)` — risk "
        "aversion and horizon widen it; deeper liquidity (κ) tightens it.")
