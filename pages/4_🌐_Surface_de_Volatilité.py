"""Page 4 · Surface de volatilité — raw-SVI par échéance, surface 3D interactive."""
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
surface = st.session_state["surface"]      # fit caché, pondéré gaussien

st.title("🌐 Surface de volatilité (SVI)")
st.markdown("Une slice raw-SVI `w(k)=a+b[ρ(k−m)+√((k−m)²+σ²)]` est calibrée par "
            "échéance (multi-départs L-BFGS-B). La surface 3D est **rotative et "
            "zoomable** — glisse pour orbiter, scrolle pour zoomer.")

st.plotly_chart(viz.vol_surface_3d(surface, meta), use_container_width=True)

st.subheader("Ajustement du smile par échéance")
cc = st.columns([3, 2])
expiries = sorted(surface.keys())
sel = cc[0].multiselect("Échéances", expiries, default=expiries)
ntm = cc[1].toggle("Pondération près de la monnaie", value=True,
                   help="Activé : sous-pondère les ailes illiquides (le fit de "
                        "production). Désactivé : pondère tous les points également "
                        "(re-fit en direct).")

# Construit la surface affichée en respectant le toggle de pondération.
disp = {}
for d in sel:
    if ntm:
        disp[d] = surface[d]                 # fit de production caché
        continue
    g = iv_panel[iv_panel["expiry_dte"] == d]
    if len(g) < 5:
        continue
    k = g["log_moneyness"].values
    iv = g["iv"].values
    T = float(g["T"].iloc[0])
    p = calibrate_svi(k, iv, T, weights=None)        # re-fit équipondéré
    rmse = float(np.sqrt(np.mean((svi_implied_vol(k, T, p) - iv) ** 2)))
    disp[d] = dict(params=p, T=T, forward=float(g["forward"].iloc[0]),
                   rmse=rmse, n=len(g))

if disp:
    st.plotly_chart(viz.smiles_grid(iv_panel, disp, sel), use_container_width=True)

    rows = []
    for d in sorted(disp):
        s = disp[d]; p = s["params"]
        rows.append(dict(echeance_j=d, T=round(s["T"], 3), a=round(p.a, 5),
                         b=round(p.b, 4), rho=round(p.rho, 4), m=round(p.m, 4),
                         sigma=round(p.sigma, 4), rmse_pv=round(s["rmse"] * 100, 3),
                         n=s["n"]))
    params_df = pd.DataFrame(rows).set_index("echeance_j")
    c = st.columns(3)
    c[0].metric("Échéances ajustées", len(disp))
    c[1].metric("RMSE moyen", f"{params_df['rmse_pv'].mean():.2f} pv")
    c[2].metric("RMSE max", f"{params_df['rmse_pv'].max():.2f} pv")
    st.subheader("Paramètres SVI ajustés")
    st.dataframe(params_df, use_container_width=True)
else:
    st.info("Sélectionne au moins une échéance.")

with st.expander("💬 Ce qu'un recruteur demande ici"):
    st.markdown(
        "- **Pourquoi SVI et pas une spline ?** SVI est parcimonieux (5 paramètres), "
        "a une forme propre en variance totale, et des conditions de non-arbitrage "
        "connues — les splines sur-ajustent et arbitragent facilement.\n"
        "- **Que fait chaque paramètre ?** `a` niveau, `b` pente des ailes, `ρ` "
        "skew, `m` translation horizontale, `σ` courbure ATM.\n"
        "- **Pourquoi multi-départs ?** La surface des moindres carrés SVI est "
        "non-convexe ; des redémarrages aléatoires évitent les mauvais minima locaux.")
