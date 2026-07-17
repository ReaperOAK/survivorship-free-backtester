"""
signal_engine.py — the app-ready signal backend. Given a universe + strategy,
returns what to hold RIGHT NOW, reading from the local cleaned DuckDB store
(zero API calls). This is the validated engine from the 20-year exploration.

Best HONEST (survivorship-corrected, free Wayback point-in-time — see
survivorship_pit.py): 'momentum_trend' on **Nifty 500**, corrected Sharpe ~1.2
(NOT the raw ~1.5 — that was survivorship fantasy). Wider universe survives the
honesty test best; Nifty 200 corrects to only ~0.87, Nifty 100 to ~0.53.
Every signal now carries its survivorship-corrected stats so the UI never shows
a fantasy number. Also returns the MINIMUM BALANCE to run it (whole-share NSE).

  from signal_engine import current_signal
  sig = current_signal("nifty500", "momentum_trend", topk=20)
"""
from __future__ import annotations
import os, sys
import numpy as np
import pandas as pd
import duckdb

sys.path.insert(0, os.path.dirname(__file__))
import data_store as ds

DB = os.path.expanduser("~/.vibe-trading/market.duckdb")

# Survivorship-CORRECTED backtest stats (momentum+trend, top-20), from the FREE
# Wayback point-in-time correction (trading-lab/survivorship_pit.py). These are the
# HONEST numbers to show users — never the survivorship-biased raw ones.
#   raw = what a naive backtest on today's index list shows (inflated by hindsight)
#   corrected = point-in-time membership, the honest edge
CORRECTED_STATS = {
    # universe:  dict(raw_sharpe, sharpe, cagr, maxdd, window, note)
    "nifty500": dict(raw_sharpe=1.49, sharpe=1.04, cagr=0.245, maxdd=-0.38,
                     window="2017-2026", note="honest best universe — breadth survives correction; incl. recovered delisted losers"),
    "nifty200": dict(raw_sharpe=1.74, sharpe=0.86, cagr=0.178, maxdd=-0.41,
                     window="2017-2023", note="raw 1.48-1.74 was survivorship fantasy"),
    "nifty100": dict(raw_sharpe=1.31, sharpe=0.53, cagr=0.087, maxdd=-0.40,
                     window="2017-2023", note="too narrow — momentum needs breadth"),
    "nifty50":  dict(raw_sharpe=1.29, sharpe=0.76, cagr=0.13, maxdd=-0.42,
                     window="2008-2025", note="point-in-time from Kaggle weights (top-10)"),
    "full":     dict(raw_sharpe=None, sharpe=None, cagr=None, maxdd=None,
                     window=None, note="not survivorship-tested; illiquid junk risk — aggressive only"),
}
DEFAULT_UNIVERSE = "nifty500"   # honest best (was nifty200 pre-survivorship-correction)
DEFAULT_STRATEGY = "ensemble_regime"   # tournament + after-tax champion (best risk-adjusted)

# AFTER-TAX net stats (Indian STCG 20% / LTCG 12.5%), nifty500 2017-2026, from aftertax_sim.py.
# These are what actually lands in your pocket — the honest headline per strategy.
NET_STATS = {
    "ensemble_regime": dict(sharpe=1.10, cagr=0.142, maxdd=-0.18,
                            note="best risk-adjusted after-tax; shallow -18% drawdowns (beginner-friendly)"),
    "momentum_trend":  dict(sharpe=0.87, cagr=0.185, maxdd=-0.38,
                            note="highest after-tax CAGR but deep -38% drawdowns"),
    "lowvol":          dict(sharpe=0.84, cagr=0.140, maxdd=-0.32,
                            note="defensive; steadier ride"),
    "buyhold":         dict(sharpe=0.84, cagr=0.141, maxdd=-0.46,
                            note="tax-efficient (low turnover) & laziest; deep drawdowns"),
}


def _market_regime(px):
    """Broad equal-weight trend filter: is the market above its own 200-day average?
    Returns (risk_on: bool). Risk-OFF -> the champion strategy recommends CASH."""
    proxy = (1 + px.pct_change().clip(-0.35, 0.35).mean(axis=1).fillna(0)).cumprod()
    sma = proxy.rolling(200).mean()
    return bool(proxy.iloc[-1] > sma.iloc[-1]) if sma.notna().iloc[-1] else True


def market_state(universe=DEFAULT_UNIVERSE):
    """Live market context for the SIP dip-rule (F3): is the market above its 200-day
    trend (risk_on), and how far below its peak (drawdown)?"""
    px, asof = _load(universe)
    proxy = (1 + px.pct_change().clip(-0.35, 0.35).mean(axis=1).fillna(0)).cumprod()
    sma = proxy.rolling(200).mean()
    risk_on = bool(proxy.iloc[-1] > sma.iloc[-1]) if bool(sma.notna().iloc[-1]) else True
    drawdown = float(proxy.iloc[-1] / proxy.cummax().iloc[-1] - 1)
    return dict(asof=str(asof), risk_on=risk_on, drawdown=drawdown)


def _load(universe):
    con = duckdb.connect(DB, read_only=True)   # one read-only conn for everything
    if universe == "full":
        cut = con.execute("SELECT MAX(date) FROM prices").fetchone()[0] - pd.Timedelta(days=90)
        syms = [r[0] for r in con.execute("""SELECT symbol FROM prices WHERE date>=? GROUP BY symbol
            HAVING AVG(close)>20 AND COUNT(*)>40 ORDER BY AVG(close*volume) DESC LIMIT 400""", [cut]).fetchall()]
    else:
        syms = [r[0] for r in con.execute("SELECT symbol FROM index_members WHERE idx=?", [universe]).fetchall()]
    maxd = con.execute("SELECT MAX(date) FROM prices").fetchone()[0]
    cutoff = (pd.Timestamp(maxd) - pd.Timedelta(days=600)).date()
    ph = ",".join(["?"] * len(syms))
    px = con.execute(f"SELECT date,symbol,close FROM prices WHERE symbol IN ({ph}) AND date>=? "
                     f"ORDER BY date", [*syms, cutoff]).df().pivot(index="date", columns="symbol", values="close")
    con.close()
    px.index = pd.to_datetime(px.index)
    return px.ffill(limit=5), maxd


def current_signal(universe=DEFAULT_UNIVERSE, strategy=DEFAULT_STRATEGY, topk=20):
    px, asof = _load(universe)
    risk_on = _market_regime(px)
    rows = {}
    for s in px.columns:
        c = px[s].dropna()
        if len(c) < 252:
            continue
        rows[s] = dict(price=float(c.iloc[-1]),
                       above_sma200=bool(c.iloc[-1] > c.rolling(200).mean().iloc[-1]),
                       ret6m=float(c.iloc[-1] / c.iloc[-126] - 1),
                       carhart=float(c.iloc[-21] / c.iloc[-252] - 1),
                       vol=float(c.pct_change().iloc[-60:].std() * np.sqrt(252)))
    df = pd.DataFrame(rows).T
    if df.empty:
        return dict(asof=str(asof), picks=df, min_balance=None, risk_on=risk_on)
    for col in ("price", "ret6m", "carhart", "vol"):     # .T yields object dtype -> coerce
        df[col] = pd.to_numeric(df[col])
    df["above_sma200"] = df["above_sma200"].astype(bool)

    eps = 1e-9
    if strategy == "lowvol":
        picks = df.nsmallest(topk, "vol").copy()
        picks["weight"] = 1.0 / len(picks)
    elif strategy == "ensemble_regime":
        # blend 3 signals (momentum+trend, risk-adjusted-momentum, low-vol); go to CASH if risk-off
        gated = df[(df["above_sma200"]) & (df["ret6m"] > 0)]
        mom = gated.sort_values("carhart", ascending=False).head(topk).index
        mv = (gated["carhart"] / (gated["vol"] + eps)).sort_values(ascending=False).head(topk).index
        lv = df.nsmallest(topk, "vol").index
        w = pd.Series(0.0, index=df.index)
        for sleeve in (mom, mv, lv):
            w[sleeve] += (1.0 / topk) / 3.0       # each sleeve = 1/k equal, averaged across 3
        if not risk_on:
            w[:] = 0.0                            # regime stop-rule -> hold cash
        picks = df.loc[w[w > 0].index].copy()
        picks["weight"] = w[w > 0]
    else:  # momentum_trend
        elig = df[(df["above_sma200"]) & (df["ret6m"] > 0)].sort_values("carhart", ascending=False)
        picks = elig.head(topk).copy()
        picks["weight"] = 1.0 / topk        # fixed 1/K -> partial cash if < topk qualify

    # minimum balance to run it with WHOLE shares (biggest position / its weight)
    min_bal = None
    if len(picks):
        need = picks["price"] / picks["weight"]
        min_bal = float(need.max())          # capital so the priciest name = >=1 share at weight
    return dict(asof=str(asof), universe=universe, strategy=strategy,
                picks=picks, cash_frac=float(1 - picks["weight"].sum()) if len(picks) else 1.0,
                min_balance=min_bal, risk_on=risk_on,
                corrected_stats=CORRECTED_STATS.get(universe),   # survivorship-corrected (pre-tax)
                net_stats=NET_STATS.get(strategy))               # after-tax headline


def _fmt(sig):
    p = sig["picks"]
    out = [f"=== {sig['strategy']} on {sig['universe']}  (as of {sig['asof']}) ==="]
    if sig.get("strategy") == "ensemble_regime":
        out.append(f"MARKET REGIME: {'risk-ON — invest' if sig.get('risk_on') else 'risk-OFF — HOLD CASH (market below its 200-day trend)'}")
    ns = sig.get("net_stats")
    if ns:
        out.append(f"AFTER-TAX (Indian STCG/LTCG, Nifty500 2017-26): Sharpe {ns['sharpe']:.2f}, "
                   f"~{ns['cagr']:.0%}/yr net, worst drop {ns['maxdd']:.0%}. {ns['note']}. Past ≠ future.")
    out.append(f"Reads from local store, zero API calls. Min balance to run (whole shares): "
               f"~Rs {sig['min_balance']:,.0f}" if sig.get("min_balance") else "Holding CASH (no picks right now).")
    if len(p):
        out.append(f"\n{'stock':14}{'price':>10}{'6m':>8}{'12-1':>8}{'vol':>7}{'wt':>7}")
        for s, r in p.iterrows():
            out.append(f"{s:14}{r['price']:>10,.0f}{r.get('ret6m',0):>7.0%}"
                       f"{r.get('carhart',0):>8.0%}{r['vol']:>7.0%}{r['weight']:>7.1%}")
        out.append(f"\nHold {len(p)} names, {sig['cash_frac']:.0%} cash.")
    return "\n".join(out)


if __name__ == "__main__":
    uni = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_UNIVERSE
    strat = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_STRATEGY
    print(_fmt(current_signal(uni, strat)))
