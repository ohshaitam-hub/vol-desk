"""Page 10 · Exercices — questions aléatoires à résoudre en utilisant l'app.

Chaque exercice te dit quelle page ouvrir et quels réglages mettre ; tu lis le
résultat dans l'app et tu saisis ta réponse. La bonne réponse est calculée par
le **même moteur** que les autres pages (sur les **données actuellement
chargées**), donc tout est cohérent et corrigé automatiquement.
"""
import numpy as np
import streamlit as st

from utils.state import require_data, lesson
from engine.core import bs_price, bs_greeks, svi_implied_vol
from engine.strategy import (relative_value_screen, simulate_delta_hedged_pnl,
                             avellaneda_stoikov_quotes)
from engine.data import surface_diagnostics, calendar_arbitrage

st.set_page_config(layout="wide", page_title="Vol Desk", page_icon="📈")
require_data()

meta = st.session_state["meta"]
iv_panel = st.session_state["iv_panel"]
surface = st.session_state["surface"]
r, q, spot = meta["r"], meta["q"], meta["spot"]

st.title("🎓 Exercices")
st.markdown("Entraîne-toi : chaque exercice te fait **utiliser l'app** pour trouver "
            "la réponse. Lis la consigne, va sur la page indiquée, règle les "
            "contrôles, relève le résultat — puis vérifie ici.")

lesson("""
**Comment ça marche ?**
1. Clique **🎲 Nouvel exercice** : une question aléatoire apparaît.
2. La consigne te dit **quelle page** ouvrir (menu de gauche) et **quels réglages**
   appliquer.
3. Relève la valeur affichée par l'app, reviens ici, saisis ta réponse, clique
   **✅ Vérifier**.
4. La correction est **automatique** : la bonne réponse est calculée par le moteur sur
   les **données actuellement chargées** (mêmes que celles affichées).

ℹ️ Pour les valeurs numériques, une **petite tolérance** est admise (arrondis).
Le **score** se met à jour en haut.
""")


# ----------------------------------------------------------------------
# Générateurs d'exercices — chacun renvoie un dict (page, prompt, kind, answer…)
# ----------------------------------------------------------------------
def g_price_greek(rng):
    S = float(round(spot)); K = float(round(spot))
    T = float(rng.choice([0.10, 0.25, 0.50, 1.00]))
    sigma = float(rng.choice([0.15, 0.20, 0.25, 0.30]))
    opt = str(rng.choice(["call", "put"]))
    metric = str(rng.choice(["Prix", "Delta", "Vega", "Theta / jour"]))
    if metric == "Prix":
        a = float(bs_price(S, K, T, r, sigma, q, opt)); tol = max(0.5, 0.02 * abs(a))
    else:
        gk = bs_greeks(S, K, T, r, sigma, q, opt)
        if metric == "Delta":
            a = float(gk["delta"]); tol = 0.02
        elif metric == "Vega":
            a = float(gk["vega"]); tol = max(0.6, 0.03 * abs(a))
        else:
            a = float(gk["theta"]) / 365.0; tol = max(0.03, 0.06 * abs(a))
    prompt = (f"**Page 🎯 Valorisation & Grecques.** Règle : `S={S:.0f}`, "
              f"`K={K:.0f}`, `T={T}` an, `σ={sigma}`, type **{opt}** (garde `r` et "
              f"`q` par défaut).\n\n👉 Quel est le **{metric}** affiché ?")
    return dict(page="🎯 Valorisation & Grecques", prompt=prompt, kind="number",
                answer=a, tol=tol, unit="")


def g_vi_atm(rng):
    dtes = sorted(iv_panel["expiry_dte"].unique())
    dte = int(rng.choice(dtes))
    g = iv_panel[iv_panel["expiry_dte"] == dte]
    a = float(g.iloc[(g["log_moneyness"].abs()).argmin()]["iv"] * 100)
    prompt = (f"**Page 📈 Volatilité implicite.** Choisis l'échéance **{dte} j** et "
              f"lis la métrique **« VI ATM »**.\n\n👉 Quelle est sa valeur (en %) ?")
    return dict(page="📈 Volatilité implicite", prompt=prompt, kind="number",
                answer=a, tol=0.5, unit="%")


def g_slice_count(rng):
    dtes = sorted(iv_panel["expiry_dte"].unique())
    dte = int(rng.choice(dtes))
    a = int((iv_panel["expiry_dte"] == dte).sum())
    prompt = (f"**Page 📈 Volatilité implicite.** Échéance **{dte} j** : lis la "
              f"métrique **« Quotes dans la slice »**.\n\n👉 Combien y en a-t-il ?")
    return dict(page="📈 Volatilité implicite", prompt=prompt, kind="number",
                answer=a, tol=0.5, unit="")


def g_svi_param(rng):
    dte = int(rng.choice(sorted(surface)))
    name = str(rng.choice(["b", "rho", "m", "sigma"]))
    a = float(getattr(surface[dte]["params"], name))
    prompt = (f"**Page 🌐 Surface de volatilité.** Dans le tableau **« Paramètres "
              f"SVI ajustés »**, échéance **{dte} j**.\n\n👉 Quelle est la valeur du "
              f"paramètre **{name}** ?")
    return dict(page="🌐 Surface de volatilité", prompt=prompt, kind="number",
                answer=a, tol=0.04, unit="")


def g_rmse(rng):
    dte = int(rng.choice(sorted(surface)))
    a = float(surface[dte]["rmse"] * 100)
    prompt = (f"**Page 🌐 Surface de volatilité.** Tableau des paramètres, colonne "
              f"**`rmse_pv`**, échéance **{dte} j**.\n\n👉 Quelle est sa valeur "
              f"(en points de vol) ?")
    return dict(page="🌐 Surface de volatilité", prompt=prompt, kind="number",
                answer=a, tol=0.15, unit="pv")


def g_butterfly(rng):
    diag = surface_diagnostics(surface, r)
    ok = bool(diag["butterfly_ok"].all()) if len(diag) else False
    prompt = ("**Page ✅ Non-arbitrage.** Regarde l'indicateur **« Sans arbitrage "
              "papillon »**.\n\n👉 La surface est-elle sans arbitrage papillon ?")
    return dict(page="✅ Non-arbitrage", prompt=prompt, kind="choice",
                answer=("Oui" if ok else "Non"), choices=["Oui", "Non"])


def g_calendar(rng):
    cal = calendar_arbitrage(surface)
    a = int(cal["violations"].sum()) if len(cal) else 0
    prompt = ("**Page ✅ Non-arbitrage.** Lis la métrique **« Violations "
              "calendaires »**.\n\n👉 Combien y en a-t-il au total ?")
    return dict(page="✅ Non-arbitrage", prompt=prompt, kind="number",
                answer=a, tol=0.5, unit="")


def g_rv_count(rng):
    z = float(rng.choice([1.0, 1.5, 2.0]))
    which = str(rng.choice(["SELL_VOL", "BUY_VOL"]))
    rv = relative_value_screen(iv_panel, surface, z_threshold=z)
    a = int((rv["signal"] == which).sum())
    label = "SELL_VOL (cher)" if which == "SELL_VOL" else "BUY_VOL (bon marché)"
    prompt = (f"**Page 💎 Valeur relative.** Règle le **seuil z = {z}**.\n\n"
              f"👉 Combien d'options sont signalées **{label}** ?")
    return dict(page="💎 Valeur relative", prompt=prompt, kind="number",
                answer=a, tol=0.5, unit="")


def g_hedge_sign(rng):
    dte = int(rng.choice(sorted(surface)))
    s = surface[dte]; T, K = s["T"], s["forward"]
    atm = float(svi_implied_vol(0.0, T, s["params"]))
    iv_impl, iv_real = round(atm, 3), round(atm * 0.85, 3)
    _, attr = simulate_delta_hedged_pnl(spot, K, T, r, q, iv_impl, iv_real,
                                        option="call", position=-1.0,
                                        n_steps=252, rehedge_every=1, seed=0)
    a = "Positif" if attr["total_pnl"] >= 0 else "Négatif"
    prompt = (f"**Page ⚖️ P&L delta-couvert.** Échéance **{dte} j**, strike **ATM**, "
              f"type **call**, position **Short**, garde les autres valeurs par "
              f"défaut.\n\n👉 Le **P&L total** est-il positif ou négatif ?")
    return dict(page="⚖️ P&L delta-couvert", prompt=prompt, kind="choice",
                answer=a, choices=["Positif", "Négatif"])


def g_mm_reservation(rng):
    inv = int(rng.choice([10, -10]))
    a = "En-dessous du mid" if inv > 0 else "Au-dessus du mid"
    prompt = (f"**Page 🏦 Tenue de marché.** Dans le tableau **« Asymétrie de "
              f"cotation vs inventaire »**, pour un inventaire de **{inv:+d}**.\n\n"
              f"👉 Le **prix de réserve** est-il au-dessus ou en-dessous du mid ?")
    return dict(page="🏦 Tenue de marché", prompt=prompt, kind="choice",
                answer=a, choices=["Au-dessus du mid", "En-dessous du mid"])


GENERATORS = [g_price_greek, g_vi_atm, g_slice_count, g_svi_param, g_rmse,
              g_butterfly, g_calendar, g_rv_count, g_hedge_sign, g_mm_reservation]


# ----------------------------------------------------------------------
# Logique de la page
# ----------------------------------------------------------------------
def new_exercise():
    st.session_state["ex_counter"] = st.session_state.get("ex_counter", 0) + 1
    rng = np.random.default_rng(st.session_state["ex_counter"] * 7919 + 13)
    gen = GENERATORS[int(rng.integers(len(GENERATORS)))]
    st.session_state["ex"] = gen(rng)
    st.session_state["ex_answered"] = False
    st.session_state.pop("ex_result", None)


if "ex" not in st.session_state:
    st.session_state.setdefault("ex_correct", 0)
    st.session_state.setdefault("ex_total", 0)
    new_exercise()

top = st.columns([1, 1, 2])
top[0].metric("Score", f"{st.session_state['ex_correct']} / {st.session_state['ex_total']}")
if top[1].button("🎲 Nouvel exercice", use_container_width=True):
    new_exercise()
    st.rerun()

ex = st.session_state["ex"]
st.markdown(f"#### 🧩 Exercice n°{st.session_state['ex_counter']} "
            f"— *{ex['page']}*")
st.info(ex["prompt"])

answered = st.session_state.get("ex_answered", False)
if ex["kind"] == "number":
    user = st.number_input("Ta réponse" + (f"  ({ex['unit']})" if ex["unit"] else ""),
                           value=0.0, step=0.01, format="%.4f", disabled=answered)
else:
    user = st.radio("Ta réponse", ex["choices"], index=None, disabled=answered)

if st.button("✅ Vérifier", disabled=answered or (ex["kind"] == "choice" and user is None)):
    if ex["kind"] == "number":
        ok = abs(float(user) - float(ex["answer"])) <= float(ex["tol"])
    else:
        ok = (user == ex["answer"])
    st.session_state["ex_total"] += 1
    if ok:
        st.session_state["ex_correct"] += 1
    st.session_state["ex_answered"] = True
    st.session_state["ex_result"] = ok
    st.rerun()

if st.session_state.get("ex_answered"):
    ok = st.session_state.get("ex_result", False)
    ans = ex["answer"]
    ans_str = (f"{ans:.4g} {ex.get('unit','')}".strip()
               if ex["kind"] == "number" else str(ans))
    if ok:
        st.success(f"✅ Correct ! Réponse attendue : **{ans_str}**.")
    else:
        st.error(f"❌ Pas tout à fait. Réponse attendue : **{ans_str}** "
                 f"(à relever sur la page **{ex['page']}**).")
    st.caption("Clique **🎲 Nouvel exercice** pour continuer.")
