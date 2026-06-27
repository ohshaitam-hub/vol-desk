"""
app.py — VOL DESK · Page 1 · Données de marché & Accueil du cockpit
Page d'accueil : oriente l'utilisateur, charge les données dont dépendent
toutes les autres pages, et affiche les KPI de la surface comme « hero ».
"""
import streamlit as st

from utils.state import render_sidebar, load_data, source_badge

st.set_page_config(layout="wide", page_title="Vol Desk", page_icon="📈")

render_sidebar()

# Chargement automatique à la première visite pour que le cockpit soit peuplé
# immédiatement (le repli synthétique garantit que ça ne bloque jamais, même
# sans réseau ni clé API).
if not st.session_state.get("data_ready"):
    with st.spinner("Chargement des données & calibration de la surface de volatilité…"):
        load_data()

meta = st.session_state["meta"]
iv_panel = st.session_state["iv_panel"]
surface = st.session_state["surface"]

# ----------------------------------------------------------------------
# Hero
# ----------------------------------------------------------------------
st.title("📈 Vol Desk — Cockpit Volatilité Options & Tenue de Marché")
st.markdown(
    "Un desk de recherche options de bout en bout : il récupère une chaîne "
    "d'options, construit une **surface de volatilité SVI sans arbitrage**, la "
    "valide, screene la **valeur relative**, simule le **P&L delta-couvert** et la "
    "**prime de risque de variance**, puis cote en **teneur de marché Avellaneda–"
    "Stoikov**. Yahoo Finance en direct si disponible, surface synthétique "
    "déterministe sinon — l'app tourne toujours.")

st.markdown(f"**Source des données :** {source_badge()}  ·  "
            f"arrêtée au `{meta['asof']:%Y-%m-%d %H:%M UTC}`")

# ----------------------------------------------------------------------
# Parcours en 9 étapes
# ----------------------------------------------------------------------
st.subheader("Parcours")
dot = """
digraph {
  rankdir=LR; bgcolor="#0d1117";
  node [shape=box style="rounded,filled" fillcolor="#161b22" color="#283039"
        fontcolor="#e6edf3" fontname="monospace" fontsize=10 margin=0.12];
  edge [color="#58a6ff" arrowsize=0.7];
  d1 [label="1 · Donnees de marche"]; d2 [label="2 · Valorisation & Grecques"];
  d3 [label="3 · Vol implicite"]; d4 [label="4 · Surface de vol (SVI)"];
  d5 [label="5 · Non-arbitrage"]; d6 [label="6 · Valeur relative"];
  d7 [label="7 · P&L delta-couvert"]; d8 [label="8 · Prime risque variance"];
  d9 [label="9 · Tenue de marche"];
  d1->d2->d3->d4->d5->d6->d7->d8->d9;
}
"""
st.graphviz_chart(dot, use_container_width=True)

# ----------------------------------------------------------------------
# Ligne de KPI
# ----------------------------------------------------------------------
c = st.columns(4)
c[0].metric("Spot", f"{meta['spot']:.2f}")
c[1].metric("# échéances ajustées", len(surface))
c[2].metric("# quotes propres", len(iv_panel))
c[3].metric("Source", "Réel" if meta["source"].startswith("yfinance") else "Synthétique")

# ----------------------------------------------------------------------
# Panel de volatilité implicite nettoyé
# ----------------------------------------------------------------------
st.subheader("Panel de volatilité implicite (nettoyé)")
st.caption("Volatilité implicite au mid et log-moneyness ln(K/F) pour chaque "
           "option survivant aux filtres de liquidité et de non-arbitrage.")
show = iv_panel.copy()
show["VI_%"] = (show["iv"] * 100).round(2)
cols = ["expiry_dte", "type", "strike", "log_moneyness", "VI_%", "mid",
        "bid", "ask", "volume", "open_interest"]
st.dataframe(show[cols].round({"log_moneyness": 4, "mid": 2, "bid": 2, "ask": 2}),
             use_container_width=True, height=380)

with st.expander("💬 Ce qu'un recruteur demande ici"):
    st.markdown(
        "- **Pourquoi le log-moneyness vs le forward, pas le strike ?** Il "
        "standardise les smiles entre maturités et centre l'ATM en `k=0` (le "
        "forward, pas le spot).\n"
        "- **Pourquoi un repli synthétique ?** Un recruteur doit pouvoir ouvrir "
        "l'app sans aucune clé API et voir une surface complète et sans arbitrage.\n"
        "- **Qu'a retiré le nettoyage ?** Les quotes croisées/périmées, les ailes "
        "illiquides, et tout prix hors des bornes de non-arbitrage (le solveur de "
        "VI renvoie NaN dans ce cas).")

with st.expander("🔭 Là où un desk pousse ça plus loin"):
    st.markdown(
        "- Calibration globale **SSVI / eSSVI** garantissant l'absence d'arbitrage "
        "statique sur *toute* la surface (pas slice par slice).\n"
        "- Cross-check **Heston / SABR** et couverture vega **avec coûts de "
        "transaction**.\n"
        "- Un **flux broker en direct** (IBKR / Polygon) avec limites de risque "
        "Greeks & inventaire.\n"
        "- Un **scanner dispersion / skew multi-noms** avec validation hors-échantillon.")

st.caption("Navigue les 8 modules analytiques depuis la barre latérale →. "
           "Ce cockpit est la version live du notebook de recherche (le labo).")
