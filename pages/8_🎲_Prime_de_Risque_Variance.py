"""Page 8 · Prime de risque de variance — la distribution honnête des issues short-vol."""
import numpy as np
import streamlit as st
from scipy.stats import skew as scipy_skew

from utils.state import require_data, push_score, lesson
from engine.core import svi_implied_vol
from engine.strategy import vrp_monte_carlo
from engine import viz

st.set_page_config(layout="wide", page_title="Vol Desk", page_icon="📈")
require_data()

meta = st.session_state["meta"]
surface = st.session_state["surface"]
r, q, spot = meta["r"], meta["q"], meta["spot"]

st.title("🎲 Prime de risque de variance")
st.markdown("Vendre la vol paie une prime — mais le payoff est **asymétrique "
            "négativement** : une moyenne positive avec une queue gauche épaisse "
            "(le rare blow-up de vol). Ce Monte Carlo tire une vol réalisée "
            "*stochastique* par trajectoire pour que la queue soit honnête.")

lesson("""
**À quoi sert cette page ?**
La page 7 simulait **une** vente de vol. Ici on la rejoue **des milliers de fois**
(**Monte Carlo**) avec des marchés aléatoires, pour voir la **distribution** des
résultats — la vraie forme du risque.

Le constat : vendre de la vol, c'est comme **vendre de l'assurance**. La plupart du
temps on gagne un petit montant (la **prime**), mais de temps en temps survient une
catastrophe (un pic de volatilité) qui fait perdre gros. D'où une **moyenne positive**
mais une **queue gauche épaisse**.

**Les mots :**
- **Prime de risque de variance** : le surplus que paie en moyenne l'acheteur de
  protection au vendeur de vol.
- **Monte Carlo** : simuler des milliers de scénarios aléatoires pour estimer une
  distribution.
- **Queue (tail)** : les rares scénarios extrêmes (ici à gauche = grosses pertes).
- **Asymétrie (skew)** négative : la distribution penche vers les pertes rares mais
  fortes.

**Comment lire :** la ligne verte = le gain **moyen** (positif). La ligne rouge = la
perte dans les **5 % pires** cas. Un taux de réussite élevé + une queue gauche = la
signature de la vente d'assurance.
""")


@st.cache_data(show_spinner=True)
def run_vrp(S0, K, T, r, q, iv_impl, iv_real_mean, n_paths, n_steps,
            vol_of_vol, jump_prob, jump_size):
    return vrp_monte_carlo(S0, K, T, r, q, iv_impl, iv_real_mean, option="call",
                           n_paths=n_paths, n_steps=n_steps, vol_of_vol=vol_of_vol,
                           jump_prob=jump_prob, jump_size=jump_size, seed=1)


expiries = sorted(surface.keys())
top = st.columns(4)
dte = top[0].selectbox("Échéance (j)", expiries, index=min(2, len(expiries) - 1))
s = surface[dte]
T, K = s["T"], s["forward"]
atm_iv = float(svi_implied_vol(0.0, T, s["params"]))
iv_impl = top[1].slider("Vol implicite (vendue à)", 0.05, 1.0, round(atm_iv, 3), 0.005)
iv_real_mean = top[2].slider("Vol réalisée (moyenne)", 0.05, 1.0, round(atm_iv * 0.85, 3), 0.005)
vov = top[3].slider("Vol-of-vol", 0.05, 1.0, 0.35, 0.05)

bot = st.columns(4)
jump_prob = bot[0].slider("Prob. de saut", 0.0, 0.30, 0.04, 0.01)
jump_size = bot[1].slider("Taille du saut (vol)", 0.0, 0.30, 0.08, 0.01)
n_paths = bot[2].select_slider("# trajectoires", [500, 1000, 2000, 4000], value=2000)
n_steps = bot[3].select_slider("# pas", [21, 42, 63, 126], value=63)

pnl, rv = run_vrp(spot, K, T, r, q, iv_impl, iv_real_mean, n_paths, n_steps,
                  vov, jump_prob, jump_size)

mean = float(np.mean(pnl)); win = float(np.mean(pnl > 0))
p5 = float(np.percentile(pnl, 5)); p1 = float(np.percentile(pnl, 1))
sk = float(scipy_skew(pnl))
push_score(vrp_mean=mean, vrp_winrate=win, vrp_tail5=p5)

k = st.columns(5)
k[0].metric("P&L moyen", f"{mean:+.2f}")
k[1].metric("Taux de réussite", f"{win*100:.1f}%")
k[2].metric("Queue 5%", f"{p5:+.2f}")
k[3].metric("Queue 1%", f"{p1:+.2f}")
k[4].metric("Asymétrie", f"{sk:+.2f}")

st.plotly_chart(viz.vrp_histogram(pnl), use_container_width=True)
if st.toggle("Afficher la distribution simulée de la vol réalisée"):
    st.plotly_chart(viz.realized_vol_histogram(rv), use_container_width=True)

st.info("📌 L'**asymétrie négative est le coût de la prime** : la plupart des "
        "trajectoires gagnent un peu (theta > gamma), quelques-unes perdent "
        "beaucoup (un pic de vol retourne le short gamma contre soi). Un taux de "
        "réussite élevé avec une queue gauche épaisse est la signature de la vente "
        "d'assurance.")

with st.expander("💬 Ce qu'un recruteur demande ici"):
    st.markdown(
        "- **Pourquoi la moyenne est positive ?** La vol implicite embarque une "
        "prime de risque sur la réalisée — les vendeurs sont payés pour stocker le "
        "risque de variance.\n"
        "- **Pourquoi modéliser une vol réalisée stochastique + des sauts ?** Un MC "
        "à vol constante cache la queue ; la prime n'a de sens que face au risque "
        "de blow-up qu'elle rémunère.\n"
        "- **Comment dimensionner ça ?** Contre la queue 1–5% (CVaR), pas la "
        "moyenne — la queue gauche est ce qui te stoppe.")
