"""
nifty_lowvol_test.py — the low-volatility idea, tested on INDIAN stocks.

The 'low-volatility anomaly': the calmest stocks tend to deliver similar (or
better) returns than the jumpy ones, with much less stress. If true, that's a
rare genuine "safer without giving up much" edge.

Test: ~15 liquid Nifty large-caps. Monthly, hold the 6 LOWEST-volatility names
(equal weight). Compare vs the Nifty index, vs holding all 15, and vs the 6
HIGHEST-vol names (to see the anomaly directly). Look-ahead safe, costs incl.
Trades Indian stocks a resident can actually buy (NSE, .NS tickers).
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

STOCKS = ["RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
          "HINDUNILVR.NS","ITC.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
          "LT.NS","AXISBANK.NS","ASIANPAINT.NS","MARUTI.NS","SUNPHARMA.NS"]
BENCH = "^NSEI"
START, END = "2017-06-01", "2025-12-31"
COST, ANN, HOLD = 0.0005, 252, 6


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


def weights(px, pick="low"):
    vol = px.pct_change().rolling(90).std()
    me = px.resample("ME").last().index
    W = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for t in me:
        if t not in vol.index:
            continue
        v = vol.loc[t].dropna()
        if len(v) < HOLD:
            continue
        chosen = (v.nsmallest(HOLD) if pick == "low" else v.nlargest(HOLD)).index
        W.loc[t, chosen] = 1.0 / HOLD
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
    print("Fetching Indian stocks (gently)...")
    px = pd.DataFrame({c: load(c) for c in STOCKS}).dropna(how="all")
    bench = load(BENCH)
    px = px[px.index >= "2018-01-01"].dropna(axis=1, how="any")
    print(f"Loaded {px.shape[1]}/{len(STOCKS)} stocks  {px.index[0].date()}..{px.index[-1].date()}\n")

    nifty = perf(bench.to_frame("i")[bench.index >= "2018-01-01"],
                 pd.DataFrame(1.0, index=bench[bench.index >= "2018-01-01"].index, columns=["i"])) if bench is not None else None
    ew = perf(px, pd.DataFrame(1.0 / px.shape[1], index=px.index, columns=px.columns))
    lowv = perf(px, weights(px, "low"))
    highv = perf(px, weights(px, "high"))

    print(f"{'approach':30}{'CAGR':>8}{'Sharpe':>9}{'WorstDrop':>11}")
    print("-" * 58)
    rows = [("Nifty 50 index", nifty), ("Hold all 15 equally", ew),
            ("LOW-vol 6 (the idea)", lowv), ("HIGH-vol 6 (opposite)", highv)]
    for name, r in rows:
        if r is None:
            continue
        s = stats(r)
        print(f"{name:30}{s['cagr']:>7.1%}{s['sharpe']:>9.2f}{s['maxdd']:>10.1%}")
    print("\nIf LOW-vol beats HIGH-vol on Sharpe AND has a smaller worst drop,")
    print("the 'safer calm stocks' anomaly is real on Indian large-caps.")


if __name__ == "__main__":
    main()
