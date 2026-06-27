"""Page 5 · Non-arbitrage & densité risque-neutre — prouver que la surface est négociable."""
import streamlit as st

from utils.state import require_data, push_score, lesson, keypoints
from engine.data import surface_diagnostics, calendar_arbitrage
from engine import viz

st.set_page_config(layout="wide", page_title="Vol Desk", page_icon="📈")
require_data()

meta = st.session_state["meta"]
surface = st.session_state["surface"]

st.title("✅ Non-arbitrage & densité risque-neutre")
st.markdown("Une surface n'est négociable que si elle est **sans arbitrage "
            "statique** : la densité risque-neutre de Breeden–Litzenberger doit "
            "rester non-négative (pas d'arbitrage papillon) et la variance totale "
            "doit être non-décroissante en maturité (pas d'arbitrage calendaire).")

lesson("""
**À quoi sert cette page ?**
C'est le **contrôle qualité** de la surface. Avant de s'y fier, on vérifie qu'elle ne
contient pas d'**incohérences** permettant de gagner de l'argent **sans risque** (un
**arbitrage**). Si la surface « arbitre », tous les signaux des pages suivantes
seraient faux.

Deux contrôles :
- **Arbitrage papillon** : on calcule la **densité risque-neutre** (les probabilités
  implicites des futurs prix de l'action). Elle doit rester **positive** partout — une
  probabilité négative est absurde et trahit un arbitrage.
- **Arbitrage calendaire** : une option plus **lointaine** doit toujours contenir au
  moins autant d'incertitude qu'une plus proche. Sinon, jouer l'une contre l'autre
  serait de l'argent gratuit.

**Les mots :**
- **Arbitrage** : un gain sans risque (ne devrait pas exister sur un marché sain).
- **Densité risque-neutre** : la distribution des futurs prix implicite dans les prix
  d'options (méthode **Breeden–Litzenberger**).

**Comment lire :** ✅ = sain (pas d'arbitrage), ❌ = problème. Sur données
synthétiques, tout doit être ✅ et « 0 violation ».
""")

diag = surface_diagnostics(surface, meta["r"])
cal = calendar_arbitrage(surface)
butterfly_ok = bool(diag["butterfly_ok"].all()) if len(diag) else False
cal_viol = int(cal["violations"].sum()) if len(cal) else 0
push_score(butterfly_ok=butterfly_ok, calendar_violations=cal_viol)

c = st.columns(3)
c[0].metric("Sans arbitrage papillon", "✅ Oui" if butterfly_ok else "❌ Non")
c[1].metric("Violations calendaires", cal_viol)
c[2].metric("RMSE moyen d'ajustement", f"{diag['fit_rmse'].mean()*100:.2f} pv" if len(diag) else "—")

expiries = sorted(surface.keys())
sel = st.multiselect("Échéances à tracer", expiries, default=expiries)
st.plotly_chart(viz.risk_neutral_density(surface, meta, sel), use_container_width=True)

st.subheader("Diagnostics par slice (Breeden–Litzenberger)")
disp = diag.copy()
disp["butterfly_ok"] = disp["butterfly_ok"].map({True: "✅", False: "❌"})
disp = disp.rename(columns={"expiry_dte": "echeance_j", "n_quotes": "n_quotes",
                            "fit_rmse": "rmse", "min_density": "densite_min",
                            "butterfly_ok": "papillon_ok"})
st.dataframe(disp.set_index("echeance_j"), use_container_width=True)

st.subheader("Contrôle des spreads calendaires")
if len(cal):
    sty = cal.style.apply(
        lambda row: ["background-color: rgba(240,97,122,0.25)" if row["violations"] > 0
                     else "" for _ in row], axis=1)
    st.dataframe(sty, use_container_width=True)
else:
    st.info("Il faut au moins deux échéances pour le contrôle calendaire.")

keypoints(
    "- **Breeden–Litzenberger** : `f(K)=e^{rT}·∂²C/∂K²` — la dérivée seconde du prix "
    "du call par rapport au strike *est* la densité risque-neutre. Négative quelque "
    "part ⇒ un papillon vendable gratuitement.\n"
    "- **Condition calendaire** : la variance totale `w(k,T)` doit être "
    "non-décroissante en T à chaque k, sinon un spread calendaire est un arbitrage.\n"
    "- On le **prouve avant de trader** : des signaux de valeur relative calculés sur "
    "une surface qui arbitre n'ont aucun sens.\n"
    "- Tout ✅ + 0 violation = surface **négociable** ; le moindre ❌ invaliderait "
    "les pages suivantes.")
