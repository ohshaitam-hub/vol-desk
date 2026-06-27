"""
utils/state.py
Shared Streamlit state: global sidebar config, cached engine calls, the
data-guard for pages 2–9, and the cross-page scorecard bus.
"""
from __future__ import annotations
import streamlit as st

from engine.data import (fetch_chain, clean_and_imply, fit_surface,
                         surface_diagnostics, calendar_arbitrage)

DEFAULTS = dict(cfg_ticker="SPY", cfg_r=0.045, cfg_q=0.013,
                cfg_max_expiries=6, cfg_z_threshold=1.5)


def _ensure_defaults():
    for k, v in DEFAULTS.items():
        st.session_state.setdefault(k, v)


# ----------------------------------------------------------------------
# Refonte visuelle — CSS global injecté sur chaque page
# ----------------------------------------------------------------------
_THEME_CSS = """
<style>
:root{
  --vd-panel:#121826; --vd-border:#1f2a3d; --vd-accent:#58a6ff;
  --vd-accent2:#7c5cff; --vd-mute:#8b98ad; --vd-buy:#3fb950; --vd-sell:#f0617a;
}
.stApp{ background:
  radial-gradient(1200px 620px at 18% -12%, rgba(88,166,255,0.10) 0%, rgba(13,17,23,0) 46%),
  radial-gradient(900px 500px at 100% 0%, rgba(124,92,255,0.08) 0%, rgba(13,17,23,0) 42%),
  #0d1117 fixed; }
.block-container{ padding-top:2.2rem; max-width:1320px; }
h1{ font-weight:700; letter-spacing:-0.02em; }
h2,h3{ font-weight:600; letter-spacing:-0.01em; color:#dbe7ff; }
hr{ border-color:var(--vd-border); }
code{ color:#9fc6ff; background:rgba(88,166,255,0.10); border-radius:5px; padding:0 4px; }

/* Cartes de KPI */
div[data-testid="stMetric"]{
  background:linear-gradient(180deg, rgba(88,166,255,0.07), rgba(18,24,38,0.55));
  border:1px solid var(--vd-border); border-radius:14px; padding:12px 16px; }
div[data-testid="stMetricValue"]{ color:#d6e7ff; font-weight:700; }
div[data-testid="stMetricLabel"] p{ color:var(--vd-mute); font-weight:500; }

/* Boutons */
.stButton>button, .stDownloadButton>button{
  background:linear-gradient(90deg,var(--vd-accent),var(--vd-accent2));
  color:#fff; border:0; border-radius:10px; font-weight:600; }
.stButton>button:hover, .stDownloadButton>button:hover{ filter:brightness(1.12); color:#fff; border:0; }

/* Encadrés (mini-cours, points clés) */
div[data-testid="stExpander"]{
  border:1px solid var(--vd-border)!important; border-left:3px solid var(--vd-accent)!important;
  border-radius:12px!important; background:rgba(18,24,38,0.55); }
div[data-testid="stExpander"] summary{ font-weight:600; }

/* Sidebar */
section[data-testid="stSidebar"]{ background:#0b101a; border-right:1px solid var(--vd-border); }

/* Tableaux & alertes arrondis */
div[data-testid="stDataFrame"]{ border:1px solid var(--vd-border); border-radius:12px; overflow:hidden; }
div[data-testid="stAlert"]{ border-radius:12px; border:1px solid var(--vd-border); }
div[data-baseweb="tab-list"]{ gap:4px; }
</style>
"""


def inject_theme():
    st.markdown(_THEME_CSS, unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Cached engine calls — page switches stay instant
# ----------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def get_market_data(ticker, r, q, max_expiries):
    """Cached fetch_chain + clean_and_imply. Always returns usable data."""
    chain, meta = fetch_chain(ticker=ticker, max_expiries=max_expiries,
                              r=r, q=q, verbose=False)
    iv_panel = clean_and_imply(chain, meta)
    return chain, meta, iv_panel


@st.cache_data(show_spinner=False)
def get_surface(token):
    """Cached SVI surface fit. `token` is the hashable (ticker, r, q, n) tuple."""
    ticker, r, q, max_expiries = token
    _, meta, iv_panel = get_market_data(ticker, r, q, max_expiries)
    return fit_surface(iv_panel, meta)


# ----------------------------------------------------------------------
# Load orchestration + sidebar
# ----------------------------------------------------------------------
def load_data():
    """Run the cached pipeline for the current config and stash it in state."""
    token = (st.session_state["cfg_ticker"], float(st.session_state["cfg_r"]),
             float(st.session_state["cfg_q"]), int(st.session_state["cfg_max_expiries"]))
    chain, meta, iv_panel = get_market_data(*token)
    surface = get_surface(token)
    st.session_state.update(chain=chain, meta=meta, iv_panel=iv_panel,
                            surface=surface, data_token=token, data_ready=True)
    # Seed the scorecard with the structural facts everyone shares.
    diag = surface_diagnostics(surface, meta["r"])
    cal = calendar_arbitrage(surface)
    push_score(source=meta["source"], spot=meta["spot"],
               n_expiries=len(surface),
               mean_rmse=float(diag["fit_rmse"].mean()) if len(diag) else float("nan"),
               butterfly_ok=bool(diag["butterfly_ok"].all()) if len(diag) else False,
               calendar_violations=int(cal["violations"].sum()) if len(cal) else 0)
    return meta


def render_sidebar():
    """Dessine la config globale persistante. Chaque page l'appelle en premier."""
    _ensure_defaults()
    inject_theme()
    sb = st.sidebar
    sb.markdown("## 📈 Vol Desk")
    sb.caption("Cockpit volatilité options & tenue de marché")
    sb.markdown("---")
    sb.markdown("### ⚙️ Configuration globale")
    sb.text_input("Ticker", key="cfg_ticker")
    sb.number_input("Taux sans risque  r", min_value=0.0, max_value=0.25,
                    step=0.005, format="%.3f", key="cfg_r")
    sb.number_input("Rendement dividende  q", min_value=0.0, max_value=0.25,
                    step=0.005, format="%.3f", key="cfg_q")
    sb.slider("Échéances max", 3, 12, key="cfg_max_expiries")
    sb.slider("Seuil z (valeur relative)", 0.5, 3.0, step=0.1, key="cfg_z_threshold")
    if sb.button("🔄 Charger / Rafraîchir", use_container_width=True, type="primary"):
        load_data()
        sb.success("Données rechargées.")
    sb.markdown("---")
    sb.markdown(f"**Statut :** {source_badge()}")


def source_badge() -> str:
    if not st.session_state.get("data_ready"):
        return "⚪ aucune donnée — clique Charger"
    src = st.session_state["meta"]["source"]
    return f"🟢 `{src}`" if src.startswith("yfinance") else f"🟡 `{src}`"


# ----------------------------------------------------------------------
# Guard + bus du scorecard
# ----------------------------------------------------------------------
def require_data():
    """Appelée par les pages 2–9. Bannière + st.stop() si pas de données."""
    render_sidebar()
    if not st.session_state.get("data_ready"):
        st.warning("👈 Charge d'abord les données sur la page **Données de marché**.")
        st.stop()


def push_score(**kwargs):
    """Stash KPIs into the cross-page scorecard (read on page 9)."""
    st.session_state.setdefault("score", {}).update(kwargs)


def get_score() -> dict:
    return dict(st.session_state.get("score", {}))


def lesson(body: str, title: str = "📚 Comprendre cette page (mini-cours)",
           expanded: bool = False):
    """Encadré pédagogique repliable, homogène sur toutes les pages.

    Explique en langage simple à quoi sert la page et définit les termes
    techniques — pour pouvoir utiliser l'app sans bagage préalable.
    """
    with st.expander(title, expanded=expanded):
        st.markdown(body)


def keypoints(body: str, title: str = "💡 Points clés à retenir"):
    """Encadré « points importants à savoir » (remplace l'ancien bloc recruteur)."""
    with st.expander(title, expanded=False):
        st.markdown(body)
