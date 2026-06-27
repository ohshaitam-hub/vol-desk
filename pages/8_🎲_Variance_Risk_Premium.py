"""Page 8 · Variance Risk Premium — the honest distribution of short-vol outcomes."""
import numpy as np
import streamlit as st
from scipy.stats import skew as scipy_skew

from utils.state import require_data, push_score
from engine.core import svi_implied_vol
from engine.strategy import vrp_monte_carlo
from engine import viz

st.set_page_config(layout="wide", page_title="Vol Desk", page_icon="📈")
require_data()

meta = st.session_state["meta"]
surface = st.session_state["surface"]
r, q, spot = meta["r"], meta["q"], meta["spot"]

st.title("🎲 Variance Risk Premium")
st.markdown("Selling vol pays a premium — but the payoff is **negatively skewed**: "
            "a positive mean with a heavy left tail (the occasional vol blow-up). "
            "This Monte Carlo draws a *stochastic* realized vol per path so the "
            "tail is honest.")


@st.cache_data(show_spinner=True)
def run_vrp(S0, K, T, r, q, iv_impl, iv_real_mean, n_paths, n_steps,
            vol_of_vol, jump_prob, jump_size):
    return vrp_monte_carlo(S0, K, T, r, q, iv_impl, iv_real_mean, option="call",
                           n_paths=n_paths, n_steps=n_steps, vol_of_vol=vol_of_vol,
                           jump_prob=jump_prob, jump_size=jump_size, seed=1)


expiries = sorted(surface.keys())
top = st.columns(4)
dte = top[0].selectbox("Expiry (d)", expiries, index=min(2, len(expiries) - 1))
s = surface[dte]
T, K = s["T"], s["forward"]
atm_iv = float(svi_implied_vol(0.0, T, s["params"]))
iv_impl = top[1].slider("Implied vol (sold at)", 0.05, 1.0, round(atm_iv, 3), 0.005)
iv_real_mean = top[2].slider("Realized vol (mean)", 0.05, 1.0, round(atm_iv * 0.85, 3), 0.005)
vov = top[3].slider("Vol-of-vol", 0.05, 1.0, 0.35, 0.05)

bot = st.columns(4)
jump_prob = bot[0].slider("Jump prob.", 0.0, 0.30, 0.04, 0.01)
jump_size = bot[1].slider("Jump size (vol)", 0.0, 0.30, 0.08, 0.01)
n_paths = bot[2].select_slider("# paths", [500, 1000, 2000, 4000], value=2000)
n_steps = bot[3].select_slider("# steps", [21, 42, 63, 126], value=63)

pnl, rv = run_vrp(spot, K, T, r, q, iv_impl, iv_real_mean, n_paths, n_steps,
                  vov, jump_prob, jump_size)

mean = float(np.mean(pnl)); win = float(np.mean(pnl > 0))
p5 = float(np.percentile(pnl, 5)); p1 = float(np.percentile(pnl, 1))
sk = float(scipy_skew(pnl))
push_score(vrp_mean=mean, vrp_winrate=win, vrp_tail5=p5)

k = st.columns(5)
k[0].metric("Mean P&L", f"{mean:+.2f}")
k[1].metric("Win rate", f"{win*100:.1f}%")
k[2].metric("5% tail", f"{p5:+.2f}")
k[3].metric("1% tail", f"{p1:+.2f}")
k[4].metric("Skew", f"{sk:+.2f}")

st.plotly_chart(viz.vrp_histogram(pnl), use_container_width=True)
if st.toggle("Show simulated realized-vol distribution"):
    st.plotly_chart(viz.realized_vol_histogram(rv), use_container_width=True)

st.info("📌 The **negative skew is the cost of the premium**: most paths win a "
        "little (theta > gamma), a few lose a lot (a vol spike turns short gamma "
        "against you). A high mean win-rate with a fat left tail is the signature "
        "of selling insurance.")

with st.expander("💬 What an interviewer asks here"):
    st.markdown(
        "- **Why is the mean positive?** Implied vol embeds a risk premium over "
        "realized — sellers are paid to warehouse variance risk.\n"
        "- **Why model stochastic realized vol + jumps?** A constant-vol MC hides "
        "the tail; the premium only makes sense against the blow-up risk it pays for.\n"
        "- **How would you size this?** Against the 1–5% tail (CVaR), not the mean — "
        "the left tail is what stops you out.")
