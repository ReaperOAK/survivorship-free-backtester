"""
fetch_delisted.py — chase the last ~10%: historical prices for stocks that WERE in
the Nifty 500 (index_members_hist) but have no prices in our store (they got dropped/
delisted/merged out — exactly the losers survivorship bias hides).

HONESTY RULE: we fetch each OLD ticker's OWN frozen Yahoo history only (.NS then .BO).
We deliberately do NOT substitute a successor/acquirer ticker (e.g. GRUH->BANDHAN),
because that would splice a different company's returns into the delisted window and
fake the correction. Truly-defunct names (DHFL, JETAIRWAYS...) will simply return
nothing — and we report that honestly.

Free source: Yahoo via yfinance, gentle pacing. Stores into prices ON CONFLICT DO NOTHING.
"""
from __future__ import annotations
import os, sys, time, warnings
import pandas as pd
import duckdb
import yfinance as yf

warnings.filterwarnings("ignore")
DB = os.path.expanduser("~/.vibe-trading/market.duckdb")


def missing_symbols(con):
    store = {x[0] for x in con.execute("SELECT DISTINCT symbol FROM prices").fetchall()}
    ever = {x[0] for x in con.execute("SELECT DISTINCT symbol FROM index_members_hist").fetchall()}
    # drop NSE 'DUMMY*' corporate-action placeholders (not real tradeable stocks)
    return sorted(s for s in (ever - store) if not s.startswith("DUMMY"))


def fetch_one(sym):
    for suffix in (".NS", ".BO"):        # NSE first, then BSE (some delisted survive on BSE)
        try:
            df = yf.download(sym + suffix, start="2000-01-01", auto_adjust=True,
                             progress=False, threads=False)
            if df is None or df.empty or len(df) < 60:
                continue
            df = df.reset_index()
            if isinstance(df.columns, pd.MultiIndex):        # yf sometimes returns MultiIndex
                df.columns = [c[0] for c in df.columns]
            out = pd.DataFrame({
                "symbol": sym,
                "date": pd.to_datetime(df["Date"]).dt.date,
                "open": df["Open"].astype(float), "high": df["High"].astype(float),
                "low": df["Low"].astype(float), "close": df["Close"].astype(float),
                "volume": df["Volume"].fillna(0).astype("int64"),
            }).dropna(subset=["close"])
            if len(out) >= 60:
                return out, suffix
        except Exception:
            pass
    return None, None


def main():
    con = duckdb.connect(DB)
    syms = missing_symbols(con)
    print(f"Chasing {len(syms)} dropped/delisted Nifty-500 names (DUMMY* excluded)...\n", flush=True)
    got, empty = [], []
    for i, sym in enumerate(syms, 1):
        out, src = fetch_one(sym)
        if out is None:
            empty.append(sym)
            print(f"  [{i:>2}/{len(syms)}] {sym:14} — no free data (defunct)", flush=True)
        else:
            con.register("tmp", out)
            con.execute("INSERT INTO prices SELECT symbol,date,open,high,low,close,volume "
                        "FROM tmp ON CONFLICT DO NOTHING")
            con.unregister("tmp")
            d0, d1 = out["date"].min(), out["date"].max()
            got.append(sym)
            print(f"  [{i:>2}/{len(syms)}] {sym:14} — {len(out):>5} rows {d0}..{d1} ({src})", flush=True)
        time.sleep(1.2)                  # gentle on Yahoo
    print(f"\nDone. Recovered {len(got)}/{len(syms)} delisted names; "
          f"{len(empty)} truly defunct (no free data).")
    print(f"Recovered: {got}")
    print(f"\nStill missing (defunct): {empty}")
    con.close()


if __name__ == "__main__":
    main()
