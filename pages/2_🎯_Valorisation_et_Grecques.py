"""Page 2 · Valorisation & Grecques — pricer Black–Scholes interactif et intuition des Grecques."""
import streamlit as st

from utils.state import require_data, lesson
from engine.core import bs_price, bs_greeks
from engine import viz

st.set_page_config(layout="wide", page_title="Vol Desk", page_icon="📈")
require_data()

meta = st.session_state["meta"]
r, q = meta["r"], meta["q"]
spot = meta["spot"]

st.title("🎯 Valorisation & Grecques")
st.markdown("Prix Black–Scholes en forme close et l'ensemble des Grecques. "
            "Bouge les contrôles — chaque graphique se recalcule en direct "
            "depuis `engine.core`.")

lesson("""
**À quoi sert cette page ?**
À calculer le **prix « juste »** d'une option avec la formule de référence
(**Black–Scholes**) et à visualiser ses **risques** — les « **Grecques** ».

Les Grecques mesurent comment le prix de l'option réagit à chaque facteur :
- **Delta** : de combien le prix de l'option bouge si l'action monte de 1 € (≈ ton
  exposition à la direction).
- **Gamma** : à quelle vitesse le Delta lui-même change (la « courbure »).
- **Vega** : sensibilité à la **volatilité** (de combien si la vol monte de 1 point).
- **Theta** : ce que l'option perd chaque **jour** qui passe (l'érosion du temps).
- **Rho** : sensibilité aux **taux d'intérêt**.

**Comment l'utiliser :** bouge les curseurs (spot, strike, maturité, vol) et regarde
le prix et les Grecques se recalculer. Les graphiques montrent comment chaque Grecque
évolue selon le prix de l'action.
""")

c = st.columns(6)
S = c[0].slider("Spot S", float(0.5 * spot), float(1.5 * spot), float(spot))
K = c[1].slider("Strike K", float(0.5 * spot), float(1.5 * spot), float(round(spot)))
T = c[2].slider("Maturité T (ans)", 0.02, 2.0, 0.25, 0.01)
sigma = c[3].slider("Vol σ", 0.05, 1.0, 0.20, 0.01)
option = c[4].radio("Type", ["call", "put"], horizontal=True)
r = c[5].number_input("r", value=float(r), step=0.005, format="%.3f")

price = float(bs_price(S, K, T, r, sigma, q, option))
g = bs_greeks(S, K, T, r, sigma, q, option)

k = st.columns(6)
k[0].metric("Prix", f"{price:.3f}")
k[1].metric("Delta", f"{float(g['delta']):.3f}")
k[2].metric("Gamma", f"{float(g['gamma']):.4f}")
k[3].metric("Vega", f"{float(g['vega']):.3f}")
k[4].metric("Theta / jour", f"{float(g['theta'])/365:.3f}")
k[5].metric("Rho", f"{float(g['rho']):.3f}")

st.plotly_chart(viz.price_vs_spot(K, T, r, sigma, q, option, S),
                use_container_width=True)
st.plotly_chart(viz.greeks_grid(K, T, r, sigma, q, option, S),
                use_container_width=True)

if st.toggle("Afficher le payoff à l'échéance"):
    st.plotly_chart(viz.payoff_at_expiry(K, option, S, premium=price,
                    position=1.0), use_container_width=True)

with st.expander("💬 Ce qu'un recruteur demande ici"):
    st.markdown(
        "- **Signe du theta vs gamma ?** Une option longue est longue gamma / "
        "courte theta — on paie la décote temporelle pour détenir la convexité. "
        "Le short inverse les deux.\n"
        "- **Pourquoi le vega est-il maximal ATM et pour les longues maturités ?** "
        "Vega ∝ S·φ(d1)·√T, maximal près du forward et croissant en √T.\n"
        "- **Theta par jour ?** Le moteur renvoie un theta annuel ; on divise par "
        "365 pour le saignement quotidien que regarde un trader.")
