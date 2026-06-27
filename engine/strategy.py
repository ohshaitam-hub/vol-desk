"""
engine/strategy.py
The trading-research layer that sits on top of the fitted surface:
  - relative-value (RV) mispricing detection vs the arbitrage-free surface
  - delta-hedged P&L simulation with full Greek attribution
  - Avellaneda–Stoikov inventory-aware quoting
  - variance-risk-premium (VRP) capture analysis
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from engine.core import bs_price, bs_greeks, svi_implied_vol


# ----------------------------------------------------------------------
# 1. Relative-value screen: market IV vs arbitrage-free surface IV
# ----------------------------------------------------------------------
def relative_value_screen(iv_panel: pd.DataFrame, surface: dict,
                          z_threshold=1.5):
    """
    For every quoted option, compare its market IV to the SVI surface fair IV.
    Standardise the residual within each expiry (a per-slice z-score) and flag
    contracts that are statistically rich (sell) or cheap (buy).

    A market maker uses exactly this signal: quote *around* the fair surface and
    lean against names that have drifted away from it.
    """
    out = []
    for dte, g in iv_panel.groupby("expiry_dte"):
        if dte not in surface:
            continue
        s = surface[dte]
        fair_iv = svi_implied_vol(g["log_moneyness"].values, s["T"], s["params"])
        resid = g["iv"].values - fair_iv
        sd = resid.std(ddof=1) if resid.std(ddof=1) > 1e-9 else 1e-9
        z = resid / sd
        gg = g.copy()
        gg["fair_iv"] = fair_iv
        gg["iv_resid"] = resid
        gg["iv_zscore"] = z
        gg["signal"] = np.where(z > z_threshold, "SELL_VOL",
                        np.where(z < -z_threshold, "BUY_VOL", "FAIR"))
        out.append(gg)
    res = pd.concat(out, ignore_index=True)
    return res.sort_values("iv_zscore").reset_index(drop=True)


# ----------------------------------------------------------------------
# 2. Delta-hedged P&L simulation with Greek attribution
# ----------------------------------------------------------------------
def simulate_delta_hedged_pnl(S0, K, T, r, q, iv_implied, iv_realized,
                              option="call", position=-1.0,
                              n_steps=252, rehedge_every=1, seed=0):
    """
    Simulate a discretely delta-hedged option position over its life.

    The underlying is simulated under the *realized* vol; the option is priced
    and hedged using the *implied* vol it was sold at. This is the classic
    short-gamma / variance-risk-premium experiment.

    Returns a tidy DataFrame (path-level) plus an attribution dict:
        theta_pnl   : deterministic time decay collected
        gamma_pnl   : P&L from realized moves vs the gamma the book carries
        vega_pnl    : P&L from the implied-vol mark moving (0 if iv constant)
        hedge_error : residual from discrete (not continuous) rehedging
        total_pnl   : sum of the above (== realised path P&L)

    position = -1.0 means SHORT one option (the seller / market maker).
    """
    rng = np.random.default_rng(seed)
    dt = T / n_steps
    # GBM path under realized vol.
    z = rng.standard_normal(n_steps)
    log_ret = (r - q - 0.5 * iv_realized ** 2) * dt + iv_realized * np.sqrt(dt) * z
    S = S0 * np.exp(np.cumsum(np.insert(log_ret, 0, 0.0)))
    times = np.linspace(0, T, n_steps + 1)
    ttm = np.maximum(T - times, 1e-8)

    rows = []
    cash = 0.0
    hedge_pos = 0.0                                   # shares held to hedge
    opt0 = bs_price(S0, K, T, r, iv_implied, q, option)
    cash += -position * opt0                          # receive premium if short

    theta_acc = gamma_acc = vega_acc = 0.0
    prev_S = S0
    for i in range(n_steps + 1):
        g = bs_greeks(S[i], K, ttm[i], r, iv_implied, q, option)
        opt_val = bs_price(S[i], K, ttm[i], r, iv_implied, q, option)

        # Greek attribution increments (relative to previous step).
        if i > 0:
            dS = S[i] - prev_S
            # gamma P&L on the *option* leg the book is short/long
            gamma_acc += 0.5 * position * g["gamma"] * dS ** 2
            theta_acc += position * g["theta"] * dt
        prev_S = S[i]

        # Rehedge to delta-neutral on the schedule.
        if i % rehedge_every == 0 or i == n_steps:
            target = -position * g["delta"]           # offset option delta
            trade = target - hedge_pos
            cash -= trade * S[i]                       # pay/receive for shares
            hedge_pos = target

        rows.append(dict(t=times[i], S=S[i], ttm=ttm[i],
                         opt_val=opt_val, delta=g["delta"],
                         gamma=g["gamma"], vega=g["vega"],
                         hedge_pos=hedge_pos, cash=cash))

    path = pd.DataFrame(rows)
    # Terminal mark-to-market: close option + liquidate hedge.
    terminal = path["cash"].iloc[-1] + position * path["opt_val"].iloc[-1] \
        + hedge_pos * S[-1]
    total = terminal
    # Theoretical short-gamma decomposition (continuous-hedging benchmark).
    hedge_error = total - (theta_acc + gamma_acc)
    attribution = dict(theta_pnl=theta_acc, gamma_pnl=gamma_acc,
                       vega_pnl=vega_acc, hedge_error=hedge_error,
                       total_pnl=total, premium=-position * opt0)
    return path, attribution


def vrp_monte_carlo(S0, K, T, r, q, iv_implied, iv_realized_mean,
                    option="call", n_paths=2000, n_steps=63,
                    vol_of_vol=0.35, jump_prob=0.04, jump_size=0.08,
                    seed=1):
    """
    Monte-Carlo distribution of delta-hedged short-vol P&L with *stochastic*
    realized volatility, so the tail is honest.

    Each path draws its own realized vol from a lognormal around
    `iv_realized_mean` (dispersion = vol_of_vol) and, with probability
    `jump_prob`, suffers a vol spike of `jump_size`. This reproduces the real
    shape of selling vol: a positive mean (the variance risk premium) with a
    heavy left tail (the occasional vol blow-up that hurts short gamma).

    Returns (pnl_array, realized_vol_array).
    """
    rng = np.random.default_rng(seed)
    # Lognormal realized-vol draws preserve positivity and right-skew.
    mu = np.log(iv_realized_mean) - 0.5 * vol_of_vol ** 2
    rv = rng.lognormal(mu, vol_of_vol, n_paths)
    jumps = rng.random(n_paths) < jump_prob
    rv = rv + jumps * jump_size                        # vol-spike regime

    pnl = np.empty(n_paths)
    for i in range(n_paths):
        _, attr = simulate_delta_hedged_pnl(
            S0, K, T, r, q, iv_implied, float(rv[i]), option,
            position=-1.0, n_steps=n_steps, seed=seed + i)
        pnl[i] = attr["total_pnl"]
    return pnl, rv


# ----------------------------------------------------------------------
# 3. Avellaneda–Stoikov inventory-aware market-making
# ----------------------------------------------------------------------
def avellaneda_stoikov_quotes(mid, inventory, sigma, T_remaining,
                              gamma=0.1, kappa=1.5):
    """
    Avellaneda–Stoikov optimal quotes for a single instrument.

    reservation price  r = s - q * gamma * sigma^2 * (T - t)
    optimal spread     d = gamma*sigma^2*(T-t) + (2/gamma) * ln(1 + gamma/kappa)

    The reservation price skews quotes against current inventory (a long book
    quotes lower to offload risk); the spread widens with risk aversion gamma,
    volatility sigma, and time-to-horizon.

    Returns dict(reservation, bid, ask, spread, skew).
    """
    tau = max(T_remaining, 1e-6)
    reservation = mid - inventory * gamma * sigma ** 2 * tau
    spread = gamma * sigma ** 2 * tau + (2.0 / gamma) * np.log(1 + gamma / kappa)
    bid = reservation - spread / 2
    ask = reservation + spread / 2
    return dict(reservation=reservation, bid=bid, ask=ask,
                spread=spread, skew=reservation - mid)


def simulate_market_making(mid0, sigma, T=1.0, n_steps=500,
                           gamma=0.1, kappa=1.5, arrival_A=140.0,
                           seed=3):
    """
    Simulate an AS market maker quoting a single instrument as its price
    diffuses. Order arrivals follow a Poisson intensity that decays with quote
    distance: lambda = A * exp(-kappa * delta). Tracks inventory, cash, and the
    quote stream so we can visualise inventory-aware skewing.
    """
    rng = np.random.default_rng(seed)
    dt = T / n_steps
    price = mid0
    inventory = 0.0
    cash = 0.0
    rows = []
    for i in range(n_steps + 1):
        tau = T - i * dt
        q = avellaneda_stoikov_quotes(price, inventory, sigma, tau,
                                      gamma, kappa)
        d_bid = price - q["bid"]
        d_ask = q["ask"] - price
        # Fill probabilities this step (Poisson thinning).
        p_buy = 1 - np.exp(-arrival_A * np.exp(-kappa * d_bid) * dt)   # we buy
        p_sell = 1 - np.exp(-arrival_A * np.exp(-kappa * d_ask) * dt)  # we sell
        if rng.random() < p_buy:
            inventory += 1
            cash -= q["bid"]
        if rng.random() < p_sell:
            inventory -= 1
            cash += q["ask"]
        pnl = cash + inventory * price
        rows.append(dict(t=i * dt, price=price, reservation=q["reservation"],
                         bid=q["bid"], ask=q["ask"], inventory=inventory,
                         cash=cash, pnl=pnl, skew=q["skew"]))
        # Diffuse the mid for the next step.
        price += sigma * price * np.sqrt(dt) * rng.standard_normal()
    return pd.DataFrame(rows)
