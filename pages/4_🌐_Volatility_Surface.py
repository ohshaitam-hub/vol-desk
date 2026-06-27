"""Page 4 · Volatility Surface — raw-SVI per expiry, interactive 3D surface."""
import numpy as np
import pandas as pd
import streamlit as st

from utils.state import require_data
from engine.core import calibrate_svi, svi_implied_vol
from engine import viz

st.set_page_config(layout="wide", page_title="Vol Desk", page_icon="📈")
require_data()

meta = st.session_state["meta"]
iv_panel = st.session_state["iv_panel"]
surface = st.session_state["surface"]      # cached, gaussian-weighted fit

st.title("🌐 Volatility Surface (SVI)")
st.markdown("A raw-SVI slice `w(k)=a+b[ρ(k−m)+√((k−m)²+σ²)]` is calibrated per "
            "expiry (multi-start L-BFGS-B). The 3D surface is **rotatable and "
            "zoomable** — drag to orbit, scroll to zoom.")

st.plotly_chart(viz.vol_surface_3d(surface, meta), use_container_width=True)

st.subheader("Per-expiry smile fit")
cc = st.columns([3, 2])
expiries = sorted(surface.keys())
sel = cc[0].multiselect("Expiries", expiries, default=expiries)
ntm = cc[1].toggle("Near-the-money weighting", value=True,
                   help="On: down-weight illiquid wings (the production fit). "
                        "Off: equal-weight every quote (re-fits live).")

# Build the display surface honouring the weighting toggle.
disp = {}
for d in sel:
    if ntm:
        disp[d] = surface[d]                 # cached production fit
        continue
    g = iv_panel[iv_panel["expiry_dte"] == d]
    if len(g) < 5:
        continue
    k = g["log_moneyness"].values
    iv = g["iv"].values
    T = float(g["T"].iloc[0])
    p = calibrate_svi(k, iv, T, weights=None)        # equal-weight refit
    rmse = float(np.sqrt(np.mean((svi_implied_vol(k, T, p) - iv) ** 2)))
    disp[d] = dict(params=p, T=T, forward=float(g["forward"].iloc[0]),
                   rmse=rmse, n=len(g))

if disp:
    st.plotly_chart(viz.smiles_grid(iv_panel, disp, sel), use_container_width=True)

    rows = []
    for d in sorted(disp):
        s = disp[d]; p = s["params"]
        rows.append(dict(expiry_dte=d, T=round(s["T"], 3), a=round(p.a, 5),
                         b=round(p.b, 4), rho=round(p.rho, 4), m=round(p.m, 4),
                         sigma=round(p.sigma, 4), rmse_vp=round(s["rmse"] * 100, 3),
                         n=s["n"]))
    params_df = pd.DataFrame(rows).set_index("expiry_dte")
    c = st.columns(3)
    c[0].metric("Expiries fitted", len(disp))
    c[1].metric("Mean RMSE", f"{params_df['rmse_vp'].mean():.2f} vp")
    c[2].metric("Max RMSE", f"{params_df['rmse_vp'].max():.2f} vp")
    st.subheader("Fitted SVI parameters")
    st.dataframe(params_df, use_container_width=True)
else:
    st.info("Select at least one expiry.")

with st.expander("💬 What an interviewer asks here"):
    st.markdown(
        "- **Why SVI and not a spline?** SVI is parsimonious (5 params), has a "
        "clean total-variance form, and known no-arbitrage conditions — splines "
        "overfit and arbitrage easily.\n"
        "- **What does each parameter do?** `a` level, `b` wing slope, `ρ` skew, "
        "`m` horizontal shift, `σ` ATM curvature.\n"
        "- **Why multi-start?** The SVI least-squares surface is non-convex; random "
        "restarts avoid bad local minima.")
