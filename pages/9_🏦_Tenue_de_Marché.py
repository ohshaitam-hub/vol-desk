"""Page 9 · Tenue de marché (Avellaneda–Stoikov) + scorecard de recherche consolidé."""
import numpy as np
import pandas as pd
import streamlit as st

from utils.state import require_data, get_score, lesson, keypoints
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

st.title("🏦 Tenue de marché — Avellaneda–Stoikov")
st.markdown("Cotation optimale sensible à l'inventaire : le **prix de réserve** "
            "s'incline contre l'inventaire courant (un book long cote plus bas "
            "pour se délester), et la **fourchette** s'élargit avec l'aversion au "
            "risque γ, la volatilité σ et l'horizon. Les arrivées d'ordres "
            "suivent `λ = A·e^(−κδ)`.")

lesson("""
**À quoi sert cette page ?**
Jusqu'ici on **analysait**. Ici on simule le **métier de teneur de marché** (market
maker) : celui qui affiche en permanence un prix auquel il **achète** (bid) et un prix
auquel il **vend** (ask). Il gagne la petite différence (la **fourchette**) sur chaque
échange, mais doit gérer son **stock** (l'**inventaire**) pour ne pas être trop exposé.

Le modèle **Avellaneda–Stoikov** calcule les cotes optimales : il **décale** ses prix
contre son inventaire (s'il a trop acheté, il baisse ses prix pour revendre) et
**élargit** la fourchette quand le risque monte.

**Les mots :**
- **Teneur de marché** : fournit en continu des prix d'achat et de vente.
- **Bid / Ask** : prix auquel il achète / vend ; **fourchette** = ask − bid.
- **Inventaire** : son stock net (positif = il a acheté, négatif = il a vendu).
- **Prix de réserve** : sa juste valeur ajustée de son inventaire.
- **γ (aversion au risque)**, **κ (profondeur du marché)** : les leviers du modèle.

**Bonus :** tout en bas, un **scorecard** récapitule les résultats clés de toutes les
pages précédentes (surface, non-arbitrage, valeur relative, prime de variance).
""")

mid_dte = sorted(surface.keys())[len(surface) // 2]
atm_sigma = float(svi_implied_vol(0.0, surface[mid_dte]["T"], surface[mid_dte]["params"]))

c = st.columns(6)
gamma = c[0].slider("γ aversion au risque", 0.01, 1.0, 0.10, 0.01)
kappa = c[1].slider("κ décroissance arrivées", 0.2, 5.0, 1.5, 0.1)
A = c[2].slider("A intensité de base", 20.0, 400.0, 140.0, 10.0)
sigma = c[3].slider("σ volatilité", 0.05, 1.0, round(atm_sigma, 3), 0.005)
T = c[4].slider("Horizon T (ans)", 0.1, 2.0, 1.0, 0.1)
n_steps = c[5].select_slider("# pas", [200, 350, 500, 800], value=500)

# Aperçu de l'asymétrie de cotation pour des inventaires représentatifs.
skew_rows = []
for inv in (0, 10, -10):
    qd = avellaneda_stoikov_quotes(spot, inv, sigma, T, gamma, kappa)
    skew_rows.append(dict(inventaire=inv, reserve=round(qd["reservation"], 3),
                          bid=round(qd["bid"], 3), ask=round(qd["ask"], 3),
                          fourchette=round(qd["spread"], 3), asymetrie=round(qd["skew"], 3)))
st.subheader("Asymétrie de cotation vs inventaire")
st.dataframe(pd.DataFrame(skew_rows).set_index("inventaire"), use_container_width=True)

mm = simulate_market_making(spot, sigma, T=T, n_steps=n_steps, gamma=gamma,
                            kappa=kappa, arrival_A=A, seed=3)
k = st.columns(2)
k[0].metric("Inventaire final", f"{mm['inventory'].iloc[-1]:.0f}")
k[1].metric("P&L final", f"{mm['pnl'].iloc[-1]:+.2f}")
st.plotly_chart(viz.market_making(mm), use_container_width=True)

# ----------------------------------------------------------------------
# Scorecard de recherche consolidé (agrège les pages via session_state)
# ----------------------------------------------------------------------
st.markdown("---")
st.subheader("🧮 Scorecard de recherche consolidé")
sc = get_score()

# Complète les manques pour que le scorecard soit complet même si une page
# n'a pas été visitée.
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
g1[0].metric("Source", "Réel" if str(sc.get("source", "")).startswith("yfinance") else "Synthétique")
g1[1].metric("Spot", f"{sc.get('spot', spot):.2f}")
g1[2].metric("# échéances", sc.get("n_expiries", len(surface)))
g1[3].metric("RMSE SVI moyen", f"{sc.get('mean_rmse', float('nan'))*100:.2f} pv")

g2 = st.columns(4)
g2[0].metric("Sans arbitrage papillon", "✅" if sc.get("butterfly_ok") else "❌")
g2[1].metric("Violations calendaires", sc.get("calendar_violations", 0))
g2[2].metric("VR cher / bon marché", f"{sc.get('rv_sell', 0)} / {sc.get('rv_buy', 0)}")
g2[3].metric("VRP moy (réussite%)", f"{sc.get('vrp_mean', 0):+.2f} ({sc.get('vrp_winrate', 0)*100:.0f}%)")

st.caption(f"Queue 5% VRP : {sc.get('vrp_tail5', float('nan')):+.2f}  ·  "
           "Le scorecard agrège chaque module précédent via `st.session_state`.")

keypoints(
    "- Le **prix de réserve** est la juste valeur ajustée de l'inventaire à laquelle "
    "le MM est *indifférent* à trader : `r = s − q·γ·σ²·(T−t)`.\n"
    "- On **incline les cotes** pour faire mean-reverter l'inventaire : un book long "
    "abaisse ses deux cotes pour être pris à l'offre et moins levé au bid.\n"
    "- La **fourchette optimale** = `γσ²(T−t) + (2/γ)ln(1+γ/κ)` : l'aversion au risque "
    "et l'horizon l'élargissent, une liquidité plus profonde (κ) la resserre.\n"
    "- Objectif d'un MM : gagner la fourchette **tout en gardant l'inventaire proche "
    "de zéro**.")
