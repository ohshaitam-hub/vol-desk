"""
engine/data.py
Options-chain acquisition (live yfinance with a deterministic synthetic
fallback) and full surface construction: per-expiry SVI fits, no-arbitrage
diagnostics, and the Breeden–Litzenberger risk-neutral density.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from engine.core import (bs_price, implied_vol, calibrate_svi,
                         svi_implied_vol, svi_total_variance, SVIParams)


# ----------------------------------------------------------------------
# 1. Synthetic chain generator (used when the live API is unavailable)
# ----------------------------------------------------------------------
def _parametric_smile(k, T):
    """
    A realistic equity-index implied-vol smile in (log-moneyness, maturity).
    Markets are NOT exactly SVI, so we generate from a quadratic-in-k smile with
    a maturity-dependent level, skew, and curvature — then let the pipeline fit
    SVI to it. This mirrors real calibration (fitting a model to market data).

      level  : ATM vol, rises mildly with sqrt(T)   (upward term structure)
      skew   : negative (OTM puts bid), steep short-dated, flatter long-dated
      curv   : smile convexity, larger short-dated
    """
    level = 0.17 + 0.025 * np.sqrt(T)
    skew = -0.30 * np.exp(-1.0 * T) - 0.10
    curv = 0.30 * np.exp(-1.5 * T) + 0.10
    iv = level + skew * k + curv * k ** 2
    return np.clip(iv, 0.05, 1.5)


def synthetic_chain(spot=450.0, r=0.045, q=0.013, seed=42):
    """
    Build a realistic equity-index option chain from a parametric market smile,
    adding quote micro-noise and a bid/ask spread so the downstream pipeline has
    to re-discover the surface exactly as it would with messy market data.

    Returns (chain_df, meta) where meta carries spot/r/q and the truth function.
    """
    rng = np.random.default_rng(seed)
    expiries_days = np.array([30, 60, 90, 180, 365])
    rows = []
    for dte in expiries_days:
        T = dte / 365.0
        fwd = spot * np.exp((r - q) * T)
        strikes = np.round(np.linspace(0.70, 1.30, 31) * spot)
        for K in strikes:
            k = np.log(K / fwd)                       # log-moneyness vs forward
            iv = float(_parametric_smile(k, T))
            iv = max(iv + rng.normal(0, 0.0015), 0.03)  # quote micro-noise
            opt = "call" if K >= spot else "put"        # OTM side, like markets
            mid = bs_price(spot, K, T, r, iv, q, opt)
            spread = max(0.02 * mid, 0.05)              # realistic bid/ask
            rows.append(dict(expiry_dte=int(dte), T=T, strike=float(K),
                             type=opt, forward=fwd,
                             bid=max(mid - spread / 2, 0.0),
                             ask=mid + spread / 2,
                             mid=mid,
                             volume=int(max(rng.normal(500, 300), 1)),
                             open_interest=int(max(rng.normal(2000, 1500), 1))))
    chain = pd.DataFrame(rows)
    meta = dict(spot=spot, r=r, q=q, source="synthetic",
                asof=datetime.now(timezone.utc), truth=_parametric_smile)
    return chain, meta


# ----------------------------------------------------------------------
# 2. Live chain via yfinance — falls back to synthetic on any failure
# ----------------------------------------------------------------------
def fetch_chain(ticker="SPY", max_expiries=6, r=0.045, q=0.013,
                verbose=True):
    """
    Try to pull a live options chain from Yahoo Finance. yfinance is
    unofficial and frequently rate-limited, so ANY failure (import, network,
    empty data) cleanly degrades to a reproducible synthetic chain.
    """
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)
        spot = float(tk.fast_info["last_price"])
        expiries = tk.options[:max_expiries]
        if not expiries:
            raise RuntimeError("no expiries returned")

        rows = []
        today = datetime.now(timezone.utc).date()
        for exp in expiries:
            dte = (datetime.strptime(exp, "%Y-%m-%d").date() - today).days
            if dte <= 0:
                continue
            T = dte / 365.0
            fwd = spot * np.exp((r - q) * T)
            oc = tk.option_chain(exp)
            for df, typ in ((oc.calls, "call"), (oc.puts, "put")):
                for _, row in df.iterrows():
                    bid, ask = row.get("bid", 0), row.get("ask", 0)
                    if bid <= 0 or ask <= 0 or ask < bid:
                        continue                      # skip stale/crossed quotes
                    mid = 0.5 * (bid + ask)
                    rows.append(dict(expiry_dte=dte, T=T, strike=float(row["strike"]),
                                     type=typ, forward=fwd, bid=bid, ask=ask, mid=mid,
                                     volume=int(row.get("volume", 0) or 0),
                                     open_interest=int(row.get("openInterest", 0) or 0)))
        if not rows:
            raise RuntimeError("no valid quotes after cleaning")
        chain = pd.DataFrame(rows)
        meta = dict(spot=spot, r=r, q=q, source=f"yfinance:{ticker}",
                    asof=datetime.now(timezone.utc), truth=None)
        if verbose:
            print(f"[data] Live chain for {ticker}: {len(chain)} quotes, "
                  f"spot={spot:.2f}, {chain.expiry_dte.nunique()} expiries")
        return chain, meta
    except Exception as e:                            # graceful degradation
        if verbose:
            print(f"[data] Live fetch failed ({type(e).__name__}: {e}). "
                  f"Falling back to synthetic chain.")
        return synthetic_chain()


# ----------------------------------------------------------------------
# 3. Clean a raw chain into a usable implied-vol panel
# ----------------------------------------------------------------------
def clean_and_imply(chain: pd.DataFrame, meta: dict,
                    min_vol=0, moneyness=(0.75, 1.25)):
    """
    Filter illiquid/extreme quotes and compute mid-price implied vol and
    log-moneyness for every surviving option. Returns an enriched DataFrame.
    """
    spot, r, q = meta["spot"], meta["r"], meta["q"]
    df = chain.copy()

    # Liquidity + sanity filters.
    df = df[(df["mid"] > 0.01) & (df["bid"] >= 0) & (df["ask"] >= df["bid"])]
    df = df[df["volume"] >= min_vol]
    df["log_moneyness"] = np.log(df["strike"] / df["forward"])
    df = df[(df["strike"] / spot).between(*moneyness)]

    # Vectorised IV inversion via list comp (Brent isn't vectorisable directly).
    ivs = [implied_vol(row.mid, spot, row.strike, row.T, r, q, row.type)
           for row in df.itertuples()]
    df["iv"] = ivs
    df = df.dropna(subset=["iv"])
    df = df[(df["iv"] > 0.02) & (df["iv"] < 2.0)]      # drop solver outliers
    return df.reset_index(drop=True)


# ----------------------------------------------------------------------
# 4. Fit one SVI slice per expiry -> the full surface
# ----------------------------------------------------------------------
def fit_surface(iv_panel: pd.DataFrame, meta: dict):
    """
    Calibrate a raw-SVI slice for each expiry. Weight points by a Gaussian in
    log-moneyness so the liquid near-the-money region dominates the fit.
    Returns {dte: dict(params, T, forward, rmse, n)}.
    """
    surface = {}
    for dte, g in iv_panel.groupby("expiry_dte"):
        if len(g) < 5:                                # too few points to fit
            continue
        k = g["log_moneyness"].values
        iv = g["iv"].values
        T = float(g["T"].iloc[0])
        weights = np.exp(-(k ** 2) / (2 * 0.15 ** 2)) + 0.05
        try:
            p = calibrate_svi(k, iv, T, weights)
        except RuntimeError:
            continue
        iv_model = svi_implied_vol(k, T, p)
        rmse = float(np.sqrt(np.mean((iv_model - iv) ** 2)))
        surface[int(dte)] = dict(params=p, T=T,
                                 forward=float(g["forward"].iloc[0]),
                                 rmse=rmse, n=len(g))
    return surface


# ----------------------------------------------------------------------
# 5. No-arbitrage diagnostics
# ----------------------------------------------------------------------
def butterfly_density(params: SVIParams, T, forward, r,
                      k_grid=None):
    """
    Risk-neutral density via Breeden–Litzenberger: f(K) = e^{rT} d^2C/dK^2.
    A negative density anywhere = butterfly (static) arbitrage in that slice.
    Returns (strikes, density).
    """
    if k_grid is None:
        k_grid = np.linspace(-0.6, 0.6, 400)
    strikes = forward * np.exp(k_grid)
    iv = svi_implied_vol(k_grid, T, params)
    call = bs_price(forward * np.exp(-r * T), strikes, T, r, iv, 0.0, "call")
    # second derivative wrt strike (finite difference on a fine grid)
    dK = np.gradient(strikes)
    d2C = np.gradient(np.gradient(call, strikes), strikes)
    density = np.exp(r * T) * d2C
    return strikes, density


def calendar_arbitrage(surface, k_grid=None):
    """
    Check the calendar-spread condition: total implied variance w(k,T) must be
    non-decreasing in T at every log-moneyness k. Returns a tidy report.
    """
    if k_grid is None:
        k_grid = np.linspace(-0.3, 0.3, 13)
    dtes = sorted(surface.keys())
    report = []
    for i in range(len(dtes) - 1):
        p1, p2 = surface[dtes[i]]["params"], surface[dtes[i + 1]]["params"]
        w1 = svi_total_variance(k_grid, p1)
        w2 = svi_total_variance(k_grid, p2)
        violations = int(np.sum(w2 < w1 - 1e-6))
        report.append(dict(near=dtes[i], far=dtes[i + 1],
                           violations=violations, n=len(k_grid)))
    return pd.DataFrame(report)


def surface_diagnostics(surface, r):
    """Aggregate butterfly + fit-quality diagnostics across all slices."""
    rows = []
    for dte, s in sorted(surface.items()):
        _, dens = butterfly_density(s["params"], s["T"], s["forward"], r)
        rows.append(dict(expiry_dte=dte, T=round(s["T"], 3), n_quotes=s["n"],
                         fit_rmse=round(s["rmse"], 5),
                         min_density=round(float(np.min(dens)), 6),
                         butterfly_ok=bool(np.min(dens) > -1e-6)))
    return pd.DataFrame(rows)
