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
