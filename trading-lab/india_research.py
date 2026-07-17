"""
india_research.py — find the BEST strategy for Indian large-caps (done properly).

Head-to-head, portfolio-level, monthly rebalance, long/flat, 5bps turnover cost,
look-ahead safe (weights decided at month-end, executed next day). Universe =
~24 liquid Nifty large-caps + ^NSEI as the market benchmark. Walk-forward by
year so we see which survives different regimes (incl. the 2018/2020 shocks).
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
START, END = "2017-06-01", "2025-12-31"
COST, ANN, K = 0.0005, 252, 6


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


def build_prices():
    series = {c.replace(".NS", ""): load(c) for c in UNIVERSE}
    series = {k: v for k, v in series.items() if v is not None}
    grid = max(series.values(), key=len).index
    return pd.DataFrame({k: v.reindex(grid).ffill() for k, v in series.items()}).dropna(how="all")


def port_return(px, weight_fn):
    rets = px.pct_change().fillna(0.0)
    sma200 = px.rolling(200).mean()
    mom = px / px.shift(126) - 1.0
    car = px.shift(21) / px.shift(252) - 1.0
    vol = rets.rolling(60).std()
    ctx = dict(px=px, sma=sma200, mom=mom, car=car, vol=vol)
    W = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for t in px.resample("ME").last().index:
        if t not in px.index:
            idx = px.index.get_indexer([t], method="ffill")[0]
            if idx < 0: continue
            t = px.index[idx]
        W.loc[t] = weight_fn(ctx, t).reindex(px.columns).fillna(0.0)
    W = W.replace(0.0, np.nan).ffill().fillna(0.0)
    Wp = W.shift(1).fillna(0.0)
    turn = Wp.diff().abs().sum(axis=1).fillna(0.0)
    return (Wp * rets).sum(axis=1) - turn * COST


def ew(ctx, t):
    c = ctx["px"].columns; return pd.Series(1.0/len(c), index=c)

def trend_ew(ctx, t):
    sel = ctx["px"].loc[t] > ctx["sma"].loc[t]; n = int(sel.sum())
    return pd.Series(np.where(sel, 1.0/max(n,1), 0.0), index=sel.index) if n else pd.Series(0.0, index=sel.index)

def tsmom_ew(ctx, t):
    sel = ctx["mom"].loc[t] > 0; n = int(sel.sum())
    return pd.Series(np.where(sel, 1.0/max(n,1), 0.0), index=sel.index) if n else pd.Series(0.0, index=sel.index)

def tsmom_invvol(ctx, t):
    sel = ctx["mom"].loc[t] > 0
    inv = (1.0/ctx["vol"].loc[t]).where(sel, 0.0).replace([np.inf,-np.inf],0.0).fillna(0.0)
    return inv/inv.sum() if inv.sum() > 0 else inv

def _topk(ctx, t):
    return set(ctx["car"].loc[t].dropna().sort_values(ascending=False).head(K).index)

def xsmom_top(ctx, t):
    top = _topk(ctx, t)
    sel = pd.Series([c in top for c in ctx["px"].columns], index=ctx["px"].columns)
    n = int(sel.sum()); return pd.Series(np.where(sel, 1.0/max(n,1), 0.0), index=sel.index)

def xs_trend(ctx, t):  # our currently-deployed one
    top = _topk(ctx, t)
    sel = pd.Series([c in top for c in ctx["px"].columns], index=ctx["px"].columns) \
          & (ctx["px"].loc[t] > ctx["sma"].loc[t]) & (ctx["mom"].loc[t] > 0)
    return pd.Series(np.where(sel, 1.0/K, 0.0), index=sel.index)

def xs_trend_invvol(ctx, t):
    top = _topk(ctx, t)
    sel = pd.Series([c in top for c in ctx["px"].columns], index=ctx["px"].columns) \
          & (ctx["px"].loc[t] > ctx["sma"].loc[t]) & (ctx["mom"].loc[t] > 0)
    inv = (1.0/ctx["vol"].loc[t]).where(sel, 0.0).replace([np.inf,-np.inf],0.0).fillna(0.0)
    if inv.sum() <= 0: return inv
    return inv/inv.sum() * (int(sel.sum())/K)

STRATS = {"buyhold_ew": ew, "trend_ew": trend_ew, "tsmom_ew": tsmom_ew,
          "tsmom_invvol": tsmom_invvol, "xsmom_top6": xsmom_top,
          "xs_trend (LIVE)": xs_trend, "xs_trend_invvol": xs_trend_invvol}


def stats(r):
    r = r.dropna()
    if len(r) < 20 or r.std() == 0: return dict(cagr=0, sharpe=0, maxdd=0)
    eq = (1+r).cumprod(); yrs = len(r)/ANN
    return dict(cagr=eq.iloc[-1]**(1/yrs)-1, sharpe=r.mean()/r.std()*np.sqrt(ANN), maxdd=(eq/eq.cummax()-1).min())


def main():
    px = build_prices()
    px = px[px.index >= "2018-01-01"]
    print(f"Universe {px.shape[1]} stocks, {len(px)} days {px.index[0].date()}..{px.index[-1].date()}\n")
    bench = load("^NSEI")
    port = {n: port_return(px, fn) for n, fn in STRATS.items()}
    if bench is not None:
        b = bench.reindex(px.index).ffill().pct_change().fillna(0.0)
        port["Nifty index"] = b

    print("Sharpe by year")
    names = list(port)
    print(f"{'year':6}" + "".join(f"{n[:13]:>15}" for n in names))
    print("-"*(6+15*len(names)))
    for y in range(2018, 2026):
        line = f"{y:<6}"
        for n in names:
            r = port[n][(port[n].index >= f"{y}-01-01") & (port[n].index <= f"{y}-12-31")]
            line += f"{stats(r)['sharpe']:>15.2f}"
        print(line)

    print("\nFULL PERIOD 2018-2025")
    print(f"{'strategy':18}{'CAGR':>9}{'Sharpe':>9}{'MaxDD':>9}")
    print("-"*45)
    ranked = sorted(names, key=lambda n: stats(port[n][port[n].index>='2018-01-01'])['sharpe'], reverse=True)
    for n in ranked:
        s = stats(port[n][port[n].index >= "2018-01-01"])
        star = "  <-- best" if n == ranked[0] else ("   (live)" if "LIVE" in n else "")
        print(f"{n:18}{s['cagr']:>8.1%}{s['sharpe']:>9.2f}{s['maxdd']:>8.1%}{star}")


if __name__ == "__main__":
    main()
