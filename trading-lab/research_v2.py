"""
research_v2 — de-biased validation of the trend edge.

Fixes vs v1:
  * FAIR universe chosen a priori (sector ETFs + macro + crypto majors),
    NOT hand-picked megacap winners -> removes selection bias.
  * WALK-FORWARD by calendar year -> see if the edge survives each regime,
    including the 2018 Q4 selloff and the 2022 bear.
  * Focus strategies: buyhold, trend(SMA200), tsmom(6m), trend+mom combo.
Same look-ahead guard (signal shifted 1 bar) and 5bps turnover cost.
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

START, END = "2017-06-01", "2025-12-31"   # earlier start so SMA200 is warm by 2018
COST, ANN = 0.0005, 252

# a-priori diversified universe: 9 SPDR sectors + broad + bonds + gold + 2 crypto
US = ["XLK","XLF","XLE","XLV","XLI","XLY","XLP","XLU","XLB","SPY","TLT","GLD"]
CRYPTO = [("BTC/USDT","ccxt"), ("ETH/USDT","ccxt")]


def load(code, src):
    try:
        dm = LOADER_REGISTRY[src]().fetch([code], START, END, interval="1D")
        df = dm.get(code)
        if df is None or len(df) < 300:
            return None
        s = df["close"].astype(float); s.index = pd.to_datetime(s.index)
        return s[~s.index.duplicated(keep="last")].sort_index()
    except Exception as e:
        print(f"  ! {code}/{src}: {str(e)[:60]}"); return None


def sig_trend(c):   return (c > c.rolling(200).mean()).astype(float)
def sig_mom(c):     return (c.pct_change(126) > 0).astype(float)
def sig_combo(c):   return ((c > c.rolling(200).mean()) & (c.pct_change(126) > 0)).astype(float)
def sig_bh(c):      return pd.Series(1.0, index=c.index)

STRATS = {"buyhold": sig_bh, "trend200": sig_trend, "tsmom126": sig_mom, "trend+mom": sig_combo}


def strat_ret(c, pos):
    ret = c.pct_change().fillna(0.0)
    p = pos.shift(1).fillna(0.0)
    return p * ret - p.diff().abs().fillna(0.0) * COST


def stats(r):
    r = r.dropna()
    if len(r) < 20 or r.std() == 0:
        return dict(cagr=0, sharpe=0, maxdd=0)
    eq = (1 + r).cumprod(); yrs = len(r) / ANN
    return dict(cagr=eq.iloc[-1] ** (1/yrs) - 1,
                sharpe=r.mean()/r.std()*np.sqrt(ANN),
                maxdd=(eq/eq.cummax()-1).min())


def main():
    uni = [(c, "yfinance") for c in US] + CRYPTO
    prices = {c: s for c, src in uni if (s := load(c, src)) is not None}
    print(f"Loaded {len(prices)}/{len(uni)} symbols  ({', '.join(prices)})\n")

    # portfolio strat returns (equal weight across assets)
    port = {}
    for name, fn in STRATS.items():
        cols = [strat_ret(s, fn(s)) for s in prices.values()]
        port[name] = pd.concat(cols, axis=1).mean(axis=1)

    years = list(range(2018, 2026))
    print("WALK-FORWARD  — Sharpe by calendar year (edge must survive each regime)")
    print(f"{'year':6}" + "".join(f"{n:>11}" for n in STRATS))
    print("-" * (6 + 11*len(STRATS)))
    regime = {2018:"chop/Q4crash",2019:"bull",2020:"covid",2021:"bull",
              2022:"BEAR",2023:"recovery",2024:"bull",2025:"bull"}
    for y in years:
        line = f"{y:<6}"
        for n in STRATS:
            r = port[n][(port[n].index >= f"{y}-01-01") & (port[n].index <= f"{y}-12-31")]
            line += f"{stats(r)['sharpe']:>11.2f}"
        print(line + f"   {regime.get(y,'')}")

    print("\nFULL PERIOD (2018-2025)")
    print(f"{'strategy':12}{'CAGR':>9}{'Sharpe':>9}{'MaxDD':>9}")
    print("-" * 39)
    for n in STRATS:
        r = port[n][port[n].index >= "2018-01-01"]
        st = stats(r)
        print(f"{n:12}{st['cagr']:>8.1%}{st['sharpe']:>9.2f}{st['maxdd']:>8.1%}")
    print("\n(fair a-priori universe; equal-weight; long/flat; 5bps turnover)")


if __name__ == "__main__":
    main()
