"""Page 10 · Exercices — vrais exercices de CALCUL (quant / desk options).

On te donne des données numériques ; tu appliques une formule et tu trouves le
résultat (parité call-put, couverture delta, P&L gamma/vega, seuil de
rentabilité du gamma, forward, log-moneyness, formule SVI, cotes
Avellaneda–Stoikov…). La correction est automatique et la **méthode** est
révélée après ta réponse — c'est un entraînement réutilisable (entretien quant,
desk, mémoire).
"""
import numpy as np
import streamlit as st

from utils.state import require_data, lesson
from engine.core import bs_price

st.set_page_config(layout="wide", page_title="Vol Desk", page_icon="📈")
require_data()

st.title("🎓 Exercices de calcul")
st.markdown("Des exercices où **tu calcules** un résultat à partir de données — pas "
            "juste lire une valeur dans un onglet. Chaque correction révèle la "
            "**formule** et le **calcul détaillé**.")

lesson("""
**Comment ça marche ?**
1. Clique **🎲 Nouvel exercice** : un énoncé chiffré apparaît (toutes les données sont
   dans l'énoncé — pas besoin d'aller ailleurs).
2. Sors ta calculatrice, applique la bonne formule, trouve le résultat.
3. Saisis ta réponse, clique **✅ Vérifier** : correction automatique + la **méthode
   détaillée** s'affiche (formule + calcul).
4. Le **score** se met à jour en haut.

🎯 Ces calculs sont le b.a.-ba d'un desk options : parité, hedging, gamma scalping,
sensibilités, SVI, market making. Utile pour un entretien quant comme pour ton mémoire.
""")

E = np.exp
LN = np.log
SQRT = np.sqrt


# ----------------------------------------------------------------------
# Générateurs : chacun renvoie (énoncé chiffré, réponse, tolérance, méthode)
# ----------------------------------------------------------------------
def g_forward(rng):
    S = float(rng.choice([100, 150, 200, 300, 450, 500]))
    r = float(rng.choice([0.02, 0.03, 0.045, 0.05]))
    q = float(rng.choice([0.0, 0.01, 0.015, 0.02]))
    T = float(rng.choice([0.25, 0.5, 1.0, 2.0]))
    F = S * E((r - q) * T)
    prompt = (f"**Prix forward.** Une action vaut `S = {S:.0f}`. Taux sans risque "
              f"`r = {r:.3f}`, rendement dividende `q = {q:.3f}`, maturité "
              f"`T = {T}` an.\n\n👉 Calcule le **prix forward** `F`.")
    method = (f"`F = S·e^((r−q)·T) = {S:.0f}·e^(({r:.3f}−{q:.3f})·{T}) "
              f"= {F:.4f}`")
    return dict(prompt=prompt, answer=F, tol=max(0.05, 0.002 * F), unit="",
                method=method, page="—")


def g_logmon(rng):
    F = float(rng.choice([100, 200, 300, 450, 500]))
    K = float(np.round(F * rng.uniform(0.85, 1.15)))
    k = LN(K / F)
    prompt = (f"**Log-moneyness.** Prix forward `F = {F:.0f}`, strike `K = {K:.0f}`.\n\n"
              f"👉 Calcule le **log-moneyness** `k = ln(K/F)` (4 décimales).")
    method = f"`k = ln(K/F) = ln({K:.0f}/{F:.0f}) = {k:.4f}`"
    return dict(prompt=prompt, answer=k, tol=0.004, unit="", method=method, page="—")


def g_parity(rng):
    S = float(rng.choice([100, 200, 300, 450]))
    K = float(np.round(S * rng.uniform(0.92, 1.08)))
    r = float(rng.choice([0.02, 0.03, 0.045]))
    q = float(rng.choice([0.0, 0.01, 0.015]))
    T = float(rng.choice([0.25, 0.5, 1.0]))
    vol = float(rng.choice([0.18, 0.22, 0.28]))
    C = float(round(bs_price(S, K, T, r, vol, q, "call"), 2))
    P = C - S * E(-q * T) + K * E(-r * T)          # parité call-put (européenne)
    prompt = (f"**Parité call-put.** Un **call** vaut `C = {C:.2f}` "
              f"(`S = {S:.0f}`, `K = {K:.0f}`, `r = {r:.3f}`, `q = {q:.3f}`, "
              f"`T = {T}`).\n\n👉 Quel est le prix du **put** de même strike et "
              f"échéance ?")
    method = (f"`P = C − S·e^(−qT) + K·e^(−rT)` "
              f"`= {C:.2f} − {S:.0f}·e^(−{q:.3f}·{T}) + {K:.0f}·e^(−{r:.3f}·{T}) "
              f"= {P:.4f}`")
    return dict(prompt=prompt, answer=P, tol=max(0.05, 0.01 * abs(P)), unit="",
                method=method, page="🎯 Valorisation & Grecques")


def g_hedge_shares(rng):
    N = int(rng.choice([50, 100, 200]))
    typ = str(rng.choice(["call", "put"]))
    delta = float(rng.choice([0.30, 0.45, 0.55, 0.65]))
    if typ == "put":
        delta = -float(rng.choice([0.30, 0.45, 0.55]))
    pos = float(rng.choice([1, -1]))
    pos_lbl = "long" if pos > 0 else "short"
    shares = -(pos * N * delta)          # actions pour neutraliser le delta
    prompt = (f"**Couverture en delta.** Tu es **{pos_lbl} {N} {typ}s** de "
              f"delta `Δ = {delta:+.2f}` chacun.\n\n👉 Combien d'**actions** du "
              f"sous-jacent faut-il détenir pour être **delta-neutre** ? "
              f"(positif = acheter, négatif = vendre)")
    method = (f"Delta du portefeuille d'options `= position×N×Δ = "
              f"{pos:+.0f}×{N}×{delta:+.2f} = {pos*N*delta:+.1f}`. On détient "
              f"l'opposé en actions : `{-(pos*N*delta):+.1f}`.")
    return dict(prompt=prompt, answer=shares, tol=0.5, unit="actions",
                method=method, page="🎯 Valorisation & Grecques")


def g_gamma_pnl(rng):
    N = int(rng.choice([10, 50, 100]))
    pos = float(rng.choice([1, -1]))
    pos_lbl = "long" if pos > 0 else "short"
    gamma = float(rng.choice([0.01, 0.02, 0.04]))
    dS = float(rng.choice([2, 3, 5, 8]))
    pnl = 0.5 * pos * N * gamma * dS ** 2
    prompt = (f"**P&L gamma.** Tu es **{pos_lbl} {N} options**, gamma `Γ = {gamma}` "
              f"par option. Le sous-jacent bouge de `ΔS = {dS:.0f}`.\n\n"
              f"👉 Estime le **P&L gamma** ≈ `½ · position · N · Γ · ΔS²`.")
    method = (f"`½·{pos:+.0f}·{N}·{gamma}·{dS:.0f}² = {pnl:+.4f}`. "
              f"(Long gamma gagne sur les mouvements ; short gamma perd.)")
    return dict(prompt=prompt, answer=pnl, tol=max(0.05, 0.01 * abs(pnl)), unit="",
                method=method, page="⚖️ P&L delta-couvert")


def g_vega_pnl(rng):
    V = float(rng.choice([0.3, 0.5, 1.2, 2.0]))
    pos = float(rng.choice([1, -1]))
    pos_lbl = "long" if pos > 0 else "short"
    v0 = float(rng.choice([18, 20, 22]))
    dv = float(rng.choice([-3, -2, 2, 3]))
    v1 = v0 + dv
    pnl = pos * V * dv
    prompt = (f"**P&L vega.** Tu es **{pos_lbl}** un vega de `{V}` (par point de "
              f"vol). La volatilité implicite passe de `{v0:.0f}%` à `{v1:.0f}%`.\n\n"
              f"👉 Estime le **P&L vega** ≈ `position · vega · Δvol(points)`.")
    method = (f"Δvol `= {v1:.0f}−{v0:.0f} = {dv:+.0f}` points. "
              f"`P&L = {pos:+.0f}·{V}·{dv:+.0f} = {pnl:+.4f}`.")
    return dict(prompt=prompt, answer=pnl, tol=max(0.05, 0.01 * abs(pnl)), unit="",
                method=method, page="🎯 Valorisation & Grecques")


def g_breakeven(rng):
    theta = -float(rng.choice([0.05, 0.10, 0.20, 0.30]))   # theta/jour (long, <0)
    gamma = float(rng.choice([0.01, 0.02, 0.04, 0.05]))
    be = SQRT(-2 * theta / gamma)
    prompt = (f"**Seuil de rentabilité du gamma (gamma scalping).** Une option "
              f"**longue** delta-couverte a un `theta = {theta:.2f}` **par jour** "
              f"et un `gamma = {gamma}`.\n\n👉 Quel **mouvement quotidien** `|ΔS|` du "
              f"sous-jacent fait que le gain gamma compense exactement la perte "
              f"theta ? (`½·Γ·ΔS² + θ_jour = 0`)")
    method = (f"`|ΔS| = √(−2·θ_jour / Γ) = √(−2·({theta:.2f})/{gamma}) "
              f"= {be:.4f}`. En dessous, le theta l'emporte (tu perds) ; au-dessus, "
              f"le gamma paie.")
    return dict(prompt=prompt, answer=be, tol=max(0.02, 0.01 * be), unit="",
                method=method, page="⚖️ P&L delta-couvert")


def g_vol_scaling(rng):
    sigma = float(rng.choice([12, 16, 20, 25, 32]))
    S = float(rng.choice([100, 200, 450, 500]))
    ask = str(rng.choice(["daily_pct", "daily_move"]))
    if ask == "daily_pct":
        a = sigma / SQRT(252)
        prompt = (f"**Mise à l'échelle de la volatilité.** La vol implicite "
                  f"**annualisée** est `σ = {sigma:.0f}%`.\n\n👉 Quelle est la vol "
                  f"**quotidienne** approximative ? (`σ / √252`, en %)")
        method = f"`{sigma:.0f}% / √252 = {sigma:.0f}/15.87 = {a:.4f}%`"
        unit = "%"
    else:
        a = S * (sigma / 100) / SQRT(252)
        prompt = (f"**Mouvement quotidien attendu.** Action `S = {S:.0f}`, vol "
                  f"annualisée `σ = {sigma:.0f}%`.\n\n👉 Quel **mouvement quotidien "
                  f"en $** (1 écart-type) est attendu ? (`S·σ/√252`)")
        method = f"`{S:.0f}·{sigma/100:.2f}/√252 = {a:.4f}`"
        unit = "$"
    return dict(prompt=prompt, answer=a, tol=max(0.01, 0.01 * a), unit=unit,
                method=method, page="—")


def g_svi_eval(rng):
    a = float(rng.choice([0.02, 0.04, 0.06]))
    b = float(rng.choice([0.2, 0.3, 0.4]))
    rho = float(rng.choice([-0.5, -0.3, -0.2]))
    m = 0.0
    sig = float(rng.choice([0.10, 0.15, 0.20]))
    T = float(rng.choice([0.25, 0.5, 1.0]))
    k = float(rng.choice([-0.10, 0.0, 0.10, 0.20]))
    w = a + b * (rho * (k - m) + SQRT((k - m) ** 2 + sig ** 2))
    vi = SQRT(max(w, 1e-10) / T) * 100
    prompt = (f"**Formule SVI.** La variance totale est "
              f"`w(k) = a + b·[ρ(k−m) + √((k−m)² + σ²)]` avec "
              f"`a={a}`, `b={b}`, `ρ={rho}`, `m={m}`, `σ={sig}`, `T={T}`.\n\n"
              f"👉 Calcule la **volatilité implicite** en `k = {k}` : "
              f"`VI = √(w/T)` (en %).")
    method = (f"`w = {a} + {b}·[{rho}·({k}) + √(({k})²+{sig}²)] = {w:.5f}` puis "
              f"`VI = √({w:.5f}/{T}) = {vi/100:.5f} = {vi:.4f}%`")
    return dict(prompt=prompt, answer=vi, tol=0.3, unit="%", method=method,
                page="🌐 Surface de volatilité")


def g_as(rng):
    s = float(rng.choice([50, 100, 200]))
    inv = int(rng.choice([-10, -5, 5, 10]))
    gamma = float(rng.choice([0.05, 0.1, 0.2]))
    sig = float(rng.choice([0.15, 0.2, 0.3]))
    tau = float(rng.choice([0.25, 0.5, 1.0]))
    kappa = float(rng.choice([1.0, 1.5, 2.0]))
    ask = str(rng.choice(["reservation", "spread"]))
    if ask == "reservation":
        a = s - inv * gamma * sig ** 2 * tau
        prompt = (f"**Avellaneda–Stoikov — prix de réserve.** Mid `s = {s:.0f}`, "
                  f"inventaire `q = {inv:+d}`, `γ = {gamma}`, `σ = {sig}`, temps "
                  f"restant `τ = {tau}`.\n\n👉 Calcule le **prix de réserve** "
                  f"`r = s − q·γ·σ²·τ`.")
        method = (f"`r = {s:.0f} − ({inv:+d})·{gamma}·{sig}²·{tau} = {a:.5f}`. "
                  f"(Inventaire long ⇒ réserve sous le mid pour se délester.)")
    else:
        a = gamma * sig ** 2 * tau + (2.0 / gamma) * LN(1 + gamma / kappa)
        prompt = (f"**Avellaneda–Stoikov — fourchette optimale.** `γ = {gamma}`, "
                  f"`σ = {sig}`, `τ = {tau}`, `κ = {kappa}`.\n\n👉 Calcule la "
                  f"**fourchette** `δ = γ·σ²·τ + (2/γ)·ln(1 + γ/κ)`.")
        method = (f"`δ = {gamma}·{sig}²·{tau} + (2/{gamma})·ln(1+{gamma}/{kappa}) "
                  f"= {a:.5f}`")
    return dict(prompt=prompt, answer=a, tol=max(0.005, 0.01 * abs(a)), unit="",
                method=method, page="🏦 Tenue de marché")


GENERATORS = [g_forward, g_logmon, g_parity, g_hedge_shares, g_gamma_pnl,
              g_vega_pnl, g_breakeven, g_vol_scaling, g_svi_eval, g_as]


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
st.markdown(f"#### 🧩 Exercice n°{st.session_state['ex_counter']}")
st.info(ex["prompt"])

answered = st.session_state.get("ex_answered", False)
user = st.number_input("Ta réponse" + (f"  ({ex['unit']})" if ex["unit"] else ""),
                       value=0.0, step=0.01, format="%.4f", disabled=answered)

if st.button("✅ Vérifier", disabled=answered):
    ok = abs(float(user) - float(ex["answer"])) <= float(ex["tol"])
    st.session_state["ex_total"] += 1
    if ok:
        st.session_state["ex_correct"] += 1
    st.session_state["ex_answered"] = True
    st.session_state["ex_result"] = ok
    st.rerun()

if answered:
    ok = st.session_state.get("ex_result", False)
    ans_str = f"{ex['answer']:.4f} {ex.get('unit','')}".strip()
    if ok:
        st.success(f"✅ Correct ! Réponse : **{ans_str}**.")
    else:
        st.error(f"❌ Pas tout à fait. Réponse attendue : **{ans_str}**.")
    st.markdown(f"**📐 Méthode :** {ex['method']}")
    if ex.get("page", "—") != "—":
        st.caption(f"💡 Tu peux vérifier ce type de calcul sur la page **{ex['page']}**.")
    st.caption("Clique **🎲 Nouvel exercice** pour continuer.")
