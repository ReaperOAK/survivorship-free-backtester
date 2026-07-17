"""
allweather_test.py — does the 5-asset-class trend strategy make us SAFER?

Strategy (from awesome-systematic-trading / Quantpedia 'asset-class-trend-following'):
  5 ETFs across DIFFERENT asset classes: SPY (US stocks), EFA (foreign stocks),
  IEF (bonds), VNQ (real estate), GSG (commodities). Monthly: hold each 1/5 slice
  only while it's above its 10-month (210d) average; otherwise that slice = cash.

We compare it against just buying the stock market (SPY) and against naively
holding all 5. The point: does trend + cross-asset diversification cut the
gut-wrenching drawdowns while keeping decent return? Look-ahead safe, costs incl.
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

ETFS = ["SPY", "EFA", "IEF", "VNQ", "GSG"]
START, END = "2017-06-01", "2025-12-31"
COST, ANN = 0.0005, 252


def load(code):
    for _ in range(3):
        try:
            df = LOADER_REGISTRY["yfinance"]().fetch([code], START, END, interval="1D").get(code)
            if df is not None and len(df) > 300:
                s = df["close"].astype(float); s.index = pd.to_datetime(s.index)
                return s[~s.index.duplicated(keep="last")].sort_index()
        except Exception:
            pass
        time.sleep(3)
    return None


def monthly_trend_weights(px):
    """Each ETF: 1/N when above 210d SMA at last month-end, else cash. Held monthly."""
    sma = px.rolling(210).mean()
    hold = (px > sma).astype(float) / len(px.columns)
    me = px.resample("ME").last().index
    W = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for t in me:
        if t in hold.index:
            W.loc[t] = hold.loc[t]
    return W.replace(0.0, np.nan).ffill().fillna(0.0)


def perf(px, W):
    rets = px.pct_change().fillna(0.0)
    Wp = W.shift(1).fillna(0.0)
    turn = Wp.diff().abs().sum(axis=1).fillna(0.0)
    return (Wp * rets).sum(axis=1) - turn * COST


def stats(r):
    r = r.dropna()
    eq = (1 + r).cumprod(); yrs = len(r) / ANN
    return dict(cagr=eq.iloc[-1] ** (1 / yrs) - 1,
                sharpe=r.mean() / r.std() * np.sqrt(ANN),
                maxdd=(eq / eq.cummax() - 1).min())


def main():
    px = pd.DataFrame({c: load(c) for c in ETFS}).dropna()
    px = px[px.index >= "2018-01-01"]
    print(f"Data: {list(px.columns)}  {px.index[0].date()}..{px.index[-1].date()}\n")

    # A) just buy the US stock market
    spy = perf(px[["SPY"]], pd.DataFrame(1.0, index=px.index, columns=["SPY"]))
    # B) naively hold all 5 equal weight (diversified, but no trend protection)
    ewW = pd.DataFrame(1.0 / len(ETFS), index=px.index, columns=ETFS)
    ew = perf(px, ewW)
    # C) the strategy: 5-asset TREND-following
    tf = perf(px, monthly_trend_weights(px))

    print(f"{'approach':32}{'CAGR':>8}{'Sharpe':>9}{'WorstDrop':>11}")
    print("-" * 60)
    for name, r in [("Just buy stocks (SPY)", spy),
                    ("Hold all 5 (no trend)", ew),
                    ("5-asset TREND (the strategy)", tf)]:
        s = stats(r)
        print(f"{name:32}{s['cagr']:>7.1%}{s['sharpe']:>9.2f}{s['maxdd']:>10.1%}")
    print("\n'WorstDrop' = biggest peak-to-trough fall. Lower = safer / less scary.")
    print("Also worth checking 2022 (stocks fell ~20%):")
    for name, r in [("  SPY", spy), ("  5-asset TREND", tf)]:
        r22 = r[(r.index >= "2022-01-01") & (r.index <= "2022-12-31")]
        eq = (1 + r22).cumprod()
        print(f"{name:20} 2022 return {eq.iloc[-1]-1:+.1%}, worst drop {(eq/eq.cummax()-1).min():.1%}")


if __name__ == "__main__":
    main()
