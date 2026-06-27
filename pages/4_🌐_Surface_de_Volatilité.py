"""Page 4 · Surface de volatilité — raw-SVI par échéance, surface 3D interactive."""
import numpy as np
import pandas as pd
import streamlit as st

from utils.state import require_data, lesson, keypoints
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

lesson("""
**À quoi sert cette page ?**
La page 3 montrait le smile d'**une seule** échéance. Ici on rassemble **toutes** les
échéances en une seule **surface 3D** : la volatilité implicite pour chaque strike
(largeur) et chaque maturité (profondeur). C'est la **carte de référence** du desk —
tout le reste de l'app s'appuie dessus.

Comme les points de marché sont bruités, on les **lisse** avec un modèle appelé
**SVI** : 5 paramètres par échéance qui décrivent la forme du smile. Ajuster ces
paramètres pour coller aux données, c'est la **calibration**.

**Les mots :**
- **Surface de volatilité** : la VI en fonction du strike *et* de la maturité, en 3D.
- **SVI** : un modèle standard et parcimonieux (5 paramètres) pour décrire un smile.
- **Calibration / fit** : régler les paramètres pour coller aux points de marché.
- **RMSE** : l'erreur moyenne du fit (en *points de vol*) — plus c'est petit, mieux
  le modèle colle.

**Comment l'utiliser :** fais **tourner la surface 3D** à la souris. En dessous, le
détail du fit par échéance (marché vs courbe SVI) et le tableau des paramètres.
""")

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

keypoints(
    "- **SVI** (5 paramètres) est préféré à une spline : parcimonieux, forme propre "
    "en variance totale, conditions de non-arbitrage connues — une spline sur-ajuste "
    "et arbitrage facilement.\n"
    "- Les **5 paramètres** : `a` niveau, `b` pente des ailes, `ρ` skew, `m` "
    "translation horizontale, `σ` courbure ATM.\n"
    "- Le **multi-départs** est nécessaire car la surface des moindres carrés SVI est "
    "non-convexe (sinon on tombe dans de mauvais minima locaux).\n"
    "- Un **RMSE faible** (< 0,5 point de vol) indique que le modèle colle bien au "
    "marché.")
