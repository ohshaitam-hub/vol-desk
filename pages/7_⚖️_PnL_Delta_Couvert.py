"""Page 7 · P&L delta-couvert — l'économie de la vente de vol et de la couverture delta."""
import streamlit as st

from utils.state import require_data, lesson, keypoints
from engine.core import svi_implied_vol
from engine.strategy import simulate_delta_hedged_pnl
from engine import viz

st.set_page_config(layout="wide", page_title="Vol Desk", page_icon="📈")
require_data()

meta = st.session_state["meta"]
surface = st.session_state["surface"]
r, q, spot = meta["r"], meta["q"], meta["spot"]

st.title("⚖️ P&L delta-couvert")
st.markdown("On vend une option à sa vol **implicite**, puis on la couvre en delta "
            "pendant que le sous-jacent bouge réellement à la vol **réalisée**. "
            "Le short vol encaisse le theta et paie le gamma — net positif quand "
            "implicite > réalisée.")

lesson("""
**À quoi sert cette page ?**
Quand on **vend** une option, on encaisse une prime mais on prend un **risque de
direction** (si l'action bouge, on peut perdre). La **couverture en delta**
(delta-hedge) consiste à acheter/vendre l'action en continu pour **annuler** ce risque
de direction. Ce qui reste est un **pari pur sur la volatilité** : on gagne si l'action
bouge **moins** que la vol à laquelle on a vendu l'option.

La page simule ça pas à pas et décompose le résultat (la **cascade**) :
- **Theta** : ce qu'on encaisse (le temps qui passe joue pour le vendeur).
- **Gamma** : ce qu'on paie quand l'action bouge fort.
- **Erreur de couverture** : le coût de se couvrir par à-coups plutôt qu'en continu.
- **Total** : la somme — positif si la vol vendue (**implicite**) dépasse la vol
  réellement subie (**réalisée**).

**Les mots :**
- **Couverture / hedge** : neutraliser un risque en prenant une position opposée.
- **Delta-neutre** : portefeuille insensible aux petites variations de l'action.
- **Short / Long** : vendeur / acheteur de l'option.

**Comment l'utiliser :** mets « vol implicite » > « vol réalisée » et regarde le total
devenir positif. La cascade montre d'où vient chaque euro.
""")

expiries = sorted(surface.keys())
c = st.columns(6)
dte = c[0].selectbox("Échéance (j)", expiries, index=min(2, len(expiries) - 1))
s = surface[dte]
T, fwd = s["T"], s["forward"]
atm_iv = float(svi_implied_vol(0.0, T, s["params"]))
strike_mode = c[1].radio("Strike", ["ATM", "Personnalisé"], horizontal=True)
K = fwd if strike_mode == "ATM" else c[1].number_input(
    "K", min_value=1.0, value=float(round(fwd)), step=1.0)
option = c[2].radio("Type", ["call", "put"], horizontal=True)
pos_label = c[3].radio("Position", ["Short (−1)", "Long (+1)"], horizontal=True)
position = -1.0 if pos_label.startswith("Short") else 1.0
iv_impl = c[4].slider("Vol implicite", 0.05, 1.0, round(atm_iv, 3), 0.005)
iv_real = c[5].slider("Vol réalisée", 0.05, 1.0, round(atm_iv * 0.85, 3), 0.005)

cc = st.columns(2)
n_steps = cc[0].slider("Pas de couverture", 21, 504, 252, 21)
rehedge_every = cc[1].slider("Re-hedge tous les (pas)", 1, 21, 1)

path, attr = simulate_delta_hedged_pnl(
    spot, K, T, r, q, iv_impl, iv_real, option=option, position=position,
    n_steps=n_steps, rehedge_every=rehedge_every, seed=0)

k = st.columns(6)
k[0].metric("Prime", f"{attr['premium']:+.2f}")
k[1].metric("P&L Theta", f"{attr['theta_pnl']:+.2f}")
k[2].metric("P&L Gamma", f"{attr['gamma_pnl']:+.2f}")
k[3].metric("P&L Vega", f"{attr['vega_pnl']:+.2f}")
k[4].metric("Erreur couv.", f"{attr['hedge_error']:+.2f}")
k[5].metric("P&L total", f"{attr['total_pnl']:+.2f}")

st.plotly_chart(viz.pnl_waterfall(attr), use_container_width=True)
st.plotly_chart(viz.hedge_path(path), use_container_width=True)

keypoints(
    "- Le **P&L short-vol** = theta encaissé à chaque pas − `½·Γ·(ΔS)²` payé à chaque "
    "mouvement. Si implicite > réalisée, le theta l'emporte en moyenne.\n"
    "- L'**erreur de couverture** est le coût de se couvrir discrètement (pas en "
    "continu) ; elle diminue quand on re-hedge plus souvent.\n"
    "- Le **P&L vega ≈ 0** ici car la marque implicite est fixe : le vega ne mord que "
    "si on bouge aussi la surface (un risque séparé).\n"
    "- C'est le **pari fondamental** d'un vendeur de vol : implicite vs réalisée.")
