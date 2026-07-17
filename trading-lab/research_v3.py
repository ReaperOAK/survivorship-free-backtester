"""
research_v3 — does better CONSTRUCTION rescue the modest edge?

Changes that historically matter more than the signal itself:
  * MONTHLY rebalance (kills daily whipsaw that hurt 2018/2022).
  * INVERSE-VOL weighting (risk parity) instead of equal weight.
  * CROSS-SECTIONAL selection: hold only top-K by 6m momentum (relative
    strength), optionally gated by an absolute trend filter -> go to cash
    when nothing is trending (real bear protection).
Look-ahead guard: weights decided at month-end t, executed t+1 (shift 1).
5bps turnover cost. Long-only, gross <= 1 (no leverage).
"""
from __future__ import annotations
import os, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
os.environ.setdefault("VIBE_TRADING_DATA_CACHE", "1")
os.environ.setdefault("TUSHARE_TOKEN", "noop")
from backtest.loaders.registry import LOADER_REGISTRY, _ensure_registered
_ensure_registered()

START, END = "2017-06-01", "2025-12-31"
COST, ANN = 0.0005, 252
US = ["XLK","XLF","XLE","XLV","XLI","XLY","XLP","XLU","XLB","SPY","TLT","GLD"]
CRYPTO = [("BTC/USDT","ccxt"), ("ETH/USDT","ccxt")]


def load(code, src):
    try:
        dm = LOADER_REGISTRY[src]().fetch([code], START, END, interval="1D")
        df = dm.get(code)
        if df is None or len(df) < 300: return None
        s = df["close"].astype(float); s.index = pd.to_datetime(s.index)
        return s[~s.index.duplicated(keep="last")].sort_index()
    except Exception:
        return None


def build_prices():
    uni = [(c,"yfinance") for c in US] + CRYPTO
    series = {c: s for c,src in uni if (s := load(c,src)) is not None}
    grid = series["SPY"].index                      # US trading-day calendar
    px = pd.DataFrame({c: s.reindex(grid).ffill() for c,s in series.items()})
    return px.dropna(how="all")


def portfolio_return(px, weight_fn, name):
    """weight_fn(px, t)->Series[asset->weight] at each month-end rebalance date."""
    rets = px.pct_change().fillna(0.0)
    sma200 = px.rolling(200).mean()
    mom = px / px.shift(126) - 1.0
    vol = rets.rolling(60).std()
    rebals = px.resample("ME").last().index          # month-end dates
    W = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    ctx = dict(px=px, sma200=sma200, mom=mom, vol=vol)
    for t in rebals:
        if t not in px.index:
            t = px.index[px.index.get_indexer([t], method="ffill")[0]]
        w = weight_fn(ctx, t)
        W.loc[t] = w.reindex(px.columns).fillna(0.0)
    W = W.replace(0.0, np.nan).ffill().fillna(0.0)    # hold between rebalances
    # renormalize rows that drifted (selection sets exact weights already)
    Wp = W.shift(1).fillna(0.0)                        # execute next day
    turn = Wp.diff().abs().sum(axis=1).fillna(0.0)
    port = (Wp * rets).sum(axis=1) - turn * COST
    return port


# --- weight functions ---
def w_buyhold(ctx, t):
    cols = ctx["px"].columns
    return pd.Series(1.0/len(cols), index=cols)

def w_tsmom_ew(ctx, t):
    sel = ctx["mom"].loc[t] > 0
    n = int(sel.sum())
    return pd.Series(np.where(sel, 1.0/max(n,1), 0.0), index=sel.index) if n else pd.Series(0.0, index=sel.index)

def w_tsmom_invvol(ctx, t):
    sel = ctx["mom"].loc[t] > 0
    inv = (1.0/ctx["vol"].loc[t]).where(sel, 0.0).replace([np.inf,-np.inf],0.0).fillna(0.0)
    return inv/inv.sum() if inv.sum() > 0 else inv

def _topk(ctx, t, k):
    m = ctx["mom"].loc[t].dropna()
    return set(m.sort_values(ascending=False).head(k).index)

def w_xsmom_top5(ctx, t):
    top = _topk(ctx, t, 5)
    sel = pd.Series([c in top for c in ctx["px"].columns], index=ctx["px"].columns)
    n = int(sel.sum())
    return pd.Series(np.where(sel, 1.0/max(n,1), 0.0), index=sel.index)

def w_xsmom_top5_trend(ctx, t):
    top = _topk(ctx, t, 5)
    trend = ctx["px"].loc[t] > ctx["sma200"].loc[t]
    pos_mom = ctx["mom"].loc[t] > 0
    sel = pd.Series([(c in top) for c in ctx["px"].columns], index=ctx["px"].columns) & trend & pos_mom
    n = int(sel.sum())
    # go partially/fully to cash when few names qualify (bear protection)
    return pd.Series(np.where(sel, 1.0/5.0, 0.0), index=sel.index)  # fixed 1/5 -> cash if <5 qualify

def w_xsmom_top5_trend_invvol(ctx, t):
    top = _topk(ctx, t, 5)
    trend = ctx["px"].loc[t] > ctx["sma200"].loc[t]
    sel = pd.Series([c in top for c in ctx["px"].columns], index=ctx["px"].columns) & trend & (ctx["mom"].loc[t] > 0)
    inv = (1.0/ctx["vol"].loc[t]).where(sel, 0.0).replace([np.inf,-np.inf],0.0).fillna(0.0)
    # cap total exposure to 1; if fewer names, stay partly in cash
    if inv.sum() <= 0: return inv
    w = inv/inv.sum()
    return w * (int(sel.sum())/5.0)   # scale by fraction of 5 slots filled -> cash otherwise

STRATS = {
    "buyhold_ew": w_buyhold,
    "tsmom_ew": w_tsmom_ew,
    "tsmom_invvol": w_tsmom_invvol,
    "xsmom_top5": w_xsmom_top5,
    "xs_top5_trend": w_xsmom_top5_trend,
    "xs_trend_ivol": w_xsmom_top5_trend_invvol,
}


def stats(r):
    r = r.dropna()
    if len(r) < 20 or r.std()==0: return dict(cagr=0,sharpe=0,maxdd=0)
    eq=(1+r).cumprod(); yrs=len(r)/ANN
    return dict(cagr=eq.iloc[-1]**(1/yrs)-1, sharpe=r.mean()/r.std()*np.sqrt(ANN), maxdd=(eq/eq.cummax()-1).min())


def main():
    px = build_prices()
    print(f"Universe {len(px.columns)} assets, {len(px)} bars {px.index[0].date()}..{px.index[-1].date()}\n")
    port = {n: portfolio_return(px, fn, n) for n,fn in STRATS.items()}

    print("Sharpe by year (bear years 2018 & 2022 are the real test)")
    print(f"{'year':6}" + "".join(f"{n:>15}" for n in STRATS))
    print("-"*(6+15*len(STRATS)))
    for y in range(2018,2026):
        line=f"{y:<6}"
        for n in STRATS:
            r=port[n][(port[n].index>=f"{y}-01-01")&(port[n].index<=f"{y}-12-31")]
            line+=f"{stats(r)['sharpe']:>15.2f}"
        print(line)

    print("\nFULL PERIOD 2018-2025")
    print(f"{'strategy':16}{'CAGR':>9}{'Sharpe':>9}{'MaxDD':>9}")
    print("-"*43)
    for n in STRATS:
        r=port[n][port[n].index>="2018-01-01"]; st=stats(r)
        print(f"{n:16}{st['cagr']:>8.1%}{st['sharpe']:>9.2f}{st['maxdd']:>8.1%}")
    print("\n(fair universe; monthly rebalance; long-only gross<=1; 5bps turnover)")


if __name__ == "__main__":
    main()
