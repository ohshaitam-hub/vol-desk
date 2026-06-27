"""Page 6 · Valeur relative — repérer les options chères/bon marché vs la surface."""
import streamlit as st

from utils.state import require_data, push_score, lesson
from engine.strategy import relative_value_screen
from engine import viz

st.set_page_config(layout="wide", page_title="Vol Desk", page_icon="📈")
require_data()

iv_panel = st.session_state["iv_panel"]
surface = st.session_state["surface"]

st.title("💎 Valeur relative")
st.markdown("La VI marché de chaque option est comparée à la **VI juste** SVI. "
            "Le résidu est standardisé au sein de son échéance (un z-score) ; les "
            "contrats au-delà du seuil sont signalés statistiquement **chers "
            "(vendre)** ou **bon marché (acheter)** — exactement le biais autour "
            "duquel un teneur de marché cote.")

lesson("""
**À quoi sert cette page ?**
On a une surface « juste » et saine (pages 4–5). On s'en sert maintenant de
**référence** : on compare le prix réel de chaque option à son **prix théorique**.
Les options anormalement **chères** sont candidates à la **vente**, les **bon marché**
à l'**achat**. C'est le cœur du trading de valeur relative.

Pour décider de « anormalement », on standardise l'écart en **z-score** : combien
d'écarts-types l'option est-elle loin de sa juste valeur. Au-delà d'un **seuil**, on
la signale.

**Les mots :**
- **Valeur relative** : comparer un prix à une référence, pas dans l'absolu.
- **Juste valeur (fair)** : le prix théorique donné par la surface SVI.
- **Résidu** : l'écart entre VI marché et VI juste.
- **z-score** : cet écart mesuré en nombre d'écarts-types (1.5 = déjà assez loin).
- **SELL_VOL / BUY_VOL / FAIR** : signal *vendre* / *acheter* / *rien à signaler*.

**Comment l'utiliser :** règle le **seuil z** (plus bas = plus de signaux). Points
rouges = chers (vendre), verts = bon marché (acheter), gris = justes.
""")

z = st.slider("Seuil z", 0.5, 3.0,
              float(st.session_state.get("cfg_z_threshold", 1.5)), 0.1)
rv = relative_value_screen(iv_panel, surface, z_threshold=z)

counts = rv["signal"].value_counts()
n_sell = int(counts.get("SELL_VOL", 0))
n_buy = int(counts.get("BUY_VOL", 0))
n_fair = int(counts.get("FAIR", 0))
push_score(rv_sell=n_sell, rv_buy=n_buy, rv_fair=n_fair, rv_zthr=z)

c = st.columns(3)
c[0].metric("🔴 SELL_VOL (cher)", n_sell)
c[1].metric("🟢 BUY_VOL (bon marché)", n_buy)
c[2].metric("⚪ FAIR (juste)", n_fair)

st.plotly_chart(viz.rv_scatter(rv), use_container_width=True)

st.subheader("Contrats signalés")
only_flagged = st.checkbox("Afficher uniquement les signalés (non-FAIR)", value=True)
table = rv[rv["signal"] != "FAIR"] if only_flagged else rv
cols = ["expiry_dte", "type", "strike", "log_moneyness", "iv", "fair_iv",
        "iv_resid", "iv_zscore", "volume", "signal"]
st.dataframe(
    table[cols].assign(
        VI_pct=(table["iv"] * 100).round(2),
        juste_pct=(table["fair_iv"] * 100).round(2))
    .round({"log_moneyness": 4, "iv_resid": 4, "iv_zscore": 2}),
    use_container_width=True, height=340)

with st.expander("💬 Ce qu'un recruteur demande ici"):
    st.markdown(
        "- **Pourquoi un z-score au sein de chaque échéance ?** Skew/niveau "
        "diffèrent selon la maturité ; standardiser par slice rend 'cher' "
        "comparable sur toute la surface.\n"
        "- **Un z-score élevé est-il un trade ?** Non — c'est un *candidat*. On "
        "vérifie liquidité, emprunt, événements et coût de couverture avant de "
        "s'appuyer dessus.\n"
        "- **D'où vient l'edge ?** De coter autour d'une surface juste propre et "
        "d'être payé pour fournir de la liquidité au flux qui s'en écarte.")
