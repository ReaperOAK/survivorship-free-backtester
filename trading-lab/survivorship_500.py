"""
survivorship_500.py — Nifty 500 momentum, point-in-time (survivorship-corrected)
vs biased (current list), using FREE Wayback membership + our store prices.
Window 2019-2026 (Wayback snapshots 2018-2026, 90% price coverage).
"""
from __future__ import annotations
import os, sys, warnings
import numpy as np
import pandas as pd
import duckdb

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(__file__))
from survivorship_test import momentum_trend_weights, perf, stats  # reuse engine
DB = os.path.expanduser("~/.vibe-trading/market.duckdb")


def main():
    con = duckdb.connect(DB, read_only=True)
    hist = con.execute("SELECT snap_date, symbol FROM index_members_hist WHERE idx='nifty500'").df()
    hist["snap_date"] = pd.to_datetime(hist["snap_date"])
    snaps = {d: set(g["symbol"]) for d, g in hist.groupby("snap_date")}
    snap_dates = sorted(snaps)
    ever = sorted(set(hist["symbol"]))
    store = {r[0] for r in con.execute("SELECT DISTINCT symbol FROM prices").fetchall()}
    have = [s for s in ever if s in store]
    ph = ",".join(["?"] * len(have))
    df = con.execute(f"SELECT date,symbol,close FROM prices WHERE symbol IN ({ph}) "
                     f"AND date>='2018-01-01' ORDER BY date", have).df()
    con.close()
    px = df.pivot(index="date", columns="symbol", values="close").ffill(limit=5)
    px.index = pd.to_datetime(px.index)

    current = snaps[snap_dates[-1]]                    # biased = today's list

    def pit(t):                                        # point-in-time: nearest-prior snapshot
        prior = [d for d in snap_dates if d <= t]
        return snaps[prior[-1]] if prior else snaps[snap_dates[0]]

    def biased(t):
        return current

    r_bias = perf(px, momentum_trend_weights(px, biased))
    r_pit = perf(px, momentum_trend_weights(px, pit))
    print(f"Nifty 500 momentum (top-20), 2019-2026 — {len(have)}/{len(ever)} members priced\n")
    print(f"{'version':34}{'CAGR':>8}{'Sharpe':>8}{'MaxDD':>8}")
    print("-" * 58)
    s1, s2 = stats(r_bias), stats(r_pit)
    print(f"{'BIASED (today list)':34}{s1['cagr']:>7.1%}{s1['sharpe']:>8.2f}{s1['maxdd']:>7.0%}")
    print(f"{'CORRECTED (Wayback point-in-time)':34}{s2['cagr']:>7.1%}{s2['sharpe']:>8.2f}{s2['maxdd']:>7.0%}")
    print(f"\nSurvivorship inflation (Nifty 500, 7y): CAGR {(s1['cagr']-s2['cagr'])*100:+.1f}pp, "
          f"Sharpe {s1['sharpe']-s2['sharpe']:+.2f}")
    print("(90% price coverage; 10% missing delisted -> true bias slightly larger.)")


if __name__ == "__main__":
    main()
