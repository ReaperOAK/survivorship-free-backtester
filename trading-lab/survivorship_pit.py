"""
survivorship_pit.py — generic point-in-time (survivorship-corrected) vs biased
momentum+trend backtest for ANY Nifty index, all with FREE data:
  BIASED    universe = today's actual constituents (index_members) held constant
  CORRECTED universe = point-in-time constituents (nearest-prior Wayback snapshot)
Both run over the window Wayback actually covers, on store prices.

Usage: python survivorship_pit.py [nifty100|nifty200|nifty500] [topk]
Self-contained (own top-K weight fn) so the top-K label is always honest.
"""
from __future__ import annotations
import os, sys, warnings
import numpy as np
import pandas as pd
import duckdb

warnings.filterwarnings("ignore")
DB = os.path.expanduser("~/.vibe-trading/market.duckdb")
COST, ANN = 0.0005, 252


def weights(px, universe_fn, topk):
    sma = px.rolling(200).mean(); mom = px / px.shift(126) - 1; car = px.shift(21) / px.shift(252) - 1
    W = pd.DataFrame(np.nan, index=px.index, columns=px.columns)   # NaN -> set on rebalance -> ffill
    for t in px.resample("ME").last().index:
        if t not in px.index or px.index.get_loc(t) < 252:
            continue
        w = pd.Series(0.0, index=px.columns)                       # COMPLETE vector (0s included)
        uni = [s for s in universe_fn(t) if s in px.columns]
        if uni:
            sub_car = car.loc[t, uni].dropna()
            trend = (px.loc[t, uni] > sma.loc[t, uni]) & (mom.loc[t, uni] > 0)
            elig = sub_car[trend.reindex(sub_car.index).fillna(False)]
            top = elig.sort_values(ascending=False).head(topk).index
            if len(top):
                w[top] = 1.0 / topk
        W.loc[t] = w
    return W.ffill().fillna(0.0)


def perf(px, W):
    rets = px.pct_change().clip(-0.35, 0.35).fillna(0)
    Wp = W.shift(1).fillna(0)
    turn = Wp.diff().abs().sum(axis=1).fillna(0)
    r = (Wp * rets).sum(axis=1) - turn * COST
    return r[Wp.abs().sum(axis=1) > 0]


def stats(r):
    r = r.dropna(); eq = (1 + r).cumprod(); yrs = len(r) / ANN
    return dict(cagr=eq.iloc[-1] ** (1 / yrs) - 1, sharpe=r.mean() / r.std() * np.sqrt(ANN),
                maxdd=(eq / eq.cummax() - 1).min())


def run(idx, topk):
    con = duckdb.connect(DB, read_only=True)
    hist = con.execute("SELECT snap_date, symbol FROM index_members_hist WHERE idx=?", [idx]).df()
    hist["snap_date"] = pd.to_datetime(hist["snap_date"])
    snaps = {d: set(g["symbol"]) for d, g in hist.groupby("snap_date")}
    snap_dates = sorted(snaps)
    today = {x[0] for x in con.execute("SELECT symbol FROM index_members WHERE idx=?", [idx]).fetchall()}
    ever = sorted(set(hist["symbol"]) | today)
    store = {x[0] for x in con.execute("SELECT DISTINCT symbol FROM prices").fetchall()}
    have = [s for s in ever if s in store]
    ph = ",".join(["?"] * len(have))
    start = (snap_dates[0] - pd.Timedelta(days=400)).strftime("%Y-%m-%d")  # 400d warmup before 1st snapshot
    df = con.execute(f"SELECT date,symbol,close FROM prices WHERE symbol IN ({ph}) AND date>=? ORDER BY date",
                     have + [start]).df()
    con.close()
    px = df.pivot(index="date", columns="symbol", values="close").ffill(limit=5)
    px.index = pd.to_datetime(px.index)
    px = px[px.index <= snap_dates[-1] + pd.Timedelta(days=31)]        # PIT valid only through last snapshot

    def pit(t):
        prior = [d for d in snap_dates if d <= t]
        return snaps[prior[-1]] if prior else snaps[snap_dates[0]]

    def biased(t):
        return today

    s1 = stats(perf(px, weights(px, biased, topk)))
    s2 = stats(perf(px, weights(px, pit, topk)))
    w0, w1 = px.index.min().date(), px.index.max().date()
    return s1, s2, len(have), len(ever), w0, w1


def main():
    idxs = [sys.argv[1]] if len(sys.argv) > 1 else ["nifty100", "nifty200", "nifty500"]
    topk = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    print(f"Survivorship correction — momentum+trend (top-{topk}), FREE Wayback point-in-time\n")
    print(f"{'index / window':22}{'members':>9}  {'':<10}{'CAGR':>7}{'Sharpe':>8}{'MaxDD':>7}")
    print("-" * 72)
    for idx in idxs:
        s1, s2, have, ever, w0, w1 = run(idx, topk)
        print(f"{idx:22}{f'{have}/{ever}':>9}  {'BIASED':<10}{s1['cagr']:>6.1%}{s1['sharpe']:>8.2f}{s1['maxdd']:>7.0%}")
        print(f"{f'  {w0}..{w1}':22}{'':>9}  {'CORRECTED':<10}{s2['cagr']:>6.1%}{s2['sharpe']:>8.2f}{s2['maxdd']:>7.0%}")
        print(f"{'':22}{'':>9}  {'-> haircut':<10}"
              f"{(s2['cagr']-s1['cagr'])*100:>+5.1f}pp{s2['sharpe']-s1['sharpe']:>+8.2f}")
        print()


if __name__ == "__main__":
    main()
