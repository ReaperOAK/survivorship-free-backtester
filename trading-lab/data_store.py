"""
data_store.py — reliable local market data, fetched ONCE, stored in DuckDB.

Solves the "stop hammering APIs" problem:
  * SOURCE: NSE bhavcopy — ONE download per trading day = the WHOLE market's EOD
    OHLCV (~2000 EQ stocks). No per-symbol API calls, no throttling.
  * STORE: DuckDB (~/.vibe-trading/market.duckdb) — columnar, fast for backtests,
    embedded (no server). PK (symbol,date) => idempotent, safe to re-run.
  * INCREMENTAL: backfill skips days already stored; `update` grabs only new days.
    After the one-time backfill, daily upkeep = 1 request.

CLI:
  python data_store.py backfill 2023-07-01 [end]   # bulk history (resumable)
  python data_store.py update                        # top up to yesterday
  python data_store.py stats                          # what's stored
  python data_store.py get RELIANCE 2024-01-01 2025-01-01
"""
from __future__ import annotations
import os, sys, io, time, zipfile
import duckdb
import httpx
import pandas as pd

DB = os.path.expanduser("~/.vibe-trading/market.duckdb")
HDRS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36", "Accept": "*/*"}
os.makedirs(os.path.dirname(DB), exist_ok=True)


def _conn():
    con = duckdb.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS prices(
        symbol VARCHAR, date DATE, open DOUBLE, high DOUBLE, low DOUBLE,
        close DOUBLE, volume BIGINT, PRIMARY KEY(symbol, date))""")
    return con


def _url(d: str) -> str:  # d = YYYYMMDD
    return f"https://archives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{d}_F_0000.csv.zip"


def fetch_bhavcopy(d: str) -> pd.DataFrame | None:
    """Download + parse one day's EQ bhavcopy into standard OHLCV. None if no file."""
    for attempt in range(3):
        try:
            r = httpx.get(_url(d), headers=HDRS, timeout=30, follow_redirects=True)
            if r.status_code == 404 or len(r.content) < 1000:
                return None  # holiday/weekend/not-yet-published
            z = zipfile.ZipFile(io.BytesIO(r.content))
            df = pd.read_csv(z.open(z.namelist()[0]))
            eq = df[df["SctySrs"] == "EQ"]
            return pd.DataFrame({
                "symbol": eq["TckrSymb"].astype(str),
                "date": pd.to_datetime(eq["TradDt"]).dt.date,
                "open": eq["OpnPric"].astype(float), "high": eq["HghPric"].astype(float),
                "low": eq["LwPric"].astype(float), "close": eq["ClsPric"].astype(float),
                "volume": eq["TtlTradgVol"].fillna(0).astype("int64"),
            })
        except Exception:
            time.sleep(1.5 + attempt)
    return None


def stored_dates() -> set:
    con = _conn()
    rows = con.execute("SELECT DISTINCT date FROM prices").fetchall()
    con.close()
    return {r[0] for r in rows}


def ingest_day(d: str) -> int:
    df = fetch_bhavcopy(d)
    if df is None or df.empty:
        return 0
    con = _conn()
    con.register("tmp", df)
    con.execute("INSERT INTO prices SELECT * FROM tmp ON CONFLICT DO NOTHING")
    con.close()
    return len(df)


def backfill(start: str, end: str | None = None, gap: float = 0.35):
    end = end or (pd.Timestamp.utcnow().normalize() - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    days = pd.bdate_range(start, end)          # weekdays only
    have = stored_dates()
    todo = [d for d in days if d.date() not in have]
    print(f"Backfill {start}..{end}: {len(todo)} trading days to fetch "
          f"({len(days)-len(todo)} already stored)", flush=True)
    got = 0
    for i, d in enumerate(todo, 1):
        n = ingest_day(d.strftime("%Y%m%d"))
        got += n
        if i % 25 == 0 or n == 0:
            print(f"  [{i}/{len(todo)}] {d.date()} +{n} rows (total ingested {got:,})", flush=True)
        time.sleep(gap)
    print(f"Done. Ingested {got:,} rows.", flush=True)


def update():
    backfill((pd.Timestamp.utcnow().normalize() - pd.Timedelta(days=20)).strftime("%Y-%m-%d"))


def clean_adjusted(symbols, start="2000-01-01", gap=2.0, suffix=".NS"):
    """DATA CLEAN: re-fetch each symbol's split/bonus-ADJUSTED series (yfinance)
    and OVERWRITE the store for the full range — removing the adjusted(yfinance)
    /raw(bhavcopy) seam so the backtest series is internally consistent. Uses
    ON CONFLICT DO UPDATE (yfinance-adjusted wins). Gentle pacing."""
    os.environ.setdefault("VIBE_TRADING_DATA_CACHE", "1"); os.environ.setdefault("TUSHARE_TOKEN", "noop")
    from backtest.loaders.registry import LOADER_REGISTRY, _ensure_registered
    _ensure_registered()
    L = LOADER_REGISTRY["yfinance"]()
    end = (pd.Timestamp.utcnow().normalize() - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"CLEAN (adjusted): {len(symbols)} symbols, overwriting seam...", flush=True)
    ok = 0
    for i, sym in enumerate(symbols, 1):
        for _ in range(3):
            try:
                df = L.fetch([sym + suffix], start, end, interval="1D").get(sym + suffix)
                if df is not None and len(df) >= 250:
                    out = pd.DataFrame({"symbol": sym, "date": pd.to_datetime(df.index).date,
                        "open": df["open"].astype(float), "high": df["high"].astype(float),
                        "low": df["low"].astype(float), "close": df["close"].astype(float),
                        "volume": df.get("volume", 0)})
                    out["volume"] = out["volume"].fillna(0).astype("int64")
                    con = _conn(); con.register("tmp", out)
                    con.execute("""INSERT INTO prices SELECT * FROM tmp
                        ON CONFLICT (symbol,date) DO UPDATE SET
                        open=excluded.open, high=excluded.high, low=excluded.low,
                        close=excluded.close, volume=excluded.volume""")
                    con.close(); ok += 1; break
            except Exception:
                pass
            time.sleep(gap * 2)
        if i % 25 == 0:
            print(f"  [{i}/{len(symbols)}] cleaned {ok}", flush=True)
        time.sleep(gap)
    print(f"CLEAN done: {ok}/{len(symbols)} adjusted + de-seamed.", flush=True)


def backfill_yfinance(symbols, start="2000-01-01", gap=2.0, suffix=".NS",
                      deep_before="2015-01-01"):
    """GENTLE yfinance seed for DEEP history (Yahoo has Indian large-caps back to
    ~2000). Fetch each symbol ONCE, store, then reads come from DuckDB. Skips a
    symbol only if it ALREADY has data starting before `deep_before` (i.e. deep
    history exists) — NOT just because bhavcopy gave it 2 recent years.
    Opens/closes the DB per write so the lock is free between symbols (reads OK)."""
    import datetime
    os.environ.setdefault("VIBE_TRADING_DATA_CACHE", "1")
    os.environ.setdefault("TUSHARE_TOKEN", "noop")
    from backtest.loaders.registry import LOADER_REGISTRY, _ensure_registered
    _ensure_registered()
    L = LOADER_REGISTRY["yfinance"]()
    end = (pd.Timestamp.utcnow().normalize() - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    cutoff = pd.Timestamp(deep_before).date()
    con = _conn()
    have = dict(con.execute("SELECT symbol, MIN(date) FROM prices GROUP BY symbol").fetchall())
    con.close()
    todo = [s for s in symbols if have.get(s) is None or have[s] > cutoff]
    print(f"yfinance DEEP seed: {len(todo)}/{len(symbols)} symbols need deep history "
          f"(gentle {gap}s gap, from {start})", flush=True)
    ok = 0
    for i, sym in enumerate(todo, 1):
        got = 0
        for _ in range(3):
            try:
                df = L.fetch([sym + suffix], start, end, interval="1D").get(sym + suffix)
                if df is not None and len(df) >= 250:
                    out = pd.DataFrame({
                        "symbol": sym, "date": pd.to_datetime(df.index).date,
                        "open": df["open"].astype(float), "high": df["high"].astype(float),
                        "low": df["low"].astype(float), "close": df["close"].astype(float),
                        "volume": df.get("volume", 0)})
                    out["volume"] = out["volume"].fillna(0).astype("int64")
                    con = _conn()
                    con.register("tmp", out)
                    con.execute("INSERT INTO prices SELECT * FROM tmp ON CONFLICT DO NOTHING")
                    con.close()               # release lock between symbols
                    got = len(out); ok += 1; break
            except Exception:
                pass
            time.sleep(gap * 2)
        if i % 20 == 0 or got == 0:
            print(f"  [{i}/{len(todo)}] {sym}: {'+'+str(got) if got else 'miss'} "
                  f"(ok {ok})", flush=True)
        time.sleep(gap)
    print(f"Deep seed done: {ok}/{len(todo)} fetched.", flush=True)


INDEX_FILES = {"nifty50": "ind_nifty50list.csv", "nifty100": "ind_nifty100list.csv",
               "nifty200": "ind_nifty200list.csv", "nifty500": "ind_nifty500list.csv"}


def refresh_index_lists():
    """Fetch NSE index constituents -> store membership (powers universe selection)."""
    con = _conn()
    con.execute("""CREATE TABLE IF NOT EXISTS index_members(
        idx VARCHAR, symbol VARCHAR, company VARCHAR, industry VARCHAR,
        PRIMARY KEY(idx, symbol))""")
    for idx, fn in INDEX_FILES.items():
        r = httpx.get(f"https://archives.nseindia.com/content/indices/{fn}",
                      headers=HDRS, timeout=30, follow_redirects=True)
        df = pd.read_csv(io.StringIO(r.text))
        out = pd.DataFrame({"idx": idx, "symbol": df["Symbol"].astype(str),
                            "company": df["Company Name"], "industry": df["Industry"]})
        con.register("tmp", out)
        con.execute("DELETE FROM index_members WHERE idx=?", [idx])
        con.execute("INSERT INTO index_members SELECT * FROM tmp")
        print(f"  {idx}: {len(out)} members stored")
    con.close()


def index_symbols(idx: str) -> list:
    con = _conn()
    rows = con.execute("SELECT symbol FROM index_members WHERE idx=? ORDER BY symbol", [idx]).fetchall()
    con.close()
    return [r[0] for r in rows]


def all_symbols() -> list:
    con = _conn()
    rows = con.execute("SELECT DISTINCT symbol FROM prices ORDER BY symbol").fetchall()
    con.close()
    return [r[0] for r in rows]


def get(symbols, start, end) -> pd.DataFrame:
    """Read close prices from the STORE (no network). Returns wide df: date x symbol."""
    con = _conn()
    syms = symbols if isinstance(symbols, (list, tuple)) else [symbols]
    ph = ",".join(["?"] * len(syms))
    df = con.execute(
        f"SELECT date, symbol, close FROM prices WHERE symbol IN ({ph}) "
        f"AND date BETWEEN ? AND ? ORDER BY date", [*syms, start, end]).df()
    con.close()
    if df.empty:
        return df
    return df.pivot(index="date", columns="symbol", values="close")


def stats():
    con = _conn()
    r = con.execute("SELECT COUNT(*) AS n_rows, COUNT(DISTINCT symbol) AS n_syms, "
                    "MIN(date) AS mn, MAX(date) AS mx FROM prices").fetchone()
    con.close()
    print(f"Store: {DB}")
    print(f"  rows={r[0]:,}  symbols={r[1]:,}  range={r[2]}..{r[3]}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "backfill":
        backfill(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "update":
        update()
    elif cmd == "seed-yf":  # gentle yfinance seed: python data_store.py seed-yf RELIANCE TCS ...
        backfill_yfinance(sys.argv[2:])
    elif cmd == "indexes":  # refresh NSE index membership lists
        refresh_index_lists()
    elif cmd == "clean-adj":  # re-fetch adjusted + de-seam for an index: clean-adj nifty500
        clean_adjusted(index_symbols(sys.argv[2]) if len(sys.argv) > 2 else index_symbols("nifty500"))
    elif cmd == "seed-index":  # deep-history seed for an index: seed-index nifty500 [start]
        refresh_index_lists()
        start = sys.argv[3] if len(sys.argv) > 3 else "2000-01-01"
        backfill_yfinance(index_symbols(sys.argv[2]), start=start, gap=2.0)
    elif cmd == "get":
        print(get(sys.argv[2], sys.argv[3], sys.argv[4]).tail())
    else:
        stats()
