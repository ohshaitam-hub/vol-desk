"""Page 5 · No-Arbitrage & Risk-Neutral Density — prove the surface is tradeable."""
import streamlit as st

from utils.state import require_data, push_score
from engine.data import surface_diagnostics, calendar_arbitrage
from engine import viz

st.set_page_config(layout="wide", page_title="Vol Desk", page_icon="📈")
require_data()

meta = st.session_state["meta"]
surface = st.session_state["surface"]

st.title("✅ No-Arbitrage & Risk-Neutral Density")
st.markdown("A surface is only tradeable if it is **static-arbitrage-free**: the "
            "Breeden–Litzenberger risk-neutral density must stay non-negative "
            "(no butterfly arbitrage) and total variance must be non-decreasing "
            "in maturity (no calendar arbitrage).")

diag = surface_diagnostics(surface, meta["r"])
cal = calendar_arbitrage(surface)
butterfly_ok = bool(diag["butterfly_ok"].all()) if len(diag) else False
cal_viol = int(cal["violations"].sum()) if len(cal) else 0
push_score(butterfly_ok=butterfly_ok, calendar_violations=cal_viol)

c = st.columns(3)
c[0].metric("Butterfly-arbitrage-free", "✅ Yes" if butterfly_ok else "❌ No")
c[1].metric("Calendar violations", cal_viol)
c[2].metric("Mean fit RMSE", f"{diag['fit_rmse'].mean()*100:.2f} vp" if len(diag) else "—")

expiries = sorted(surface.keys())
sel = st.multiselect("Expiries to plot", expiries, default=expiries)
st.plotly_chart(viz.risk_neutral_density(surface, meta, sel), use_container_width=True)

st.subheader("Per-slice diagnostics (Breeden–Litzenberger)")
disp = diag.copy()
disp["butterfly_ok"] = disp["butterfly_ok"].map({True: "✅", False: "❌"})
st.dataframe(disp.set_index("expiry_dte"), use_container_width=True)

st.subheader("Calendar-spread check")
if len(cal):
    sty = cal.style.apply(
        lambda row: ["background-color: rgba(240,97,122,0.25)" if row["violations"] > 0
                     else "" for _ in row], axis=1)
    st.dataframe(sty, use_container_width=True)
else:
    st.info("Need at least two expiries for the calendar check.")

with st.expander("💬 What an interviewer asks here"):
    st.markdown(
        "- **Breeden–Litzenberger?** `f(K)=e^{rT}·∂²C/∂K²` — the second strike "
        "derivative of the call price *is* the risk-neutral density. Negative "
        "anywhere ⇒ a butterfly you could sell for free money.\n"
        "- **Calendar condition?** Total implied variance `w(k,T)` must be "
        "non-decreasing in T at every k, else a calendar spread is arbitrage.\n"
        "- **Why prove it before trading?** Relative-value signals off an "
        "arbitraging surface are meaningless.")
