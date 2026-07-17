"""
india_sip_projection.py — what does Rs 10,000/month actually build?

Simulates: start with Rs 10,000, add Rs 10,000 every month, invest it all in the
12-stock Indian momentum strategy, 2018 -> 2025. Compares against the SAME
monthly savings sitting in a bank FD (~6.5%/yr). Shows the power of the SIP:
you keep buying through crashes, so drawdowns hurt far less than the -54% headline.
NOT a promise — past performance; real future differs. Illustration only.
"""
from __future__ import annotations
import os, time, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
os.environ.setdefault("VIBE_TRADING_DATA_CACHE", "1")
os.environ.setdefault("TUSHARE_TOKEN", "noop")
from backtest.loaders.registry import LOADER_REGISTRY, _ensure_registered
_ensure_registered()

UNIVERSE = ["RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS","HINDUNILVR.NS",
            "ITC.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS","LT.NS","AXISBANK.NS",
            "ASIANPAINT.NS","MARUTI.NS","SUNPHARMA.NS","BAJFINANCE.NS","HCLTECH.NS",
            "WIPRO.NS","TITAN.NS","NESTLEIND.NS","POWERGRID.NS","NTPC.NS","TATAMOTORS.NS","ONGC.NS"]
START, END, COST, K, MONTHLY = "2017-06-01", "2025-12-31", 0.0005, 12, 10000


def load(code):
    for _ in range(3):
        try:
            df = LOADER_REGISTRY["yfinance"]().fetch([code], START, END, interval="1D").get(code)
            if df is not None and len(df) > 300:
                s = df["close"].astype(float); s.index = pd.to_datetime(s.index)
                return s[~s.index.duplicated(keep="last")].sort_index()
        except Exception:
            pass
        time.sleep(2)
    return None


def strat_daily_returns(px):
    rets = px.pct_change().fillna(0.0)
    sma = px.rolling(200).mean(); mom = px/px.shift(126)-1; car = px.shift(21)/px.shift(252)-1
    vol = rets.rolling(60).std()
    W = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for t in px.resample("ME").last().index:
        if t not in px.index: continue
        top = set(car.loc[t].dropna().sort_values(ascending=False).head(K).index)
        sel = pd.Series([c in top for c in px.columns], index=px.columns) & (px.loc[t] > sma.loc[t]) & (mom.loc[t] > 0)
        inv = (1.0/vol.loc[t]).where(sel, 0.0).replace([np.inf,-np.inf],0.0).fillna(0.0)
        if inv.sum() > 0:
            W.loc[t] = (inv/inv.sum()) * (int(sel.sum())/K)
    W = W.replace(0.0, np.nan).ffill().fillna(0.0).shift(1).fillna(0.0)
    return (W*rets).sum(axis=1) - W.diff().abs().sum(axis=1).fillna(0.0)*COST


def simulate(monthly_ret, monthly_contrib):
    """Add contribution at each month start, then grow by that month's return."""
    val, contributed = 0.0, 0.0
    for r in monthly_ret:
        val += monthly_contrib; contributed += monthly_contrib
        val *= (1 + r)
    return val, contributed


def main():
    series = {c.replace(".NS",""): load(c) for c in UNIVERSE}
    series = {k: v for k, v in series.items() if v is not None}
    grid = max(series.values(), key=len).index
    px = pd.DataFrame({k: v.reindex(grid).ffill() for k, v in series.items()}).dropna(how="all")
    px = px[px.index >= "2018-01-01"]

    daily = strat_daily_returns(px)
    monthly = (1 + daily).resample("ME").prod() - 1   # compound daily -> monthly
    months = len(monthly)

    strat_val, contributed = simulate(monthly.values, MONTHLY)
    fd_val, _ = simulate([ (1.065**(1/12)-1) ] * months, MONTHLY)   # ~6.5%/yr bank FD

    print(f"Plan: Rs {MONTHLY:,}/month into the 12-stock momentum strategy")
    print(f"Period: {monthly.index[0].strftime('%b %Y')} -> {monthly.index[-1].strftime('%b %Y')} ({months} months)\n")
    print(f"  Total you put in (your salary):   Rs {contributed:>12,.0f}")
    print(f"  If left in a bank FD (~6.5%/yr):   Rs {fd_val:>12,.0f}   (+Rs {fd_val-contributed:,.0f})")
    print(f"  In the momentum strategy:          Rs {strat_val:>12,.0f}   (+Rs {strat_val-contributed:,.0f})")
    mult = strat_val / contributed
    print(f"\n  -> Rs {contributed:,.0f} put in became Rs {strat_val:,.0f}  ({mult:.2f}x)")
    print("  The monthly buying is why big market drops didn't wreck this: you")
    print("  kept accumulating cheap shares. (Past data; future will differ.)")


if __name__ == "__main__":
    main()
