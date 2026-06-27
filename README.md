# 📈 Vol Desk — Options Volatility & Market-Making Cockpit

An interactive, multipage **Streamlit** cockpit for options-volatility research and
electronic market making. It pulls an options chain, builds an **arbitrage-free SVI
volatility surface**, validates it (Breeden–Litzenberger + calendar checks), screens
**relative value**, simulates **delta-hedged P&L** and the **variance risk premium**,
and quotes as an **Avellaneda–Stoikov market maker**.

Front-end + in-process compute only — **no backend, no database, no API keys**.
Tries live Yahoo Finance; on any failure it falls back to a deterministic synthetic
surface, so it **always runs** (ideal for cloud demos / recruiter review).

## The 9-step journey

```
1 Market Data → 2 Pricing & Greeks → 3 Implied Vol → 4 Vol Surface (SVI)
→ 5 No-Arbitrage → 6 Relative Value → 7 Delta-Hedged P&L → 8 Variance Risk Premium
→ 9 Market Making (+ scorecard)
```

| Page | What it does |
|------|--------------|
| 1 · Market Data | Loads the chain, fits the surface, cockpit KPIs & cleaned IV panel |
| 2 · Pricing & Greeks | Live Black–Scholes pricer + Delta/Gamma/Vega/Theta charts |
| 3 · Implied Vol | Brent IV inversion, raw market smiles, single-option IV calculator |
| 4 · Vol Surface | **Rotatable 3D SVI surface**, per-expiry smile fits, SVI params |
| 5 · No-Arbitrage | Risk-neutral density, butterfly ✅/❌, calendar violations |
| 6 · Relative Value | Rich/cheap z-score screen vs the fair surface |
| 7 · Delta-Hedged P&L | Theta/Gamma/Vega/Hedge-error waterfall + hedged path |
| 8 · Variance Risk Premium | Monte-Carlo P&L distribution: positive mean, fat left tail |
| 9 · Market Making | Avellaneda–Stoikov quoting + a consolidated research scorecard |

## Architecture

```
vol-desk/
├── app.py                  # Page 1 · Market Data & Cockpit Home
├── pages/                  # Pages 2–9 (numeric prefix sets sidebar order)
├── engine/
│   ├── core.py             # BS pricing, Greeks, IV solver, SVI calibration
│   ├── data.py             # chain (yfinance + synthetic), surface fit, no-arb
│   ├── strategy.py         # RV screen, delta-hedge P&L, VRP MC, A–S quoting
│   └── viz.py              # Plotly chart builders (dark research-desk theme)
├── utils/state.py          # sidebar config, cached data/surface, data guard, scorecard
├── .streamlit/config.toml  # dark theme
└── requirements.txt
```

- `engine/core.py`, `engine/data.py`, `engine/strategy.py` are the **validated quant
  engine** (exact put-call parity, exact IV round-trip, SVI recovers its parameters,
  butterfly density ≥ 0, zero calendar violations) — used **verbatim**.
- Each page is a thin UI wrapper: it calls the engine, never re-derives the math, and
  renders everything in **Plotly**. All chart construction lives in `engine/viz.py`.
- `utils/state.py` caches `get_market_data` / `get_surface` so page switches are
  instant; pages 2–9 call `require_data()` which guards with a banner + `st.stop()`.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`. With no network it uses the synthetic surface.

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub.
2. https://share.streamlit.io → **Create app** → pick the repo, branch `main`,
   **Main file path `app.py`**. No secrets required.
3. Deploy. (Advanced → Python 3.12 recommended.)

## Cockpit vs notebook

The original research **notebook is the lab** — exploratory, sequential, matplotlib.
This app is the **cockpit**: the same validated engine, made interactive so a PM or
recruiter can drive the whole workflow live, rotate the surface, re-screen relative
value, and stress the variance-risk-premium tail in real time.

## Where a desk takes this next

SSVI/eSSVI global no-arbitrage calibration · Heston/SABR cross-check with vega hedging
and transaction costs · a live broker feed (IBKR/Polygon) with Greek & inventory risk
limits · a multi-name dispersion/skew scanner with out-of-sample validation.

> Synthetic data is illustrative, not investment advice.
