"""Page 3 · Volatilité implicite — inversion des prix marché et smiles bruts."""
import streamlit as st

from utils.state import require_data, lesson, keypoints
from engine.core import implied_vol
from engine import viz

st.set_page_config(layout="wide", page_title="Vol Desk", page_icon="📈")
require_data()

meta = st.session_state["meta"]
iv_panel = st.session_state["iv_panel"]
r, q, spot = meta["r"], meta["q"], meta["spot"]

st.title("📈 Volatilité implicite")
st.markdown("Chaque prix mid coté est inversé en volatilité implicite Black–"
            "Scholes via un solveur de Brent robuste, puis tracé contre le "
            "log-moneyness `ln(K/F)` — le smile marché brut avant tout ajustement.")

lesson("""
**À quoi sert cette page ?**
La page 2 allait du *prix → vol*. Ici on fait l'**inverse** : à partir du **prix de
marché** d'une option, on retrouve la **volatilité implicite (VI)** — la volatilité
que le marché « price » dans cette option.

En traçant la VI pour tous les strikes d'une même échéance, on obtient une courbe : le
**smile** (ou **skew** quand elle penche d'un côté). Sa forme raconte ce que le marché
craint (souvent une chute → les options de protection sont plus chères).

**Les mots :**
- **Volatilité implicite (VI)** : la vol déduite du prix de marché de l'option.
- **Log-moneyness `ln(K/F)`** : mesure si l'option est « à la monnaie » (≈ 0),
  au-dessus (> 0) ou en-dessous (< 0). `K` = strike, `F` = prix *forward* (le prix
  attendu de l'action à l'échéance).
- **ATM (à la monnaie)** : strike ≈ prix de l'action.
- **Smile / skew** : la forme de la courbe de VI selon le strike.

**Comment l'utiliser :** choisis une échéance, observe le nuage de points (le smile).
En bas, un mini-calculateur : entre un prix d'option → il te rend la VI correspondante.
""")

expiries = sorted(iv_panel["expiry_dte"].unique())
dte = st.selectbox("Échéance (jours avant expiration)", expiries)
g = iv_panel[iv_panel["expiry_dte"] == dte]

c = st.columns(3)
c[0].metric("Quotes dans la slice", len(g))
c[1].metric("VI ATM (k≈0 le plus proche)",
            f"{g.iloc[(g['log_moneyness'].abs()).argmin()]['iv']*100:.2f}%")
c[2].metric("Skew (proxy 25Δ)",
            f"{(g['iv'].max()-g['iv'].min())*100:.2f} pv")

st.plotly_chart(viz.iv_market_scatter(iv_panel, dte), use_container_width=True)

st.dataframe(
    g[["type", "strike", "log_moneyness", "iv", "mid", "volume"]]
    .assign(VI_pct=(g["iv"] * 100).round(2))
    .round({"log_moneyness": 4, "mid": 2}),
    use_container_width=True, height=300)

st.subheader("Calculateur de VI pour une option")
cc = st.columns(4)
px = cc[0].number_input("Prix de l'option", min_value=0.0, value=10.0, step=0.5)
strike = cc[1].number_input("Strike", min_value=1.0, value=float(round(spot)), step=1.0)
T_in = cc[2].number_input("Maturité (ans)", min_value=0.01, value=float(dte / 365), step=0.01)
typ = cc[3].radio("Type", ["call", "put"], horizontal=True)
iv_calc = implied_vol(px, spot, strike, T_in, r, q, typ)
st.metric("Volatilité implicite",
          f"{iv_calc*100:.2f}%" if iv_calc == iv_calc else "n/a (hors bornes de non-arbitrage)")

keypoints(
    "- La **VI peut être NaN** quand le prix viole les bornes de non-arbitrage (sous "
    "l'intrinsèque / au-dessus du sous-jacent actualisé) : le solveur refuse "
    "d'inventer une vol à partir d'une mauvaise quote.\n"
    "- On inverse le **prix mid** : c'est le point le moins biaisé (le bid et l'ask "
    "embarquent chacun une demi-fourchette).\n"
    "- Les indices actions montrent un **skew baissier** : les puts OTM (protection) "
    "sont plus chers ; un U symétrique serait un *smile*.\n"
    "- La VI **n'est pas** la vol future réalisée : c'est l'anticipation du marché, "
    "prime de risque incluse.")
