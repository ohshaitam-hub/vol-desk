"""
engine/core.py
Core option-pricing, Greeks, implied-vol, and SVI-calibration machinery.
Pure NumPy/SciPy so it runs anywhere (Colab, local, CI).
"""
from __future__ import annotations
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq, minimize
from dataclasses import dataclass

# ----------------------------------------------------------------------
# 1. Black–Scholes–Merton pricing and closed-form Greeks
# ----------------------------------------------------------------------
SQRT_2PI = np.sqrt(2.0 * np.pi)


def _d1_d2(S, K, T, r, sigma, q=0.0):
    """Return the d1, d2 terms of Black–Scholes. Vectorised over arrays."""
    S, K, T, sigma = map(np.asarray, (S, K, T, sigma))
    # Guard against degenerate inputs that would divide by zero.
    vol_sqrt_t = np.maximum(sigma * np.sqrt(T), 1e-12)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    return d1, d2


def bs_price(S, K, T, r, sigma, q=0.0, option="call"):
    """Black–Scholes price for a European call or put (continuous dividend q)."""
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    disc_r, disc_q = np.exp(-r * T), np.exp(-q * T)
    if option == "call":
        return S * disc_q * norm.cdf(d1) - K * disc_r * norm.cdf(d2)
    elif option == "put":
        return K * disc_r * norm.cdf(-d2) - S * disc_q * norm.cdf(-d1)
    raise ValueError("option must be 'call' or 'put'")


def bs_greeks(S, K, T, r, sigma, q=0.0, option="call"):
    """Return a dict of the primary Greeks (per-year theta, per-1-vol-point vega)."""
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    disc_r, disc_q = np.exp(-r * T), np.exp(-q * T)
    pdf_d1 = norm.pdf(d1)

    gamma = disc_q * pdf_d1 / (S * sigma * np.sqrt(T))
    vega = S * disc_q * pdf_d1 * np.sqrt(T)            # per 1.00 change in vol
    if option == "call":
        delta = disc_q * norm.cdf(d1)
        theta = (-S * disc_q * pdf_d1 * sigma / (2 * np.sqrt(T))
                 - r * K * disc_r * norm.cdf(d2)
                 + q * S * disc_q * norm.cdf(d1))
        rho = K * T * disc_r * norm.cdf(d2)
    else:
        delta = -disc_q * norm.cdf(-d1)
        theta = (-S * disc_q * pdf_d1 * sigma / (2 * np.sqrt(T))
                 + r * K * disc_r * norm.cdf(-d2)
                 - q * S * disc_q * norm.cdf(-d1))
        rho = -K * T * disc_r * norm.cdf(-d2)
    return {"delta": delta, "gamma": gamma, "vega": vega,
            "theta": theta, "rho": rho}


# ----------------------------------------------------------------------
# 2. Implied-volatility solver (robust Brent root-finding)
# ----------------------------------------------------------------------
def implied_vol(price, S, K, T, r, q=0.0, option="call",
                lo=1e-4, hi=5.0):
    """
    Back out Black–Scholes implied vol from a market price.
    Returns np.nan when the price is outside no-arbitrage bounds or the
    solver fails to bracket a root (illiquid / stale quotes).
    """
    # Intrinsic-value (no-arbitrage) bounds — reject garbage quotes early.
    disc_r, disc_q = np.exp(-r * T), np.exp(-q * T)
    if option == "call":
        intrinsic = max(S * disc_q - K * disc_r, 0.0)
        upper = S * disc_q
    else:
        intrinsic = max(K * disc_r - S * disc_q, 0.0)
        upper = K * disc_r
    if not (intrinsic - 1e-8 <= price <= upper + 1e-8):
        return np.nan

    objective = lambda sig: bs_price(S, K, T, r, sig, q, option) - price
    try:
        f_lo, f_hi = objective(lo), objective(hi)
        if f_lo * f_hi > 0:          # root not bracketed
            return np.nan
        return brentq(objective, lo, hi, maxiter=100, xtol=1e-8)
    except (ValueError, RuntimeError):
        return np.nan


# ----------------------------------------------------------------------
# 3. SVI volatility-surface parameterisation (Gatheral raw form)
# ----------------------------------------------------------------------
@dataclass
class SVIParams:
    """Raw-SVI parameters for a single expiry slice."""
    a: float       # vertical level of total variance
    b: float       # angle / wing slope (b >= 0)
    rho: float     # skew / rotation (|rho| < 1)
    m: float       # horizontal translation
    sigma: float   # ATM curvature smoothness (sigma > 0)

    def as_tuple(self):
        return (self.a, self.b, self.rho, self.m, self.sigma)


def svi_total_variance(k, p: SVIParams):
    """Total implied variance w(k) = sigma_BS^2 * T for log-moneyness k."""
    a, b, rho, m, sigma = p.as_tuple()
    return a + b * (rho * (k - m) + np.sqrt((k - m) ** 2 + sigma ** 2))


def svi_implied_vol(k, T, p: SVIParams):
    """Convert SVI total variance to Black–Scholes implied vol."""
    w = np.maximum(svi_total_variance(k, p), 1e-10)
    return np.sqrt(w / T)


def calibrate_svi(k, iv, T, weights=None):
    """
    Fit raw-SVI parameters to a single expiry's (log-moneyness, IV) points by
    weighted least squares on total variance. Returns an SVIParams object.

    Uses a multi-start L-BFGS-B optimisation to avoid poor local minima — SVI
    objective surfaces are notoriously non-convex.
    """
    k = np.asarray(k, dtype=float)
    iv = np.asarray(iv, dtype=float)
    w_target = (iv ** 2) * T                      # observed total variance
    if weights is None:
        weights = np.ones_like(k)

    def loss(theta):
        a, b, rho, m, sig = theta
        p = SVIParams(a, b, rho, m, sig)
        w_model = svi_total_variance(k, p)
        return np.sum(weights * (w_model - w_target) ** 2)

    # Parameter bounds keep the fit economically sensible & arbitrage-friendlier.
    var_atm = float(np.nanmedian(w_target))
    bounds = [(1e-6, max(var_atm * 5, 1.0)),   # a
              (1e-4, 5.0),                       # b
              (-0.999, 0.999),                   # rho
              (-1.0, 1.0),                        # m
              (1e-4, 2.0)]                        # sigma

    best, best_loss = None, np.inf
    rng = np.random.default_rng(7)
    starts = [(var_atm, 0.1, -0.5, 0.0, 0.1)]   # sensible default start
    for _ in range(12):                          # + random restarts
        starts.append((max(var_atm * rng.uniform(0.3, 1.5), 1e-4),
                       rng.uniform(0.05, 1.0),
                       rng.uniform(-0.9, 0.5),
                       rng.uniform(-0.3, 0.3),
                       rng.uniform(0.02, 0.4)))
    for s in starts:
        try:
            res = minimize(loss, s, method="L-BFGS-B", bounds=bounds)
            if res.fun < best_loss:
                best_loss, best = res.fun, res.x
        except Exception:
            continue
    if best is None:
        raise RuntimeError("SVI calibration failed to converge.")
    return SVIParams(*best)
