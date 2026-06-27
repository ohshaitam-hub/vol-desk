"""Page 6 · Relative Value — flag options rich/cheap vs the arbitrage-free surface."""
import streamlit as st

from utils.state import require_data, push_score
from engine.strategy import relative_value_screen
from engine import viz

st.set_page_config(layout="wide", page_title="Vol Desk", page_icon="📈")
require_data()

iv_panel = st.session_state["iv_panel"]
surface = st.session_state["surface"]

st.title("💎 Relative Value")
st.markdown("Each option's market IV is compared to the SVI **fair IV**. The "
            "residual is standardised within its expiry (a z-score); contracts "
            "beyond the threshold are flagged statistically **rich (sell)** or "
            "**cheap (buy)** — exactly the lean a market maker quotes around.")

z = st.slider("z-threshold", 0.5, 3.0,
              float(st.session_state.get("cfg_z_threshold", 1.5)), 0.1)
rv = relative_value_screen(iv_panel, surface, z_threshold=z)

counts = rv["signal"].value_counts()
n_sell = int(counts.get("SELL_VOL", 0))
n_buy = int(counts.get("BUY_VOL", 0))
n_fair = int(counts.get("FAIR", 0))
push_score(rv_sell=n_sell, rv_buy=n_buy, rv_fair=n_fair, rv_zthr=z)

c = st.columns(3)
c[0].metric("🔴 SELL_VOL (rich)", n_sell)
c[1].metric("🟢 BUY_VOL (cheap)", n_buy)
c[2].metric("⚪ FAIR", n_fair)

st.plotly_chart(viz.rv_scatter(rv), use_container_width=True)

st.subheader("Flagged contracts")
only_flagged = st.checkbox("Show only flagged (non-FAIR)", value=True)
table = rv[rv["signal"] != "FAIR"] if only_flagged else rv
cols = ["expiry_dte", "type", "strike", "log_moneyness", "iv", "fair_iv",
        "iv_resid", "iv_zscore", "volume", "signal"]
st.dataframe(
    table[cols].assign(
        iv_pct=(table["iv"] * 100).round(2),
        fair_pct=(table["fair_iv"] * 100).round(2))
    .round({"log_moneyness": 4, "iv_resid": 4, "iv_zscore": 2}),
    use_container_width=True, height=340)

with st.expander("💬 What an interviewer asks here"):
    st.markdown(
        "- **Why z-score within each expiry?** Skew/level differ by maturity; "
        "standardising per slice makes 'rich' comparable across the surface.\n"
        "- **Is a high z-score a trade?** No — it's a *candidate*. You'd check "
        "liquidity, borrow, events, and hedge cost before leaning on it.\n"
        "- **Where does the edge come from?** Quoting around a clean fair surface "
        "and being paid to provide liquidity to flow that drifts off it.")
