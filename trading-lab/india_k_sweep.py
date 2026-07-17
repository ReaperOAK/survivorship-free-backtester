"""
india_k_sweep.py — how many stocks to hold? (fixing the -70% drawdown)

The full test showed concentrated momentum (top 6) has great Sharpe but a
catastrophic ~-70% drawdown, while holding ALL names is much safer (-35%) but
lower return. This finds the sweet spot: momentum+trend, inverse-vol, monthly,
but holding the top-K by momentum for K = 6..all. We want the K that keeps
strong return while cutting the drawdown to something a human can actually hold.
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
START, END, COST, ANN = "2017-06-01", "2025-12-31", 0.0005, 252


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


def run(px, K):
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
            W.loc[t] = (inv/inv.sum()) * (int(sel.sum())/K)   # partial cash if < K qualify
    W = W.replace(0.0, np.nan).ffill().fillna(0.0)
    Wp = W.shift(1).fillna(0.0)
    r = (Wp*rets).sum(axis=1) - Wp.diff().abs().sum(axis=1).fillna(0.0)*COST
    r = r[r.index >= "2018-01-01"]
    eq = (1+r).cumprod(); yrs = len(r)/ANN
    return dict(cagr=eq.iloc[-1]**(1/yrs)-1, sharpe=r.mean()/r.std()*np.sqrt(ANN), maxdd=(eq/eq.cummax()-1).min())


def main():
    series = {c.replace(".NS",""): load(c) for c in UNIVERSE}
    series = {k: v for k, v in series.items() if v is not None}
    grid = max(series.values(), key=len).index
    px = pd.DataFrame({k: v.reindex(grid).ffill() for k, v in series.items()}).dropna(how="all")
    print(f"Universe {px.shape[1]} stocks\n")
    print(f"{'hold top-K':>11}{'CAGR':>9}{'Sharpe':>9}{'MaxDD':>9}")
    print("-"*38)
    for K in [6, 8, 10, 12, 15, 18, px.shape[1]]:
        s = run(px, K)
        tag = "  <- diversified" if K >= 10 else ""
        print(f"{K:>11}{s['cagr']:>8.1%}{s['sharpe']:>9.2f}{s['maxdd']:>8.1%}{tag}")
    print("\nGoal: keep Sharpe high while pulling MaxDD up from -70% to something holdable.")


if __name__ == "__main__":
    main()
