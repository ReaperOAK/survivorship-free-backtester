"""
momentum_full.py — momentum across the FULL Indian market, from the local store.

No API calls: reads the DuckDB store (whole market, 2y). Uses DuckDB to pick a
liquid universe fast (top-N by turnover), then computes the same validated
momentum signal on ALL of them — the real universe, not 23 hand-picked names.
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
import duckdb

DB = os.path.expanduser("~/.vibe-trading/market.duckdb")
TOPK, N_LIQUID = 15, 300


def main():
    con = duckdb.connect(DB, read_only=True)
    maxd = con.execute("SELECT MAX(date) FROM prices").fetchone()[0]
    cutoff = pd.Timestamp(maxd) - pd.Timedelta(days=90)

    # 1) liquid universe: top-N by avg daily turnover (close*volume) — fast SQL over 1M rows
    liquid = con.execute("""
        SELECT symbol, AVG(close*volume) AS turnover, COUNT(*) AS n
        FROM prices WHERE date >= ? GROUP BY symbol
        HAVING n >= 40 AND AVG(close) > 20
        ORDER BY turnover DESC LIMIT ?""", [cutoff.date(), N_LIQUID]).df()
    syms = liquid["symbol"].tolist()
    total_market = con.execute("SELECT COUNT(DISTINCT symbol) FROM prices").fetchone()[0]

    # 2) pull their close history from the store (still zero network)
    ph = ",".join(["?"] * len(syms))
    px = con.execute(f"SELECT date, symbol, close FROM prices WHERE symbol IN ({ph}) "
                     f"ORDER BY date", syms).df().pivot(index="date", columns="symbol", values="close")
    con.close()
    px.index = pd.to_datetime(px.index)

    # 3) momentum signal on each (same rules as validated strategy)
    rows = []
    for s in px.columns:
        c = px[s].dropna()
        if len(c) < 252:
            continue
        price = c.iloc[-1]
        sma200 = c.rolling(200).mean().iloc[-1]
        ret6m = c.iloc[-1] / c.iloc[-126] - 1
        carhart = c.iloc[-21] / c.iloc[-252] - 1
        vol = c.pct_change().iloc[-60:].std() * np.sqrt(252)
        eligible = (price > sma200) and (ret6m > 0)
        rows.append((s, price, eligible, ret6m, carhart, vol))
    df = pd.DataFrame(rows, columns=["sym", "price", "elig", "ret6m", "carhart", "vol"])

    print(f"Scanned {len(df)} liquid stocks (from {total_market:,} in the store), "
          f"data through {maxd}. ALL from local DuckDB — zero API calls.\n")
    top = df[df["elig"]].sort_values("carhart", ascending=False).head(TOPK)
    print(f"=== Top {TOPK} momentum stocks across the FULL market ===")
    print(f"{'stock':14}{'price(Rs)':>11}{'6m ret':>9}{'12-1 mom':>10}{'ann.vol':>9}")
    print("-" * 53)
    for _, r in top.iterrows():
        print(f"{r['sym']:14}{r['price']:>11,.0f}{r['ret6m']:>8.0%}{r['carhart']:>10.0%}{r['vol']:>9.0%}")
    print(f"\n{int(df['elig'].sum())}/{len(df)} liquid stocks currently in an uptrend "
          f"(above 200-day avg + positive 6m momentum).")


if __name__ == "__main__":
    main()
