"""
engine/viz.py
Plotly chart builders — a web-interactive port of the validated matplotlib
reference (Appendix B). Same data, same intent, interactive rendering.
Every function returns a go.Figure styled with the dark research-desk theme.
"""
from __future__ import annotations
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from engine.core import svi_implied_vol, bs_price, bs_greeks
from engine.data import butterfly_density

# ----------------------------------------------------------------------
# House style (mirrors .streamlit/config.toml)
# ----------------------------------------------------------------------
BG = "#0d1117"; PANEL = "#161b22"; FG = "#e6edf3"; GRID = "#283039"
ACCENT = "#58a6ff"; SELL = "#f0617a"; BUY = "#3fb950"; MUTE = "#8b949e"
SIGNAL_COLORS = {"FAIR": MUTE, "SELL_VOL": SELL, "BUY_VOL": BUY}


def _dark(fig, title=None, height=None, legend=True):
    fig.update_layout(
        template="plotly_dark", title=title, height=height,
        paper_bgcolor=BG, plot_bgcolor=BG, font=dict(color=FG, family="monospace"),
        margin=dict(l=10, r=10, t=46 if title else 16, b=10),
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", yanchor="bottom",
                    y=1.02, x=0) if legend else dict(),
        colorway=[ACCENT, SELL, BUY, "#d29922", "#a371f7", MUTE],
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    return fig


# ======================================================================
# Page 2 — Pricing & Greeks
# ======================================================================
def price_vs_spot(K, T, r, sigma, q, option, spot, width=0.4):
    S = np.linspace(spot * (1 - width), spot * (1 + width), 200)
    price = bs_price(S, K, T, r, sigma, q, option)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=S, y=price, mode="lines", name="BS price",
                             line=dict(color=ACCENT, width=2.5)))
    fig.add_vline(x=spot, line_dash="dash", line_color=MUTE)
    fig.add_vline(x=K, line_dash="dot", line_color=BUY)
    fig.update_xaxes(title="Spot S"); fig.update_yaxes(title="Option price")
    return _dark(fig, "Option price vs spot", 360)


def greeks_grid(K, T, r, sigma, q, option, spot, width=0.4):
    S = np.linspace(spot * (1 - width), spot * (1 + width), 200)
    g = bs_greeks(S, K, T, r, sigma, q, option)
    fig = make_subplots(rows=2, cols=2,
                        subplot_titles=("Delta", "Gamma", "Vega", "Theta / day"))
    series = [("delta", g["delta"], 1, 1), ("gamma", g["gamma"], 1, 2),
              ("vega", g["vega"], 2, 1), ("theta", g["theta"] / 365.0, 2, 2)]
    colors = [ACCENT, BUY, "#d29922", SELL]
    for (name, y, rr, cc), col in zip(series, colors):
        fig.add_trace(go.Scatter(x=S, y=y, mode="lines", name=name,
                                 line=dict(color=col, width=2)), row=rr, col=cc)
        fig.add_vline(x=spot, line_dash="dash", line_color=MUTE, row=rr, col=cc)
    fig.update_layout(showlegend=False)
    return _dark(fig, "Greeks vs spot", 460, legend=False)


def payoff_at_expiry(K, option, spot, premium=0.0, position=1.0, width=0.4):
    S = np.linspace(spot * (1 - width), spot * (1 + width), 200)
    intrinsic = np.maximum(S - K, 0) if option == "call" else np.maximum(K - S, 0)
    payoff = position * (intrinsic - premium)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=S, y=payoff, mode="lines", name="Payoff @ expiry",
                             line=dict(color=BUY, width=2.5)))
    fig.add_hline(y=0, line_color=MUTE)
    fig.add_vline(x=K, line_dash="dot", line_color=ACCENT)
    fig.update_xaxes(title="Spot at expiry"); fig.update_yaxes(title="P&L")
    return _dark(fig, "Payoff at expiry", 320)


# ======================================================================
# Page 3 — Implied Volatility
# ======================================================================
def iv_market_scatter(iv_panel, dte):
    g = iv_panel[iv_panel["expiry_dte"] == dte].sort_values("log_moneyness")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=g["log_moneyness"], y=g["iv"] * 100, mode="markers",
                             marker=dict(color=ACCENT, size=8,
                                         line=dict(width=0)), name="Market IV",
                             text=g["strike"], hovertemplate="K=%{text}<br>"
                             "ln(K/F)=%{x:.3f}<br>IV=%{y:.2f}%"))
    fig.add_vline(x=0, line_dash="dash", line_color=MUTE)
    fig.update_xaxes(title="log-moneyness  ln(K/F)")
    fig.update_yaxes(title="Implied vol (%)")
    return _dark(fig, f"Market implied-vol smile · {dte}d", 380)


# ======================================================================
# Page 4 — Volatility Surface (SVI)
# ======================================================================
def vol_surface_3d(surface, meta):
    k_grid = np.linspace(-0.35, 0.35, 60)
    dtes = sorted(surface.keys())
    mats = [surface[d]["T"] for d in dtes]
    Z = np.array([svi_implied_vol(k_grid, surface[d]["T"], surface[d]["params"]) * 100
                  for d in dtes])
    fig = go.Figure(go.Surface(
        x=k_grid, y=mats, z=Z, colorscale="Viridis",
        colorbar=dict(title="IV %"), contours={"z": {"show": True,
                      "usecolormap": True, "highlightcolor": FG, "project_z": True}}))
    fig.update_layout(
        template="plotly_dark", paper_bgcolor=BG, font=dict(color=FG, family="monospace"),
        height=560, margin=dict(l=0, r=0, t=46, b=0),
        title=f"Arbitrage-free implied-volatility surface · {meta['source']}",
        scene=dict(xaxis_title="ln(K/F)", yaxis_title="Maturity (yrs)",
                   zaxis_title="IV (%)", bgcolor=BG,
                   xaxis=dict(gridcolor=GRID), yaxis=dict(gridcolor=GRID),
                   zaxis=dict(gridcolor=GRID),
                   camera=dict(eye=dict(x=1.5, y=-1.6, z=0.9))))
    return fig


def smiles_grid(iv_panel, surface, dtes):
    dtes = [d for d in sorted(dtes) if d in surface]
    if not dtes:
        return _dark(go.Figure(), "No expiry selected", 300)
    n = len(dtes); cols = min(3, n); rows = int(np.ceil(n / cols))
    titles = [f"{d}d · RMSE {surface[d]['rmse']*100:.2f} vp" for d in dtes]
    fig = make_subplots(rows=rows, cols=cols, subplot_titles=titles,
                        horizontal_spacing=0.08, vertical_spacing=0.16)
    for idx, d in enumerate(dtes):
        rr, cc = idx // cols + 1, idx % cols + 1
        g = iv_panel[iv_panel["expiry_dte"] == d].sort_values("log_moneyness")
        s = surface[d]
        fig.add_trace(go.Scatter(x=g["log_moneyness"], y=g["iv"] * 100, mode="markers",
                                 marker=dict(color=ACCENT, size=6), name="Market",
                                 showlegend=(idx == 0)), row=rr, col=cc)
        kk = np.linspace(g["log_moneyness"].min(), g["log_moneyness"].max(), 200)
        fig.add_trace(go.Scatter(x=kk, y=svi_implied_vol(kk, s["T"], s["params"]) * 100,
                                 mode="lines", line=dict(color=SELL, width=2),
                                 name="SVI fit", showlegend=(idx == 0)), row=rr, col=cc)
    return _dark(fig, "Volatility smile / skew by expiry — market vs SVI",
                 max(320, 260 * rows))


def term_structure(surface):
    dtes = sorted(surface.keys())
    atm = [float(svi_implied_vol(np.array([0.0]), surface[d]["T"],
                                 surface[d]["params"])[0]) * 100 for d in dtes]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dtes, y=atm, mode="lines+markers+text",
                             text=[f"{v:.1f}%" for v in atm], textposition="top center",
                             line=dict(color=ACCENT, width=2.5),
                             marker=dict(size=9), name="ATM IV"))
    fig.update_xaxes(title="Days to expiry"); fig.update_yaxes(title="ATM IV (%)")
    return _dark(fig, "ATM volatility term structure", 360)


# ======================================================================
# Page 5 — No-arbitrage & risk-neutral density
# ======================================================================
def risk_neutral_density(surface, meta, dtes):
    dtes = [d for d in sorted(dtes) if d in surface]
    fig = go.Figure()
    for d in dtes:
        s = surface[d]
        strikes, dens = butterfly_density(s["params"], s["T"], s["forward"], meta["r"])
        dens = np.clip(dens, 0, None)
        fig.add_trace(go.Scatter(x=strikes, y=dens, mode="lines", name=f"{d}d",
                                 line=dict(width=1.8)))
    fig.add_vline(x=meta["spot"], line_dash="dash", line_color=MUTE,
                  annotation_text="Spot")
    fig.update_xaxes(title="Strike"); fig.update_yaxes(title="Risk-neutral density")
    return _dark(fig, "Risk-neutral density (Breeden–Litzenberger)", 400)


# ======================================================================
# Page 6 — Relative value
# ======================================================================
def rv_scatter(rv):
    fig = go.Figure()
    for sig, grp in rv.groupby("signal"):
        fig.add_trace(go.Scatter(
            x=grp["log_moneyness"], y=grp["iv_resid"] * 100, mode="markers",
            name=sig, marker=dict(color=SIGNAL_COLORS.get(sig, MUTE),
                                  size=np.clip(grp["volume"] / 25, 6, 26),
                                  line=dict(width=0)),
            text=grp["strike"], hovertemplate="K=%{text}<br>resid=%{y:.2f} vp"))
    fig.add_hline(y=0, line_color=FG, opacity=0.5)
    fig.update_xaxes(title="log-moneyness  ln(K/F)")
    fig.update_yaxes(title="IV residual (vol-pts)")
    return _dark(fig, "Relative value · market IV − arbitrage-free fair IV", 440)


# ======================================================================
# Page 7 — Delta-hedged P&L
# ======================================================================
def pnl_waterfall(attr):
    labels = ["Theta", "Gamma", "Vega", "Hedge error", "TOTAL"]
    vals = [attr["theta_pnl"], attr["gamma_pnl"], attr["vega_pnl"],
            attr["hedge_error"], attr["total_pnl"]]
    fig = go.Figure(go.Waterfall(
        orientation="v", measure=["relative", "relative", "relative", "relative", "total"],
        x=labels, y=vals, text=[f"{v:+.2f}" for v in vals], textposition="outside",
        connector=dict(line=dict(color=MUTE)),
        increasing=dict(marker=dict(color=BUY)),
        decreasing=dict(marker=dict(color=SELL)),
        totals=dict(marker=dict(color=ACCENT))))
    fig.add_hline(y=0, line_color=FG, opacity=0.4)
    fig.update_yaxes(title="P&L ($ / contract)")
    return _dark(fig, "Delta-hedged short-vol P&L attribution", 400, legend=False)


def hedge_path(path):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=path["t"], y=path["S"], mode="lines", name="Spot",
                             line=dict(color=FG, width=1.6)), secondary_y=False)
    fig.add_trace(go.Scatter(x=path["t"], y=path["opt_val"], mode="lines",
                             name="Option value", line=dict(color=ACCENT, width=1.6)),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=path["t"], y=path["delta"], mode="lines",
                             name="Delta", line=dict(color=SELL, width=1.2, dash="dot")),
                  secondary_y=True)
    fig.update_xaxes(title="Time (yrs)")
    fig.update_yaxes(title="Spot / option value", secondary_y=False)
    fig.update_yaxes(title="Delta", secondary_y=True)
    return _dark(fig, "Hedged path · spot, option value & running delta", 380)


# ======================================================================
# Page 8 — Variance risk premium
# ======================================================================
def vrp_histogram(pnl):
    mean, p5, p1 = float(np.mean(pnl)), float(np.percentile(pnl, 5)), float(np.percentile(pnl, 1))
    fig = go.Figure(go.Histogram(x=pnl, nbinsx=60, marker_color=ACCENT, opacity=0.8))
    fig.add_vline(x=mean, line_color=BUY, line_width=2,
                  annotation_text=f"mean {mean:+.2f}")
    fig.add_vline(x=p5, line_color=SELL, line_dash="dash", line_width=2,
                  annotation_text=f"5% tail {p5:+.2f}")
    fig.add_vline(x=0, line_color=MUTE)
    fig.update_xaxes(title="P&L ($ / contract)"); fig.update_yaxes(title="Frequency")
    return _dark(fig, "Variance-risk-premium capture · delta-hedged short vol", 400)


def realized_vol_histogram(rv):
    fig = go.Figure(go.Histogram(x=rv * 100, nbinsx=50, marker_color="#d29922", opacity=0.8))
    fig.update_xaxes(title="Realized vol (%)"); fig.update_yaxes(title="Frequency")
    return _dark(fig, "Simulated realized-vol distribution", 320)


# ======================================================================
# Page 9 — Market making (Avellaneda–Stoikov)
# ======================================================================
def market_making(mm):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        row_heights=[0.6, 0.4],
                        specs=[[{}], [{"secondary_y": True}]],
                        subplot_titles=("Mid, reservation & quoted band", "Inventory & quote skew"))
    fig.add_trace(go.Scatter(x=mm["t"], y=mm["ask"], mode="lines",
                             line=dict(width=0), showlegend=False, hoverinfo="skip"),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=mm["t"], y=mm["bid"], mode="lines", fill="tonexty",
                             fillcolor="rgba(88,166,255,0.15)", line=dict(width=0),
                             name="Quoted spread"), row=1, col=1)
    fig.add_trace(go.Scatter(x=mm["t"], y=mm["price"], mode="lines", name="Mid",
                             line=dict(color=FG, width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=mm["t"], y=mm["reservation"], mode="lines",
                             name="Reservation", line=dict(color=ACCENT, width=1, dash="dash")),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=mm["t"], y=mm["inventory"], mode="lines", name="Inventory",
                             line=dict(color=BUY, width=1.6)), row=2, col=1, secondary_y=False)
    fig.add_trace(go.Scatter(x=mm["t"], y=mm["skew"], mode="lines", name="Quote skew",
                             line=dict(color=SELL, width=1, dash="dot")),
                  row=2, col=1, secondary_y=True)
    fig.update_yaxes(title="Price", row=1, col=1)
    fig.update_yaxes(title="Inventory", row=2, col=1, secondary_y=False)
    fig.update_yaxes(title="Skew", row=2, col=1, secondary_y=True)
    fig.update_xaxes(title="Time (yrs)", row=2, col=1)
    return _dark(fig, "Avellaneda–Stoikov inventory-aware market making", 560)
