# 📈 Vol Desk — Cockpit Volatilité Options & Tenue de Marché

Un cockpit **Streamlit** multipage et interactif pour la recherche sur la volatilité
des options et la tenue de marché électronique. Il récupère une chaîne d'options,
construit une **surface de volatilité SVI sans arbitrage**, la valide
(Breeden–Litzenberger + contrôles calendaires), screene la **valeur relative**,
simule le **P&L delta-couvert** et la **prime de risque de variance**, et cote en
**teneur de marché Avellaneda–Stoikov**.

Front-end + calcul en process uniquement — **pas de backend, pas de base de données,
aucune clé API**. Essaie Yahoo Finance en direct ; sur toute défaillance, repli sur
une surface synthétique déterministe, donc l'app **tourne toujours** (idéal pour une
démo cloud / revue par un recruteur).

## Le parcours en 9 étapes

```
1 Données de marché → 2 Valorisation & Grecques → 3 Vol implicite → 4 Surface (SVI)
→ 5 Non-arbitrage → 6 Valeur relative → 7 P&L delta-couvert → 8 Prime risque variance
→ 9 Tenue de marché (+ scorecard)
```

| Page | Rôle |
|------|------|
| 1 · Données de marché | Charge la chaîne, ajuste la surface, KPI & panel IV nettoyé |
| 2 · Valorisation & Grecques | Pricer Black–Scholes live + graphes Delta/Gamma/Vega/Theta |
| 3 · Vol implicite | Inversion Brent, smiles marché, calculateur de VI |
| 4 · Surface de vol | **Surface SVI 3D rotative**, smiles par échéance, paramètres SVI |
| 5 · Non-arbitrage | Densité risque-neutre, papillon ✅/❌, violations calendaires |
| 6 · Valeur relative | Screen cher/bon marché par z-score vs la surface juste |
| 7 · P&L delta-couvert | Cascade Theta/Gamma/Vega/Erreur + trajectoire couverte |
| 8 · Prime risque variance | Distribution MC du P&L : moyenne positive, queue gauche épaisse |
| 9 · Tenue de marché | Cotation Avellaneda–Stoikov + scorecard de recherche consolidé |

## Architecture

```
vol-desk/
├── app.py                  # Page 1 · Données de marché & Accueil du cockpit
├── pages/                  # Pages 2–9 (le préfixe numérique fixe l'ordre sidebar)
├── engine/
│   ├── core.py             # Pricing BS, Grecques, solveur VI, calibration SVI
│   ├── data.py             # chaîne (yfinance + synthétique), fit surface, non-arb
│   ├── strategy.py         # screen VR, P&L delta-couvert, MC VRP, cotation A–S
│   └── viz.py              # constructeurs de graphiques Plotly (thème sombre)
├── utils/state.py          # config sidebar, cache data/surface, guard, scorecard
├── .streamlit/config.toml  # thème sombre
└── requirements.txt
```

- `engine/core.py`, `engine/data.py`, `engine/strategy.py` sont le **moteur quant
  validé** (parité put-call exacte, round-trip VI exact, SVI récupère ses paramètres,
  densité ≥ 0, zéro violation calendaire) — utilisés **verbatim**.
- Chaque page est un wrapper UI fin : elle appelle le moteur, ne re-dérive jamais les
  maths, et rend tout en **Plotly**. Toute la construction graphique vit dans
  `engine/viz.py`.
- `utils/state.py` cache `get_market_data` / `get_surface` pour que les changements de
  page soient instantanés ; les pages 2–9 appellent `require_data()` qui garde avec
  une bannière + `st.stop()`.

## Lancer en local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Ouvre sur `http://localhost:8501`. Sans réseau, l'app utilise la surface synthétique.

## Déployer sur Streamlit Community Cloud

1. Pousser ce repo sur GitHub.
2. https://share.streamlit.io → **Create app** → choisir le repo, branche `main`,
   **Main file path `app.py`**. Aucun secret requis.
3. Déployer. (Advanced → Python 3.12 recommandé.)

## Cockpit vs notebook

Le **notebook de recherche est le labo** — exploratoire, séquentiel, matplotlib.
Cette app est le **cockpit** : le même moteur validé, rendu interactif pour qu'un PM
ou un recruteur pilote tout le workflow en direct, fasse tourner la surface, re-screene
la valeur relative et stresse la queue de la prime de risque de variance en temps réel.

## Là où un desk pousse ça plus loin

Calibration globale SSVI/eSSVI sans arbitrage · cross-check Heston/SABR avec couverture
vega et coûts de transaction · un flux broker en direct (IBKR/Polygon) avec limites de
risque Greeks & inventaire · un scanner dispersion/skew multi-noms avec validation
hors-échantillon.

> Les données synthétiques sont illustratives, pas un conseil en investissement.
