"""Page 7 · Delta-Hedged P&L — the economics of selling vol and hedging delta."""
import streamlit as st

from utils.state import require_data
from engine.core import svi_implied_vol
from engine.strategy import simulate_delta_hedged_pnl
from engine import viz

st.set_page_config(layout="wide", page_title="Vol Desk", page_icon="📈")
require_data()

meta = st.session_state["meta"]
surface = st.session_state["surface"]
r, q, spot = meta["r"], meta["q"], meta["spot"]

st.title("⚖️ Delta-Hedged P&L")
st.markdown("Sell an option at its **implied** vol, then delta-hedge it while the "
            "underlying actually moves at the **realized** vol. Short vol collects "
            "theta and pays gamma — net positive when implied > realized.")

expiries = sorted(surface.keys())
c = st.columns(6)
dte = c[0].selectbox("Expiry (d)", expiries, index=min(2, len(expiries) - 1))
s = surface[dte]
T, fwd = s["T"], s["forward"]
atm_iv = float(svi_implied_vol(0.0, T, s["params"]))
strike_mode = c[1].radio("Strike", ["ATM", "Custom"], horizontal=True)
K = fwd if strike_mode == "ATM" else c[1].number_input(
    "K", min_value=1.0, value=float(round(fwd)), step=1.0)
option = c[2].radio("Type", ["call", "put"], horizontal=True)
pos_label = c[3].radio("Position", ["Short (−1)", "Long (+1)"], horizontal=True)
position = -1.0 if pos_label.startswith("Short") else 1.0
iv_impl = c[4].slider("Implied vol", 0.05, 1.0, round(atm_iv, 3), 0.005)
iv_real = c[5].slider("Realized vol", 0.05, 1.0, round(atm_iv * 0.85, 3), 0.005)

cc = st.columns(2)
n_steps = cc[0].slider("Hedge steps", 21, 504, 252, 21)
rehedge_every = cc[1].slider("Rehedge every (steps)", 1, 21, 1)

path, attr = simulate_delta_hedged_pnl(
    spot, K, T, r, q, iv_impl, iv_real, option=option, position=position,
    n_steps=n_steps, rehedge_every=rehedge_every, seed=0)

k = st.columns(6)
k[0].metric("Premium", f"{attr['premium']:+.2f}")
k[1].metric("Theta P&L", f"{attr['theta_pnl']:+.2f}")
k[2].metric("Gamma P&L", f"{attr['gamma_pnl']:+.2f}")
k[3].metric("Vega P&L", f"{attr['vega_pnl']:+.2f}")
k[4].metric("Hedge error", f"{attr['hedge_error']:+.2f}")
k[5].metric("Total P&L", f"{attr['total_pnl']:+.2f}")

st.plotly_chart(viz.pnl_waterfall(attr), use_container_width=True)
st.plotly_chart(viz.hedge_path(path), use_container_width=True)

with st.expander("💬 What an interviewer asks here"):
    st.markdown(
        "- **Where does short-vol P&L come from?** You collect theta each step and "
        "pay `½·Γ·(ΔS)²` on every move. If implied > realized, theta wins on average.\n"
        "- **What is hedge error?** The cost of hedging discretely instead of "
        "continuously — it shrinks as you rehedge more often (and pay more cost).\n"
        "- **Why is vega P&L ~0 here?** The implied mark is held fixed; vega only "
        "bites if you also move the surface (a separate risk).")
