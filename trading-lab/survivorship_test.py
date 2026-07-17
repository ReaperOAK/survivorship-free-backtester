"""
survivorship_test.py — Nifty 50 backtest WITH point-in-time membership vs WITHOUT
(the survivorship-biased current-list version). Quantifies how much survivorship
inflated our earlier numbers.

Data: Kaggle historical Nifty-50 monthly constituent weights (2008-2025) +
prices from our store (incl. delisted RCOM/RELCAPITAL we could fetch).
Honest gap: 12 delisted/merged names have no free price data -> excluded (noted).
"""
from __future__ import annotations
import os, sys, warnings
import numpy as np
import pandas as pd
import duckdb

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(__file__))
DB = os.path.expanduser("~/.vibe-trading/market.duckdb")
WEIGHTS = "/home/reaperoak/Downloads/nifty50_hist/weights.csv"
COST, ANN, TOPK = 0.0005, 252, 10


def load_membership():
    w = pd.read_csv(WEIGHTS)
    w["DATE"] = pd.to_datetime(w["DATE"])
    w = w.set_index("DATE")
    # month -> set of constituents (weight>0) that month
    return {d: set(row[row > 0].index) for d, row in w.iterrows()}, list(w.columns)


def load_prices(symbols):
    con = duckdb.connect(DB, read_only=True)
    ph = ",".join(["?"] * len(symbols))
    df = con.execute(f"SELECT date,symbol,close FROM prices WHERE symbol IN ({ph}) "
                     f"AND date>='2008-01-01' ORDER BY date", symbols).df()
    con.close()
    px = df.pivot(index="date", columns="symbol", values="close")
    px.index = pd.to_datetime(px.index)
    return px.ffill(limit=5)


def momentum_trend_weights(px, universe_fn):
    """universe_fn(t) -> set of eligible symbols at month t (point-in-time or fixed)."""
    sma = px.rolling(200).mean(); mom = px / px.shift(126) - 1; car = px.shift(21) / px.shift(252) - 1
    W = pd.DataFrame(np.nan, index=px.index, columns=px.columns)   # NaN -> set on rebalance -> ffill
    for t in px.resample("ME").last().index:
        if t not in px.index or px.index.get_loc(t) < 252:
            continue
        w = pd.Series(0.0, index=px.columns)   # COMPLETE vector (0s included)
        uni = [s for s in universe_fn(t) if s in px.columns]
        if uni:
            sub_car = car.loc[t, uni].dropna()
            trend = (px.loc[t, uni] > sma.loc[t, uni]) & (mom.loc[t, uni] > 0)
            elig = sub_car[trend.reindex(sub_car.index).fillna(False)]
            top = elig.sort_values(ascending=False).head(TOPK).index
            if len(top):
                w[top] = 1.0 / TOPK
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


def main():
    membership, ever = load_membership()
    con = duckdb.connect(DB, read_only=True)
    in_store = {r[0] for r in con.execute("SELECT DISTINCT symbol FROM prices").fetchall()}
    con.close()
    have = [s for s in ever if s in in_store]
    missing = [s for s in ever if s not in in_store]
    px = load_prices(have)
    print(f"Nifty 50 survivorship test — {len(have)}/{len(ever)} ever-members have prices "
          f"({len(missing)} delisted/merged unfetchable: {missing})\n")

    months = sorted(membership)
    def pit_universe(t):     # point-in-time: constituents that month (survivorship-FREE)
        key = min(months, key=lambda m: abs((m - t).days))
        return membership[key]
    def biased_universe(t):  # current list only (survivorship-BIASED)
        return membership[months[-1]]

    r_pit = perf(px, momentum_trend_weights(px, pit_universe))
    r_bias = perf(px, momentum_trend_weights(px, biased_universe))
    print(f"{'version':32}{'CAGR':>8}{'Sharpe':>8}{'MaxDD':>8}")
    print("-" * 56)
    s1 = stats(r_bias); s2 = stats(r_pit)
    print(f"{'BIASED (today''s constituents)':32}{s1['cagr']:>7.1%}{s1['sharpe']:>8.2f}{s1['maxdd']:>7.0%}")
    print(f"{'CORRECTED (point-in-time)':32}{s2['cagr']:>7.1%}{s2['sharpe']:>8.2f}{s2['maxdd']:>7.0%}")
    print(f"\nSurvivorship inflation: CAGR {(s1['cagr']-s2['cagr'])*100:+.1f}pp, "
          f"Sharpe {s1['sharpe']-s2['sharpe']:+.2f}")
    print("(Partial fix — 12 delisted names lack free prices, so true bias is a bit larger.)")


if __name__ == "__main__":
    main()
