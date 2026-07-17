"""
wayback_membership.py — FREE point-in-time Nifty index membership from the
Internet Archive. NSE's constituent CSVs have stable URLs that archive.org has
snapshotted over the years -> we reconstruct 'who was in the index when' for free.
Stores into DuckDB table index_members_hist(idx, snap_date, symbol).
"""
from __future__ import annotations
import os, io, time
import httpx
import pandas as pd
import duckdb

DB = os.path.expanduser("~/.vibe-trading/market.duckdb")
HDRS = {"User-Agent": "Mozilla/5.0"}
URLS = {"nifty500": "niftyindices.com/IndexConstituent/ind_nifty500list.csv",
        "nifty200": "niftyindices.com/IndexConstituent/ind_nifty200list.csv",
        "nifty100": "niftyindices.com/IndexConstituent/ind_nifty100list.csv"}


def snapshots(url, collapse="timestamp:8"):
    q = f"http://web.archive.org/cdx/search/cdx?url={url}&output=json&collapse={collapse}&filter=statuscode:200&limit=200"
    for _ in range(3):
        try:
            d = httpx.get(q, timeout=45).json()
            return [s[1] for s in d[1:]] if len(d) > 1 else []
        except Exception:
            time.sleep(3)
    return []


def fetch_snapshot(ts, url):
    """Fetch the RAW archived CSV (id_ modifier = original file, not HTML wrapper)."""
    for _ in range(3):
        try:
            r = httpx.get(f"https://web.archive.org/web/{ts}id_/https://{url}",
                          headers=HDRS, timeout=45, follow_redirects=True)
            if r.status_code == 200 and "Symbol" in r.text[:2000]:
                df = pd.read_csv(io.StringIO(r.text))
                col = [c for c in df.columns if c.strip().lower() == "symbol"][0]
                return [str(s).strip() for s in df[col].dropna()]
        except Exception:
            time.sleep(3)
    return None


def main():
    con = duckdb.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS index_members_hist(
        idx VARCHAR, snap_date DATE, symbol VARCHAR, PRIMARY KEY(idx, snap_date, symbol))""")
    for idx, url in URLS.items():
        snaps = snapshots(url)
        print(f"{idx}: {len(snaps)} snapshots", flush=True)
        for ts in snaps:
            syms = fetch_snapshot(ts, url)
            if not syms:
                print(f"  {ts}: miss", flush=True); continue
            snap_date = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
            out = pd.DataFrame({"idx": idx, "snap_date": snap_date, "symbol": syms})
            con.register("tmp", out)
            con.execute("INSERT INTO index_members_hist SELECT * FROM tmp ON CONFLICT DO NOTHING")
            print(f"  {snap_date}: {len(syms)} constituents", flush=True)
            time.sleep(1)
    # report
    r = con.execute("""SELECT idx, COUNT(DISTINCT snap_date) snaps, COUNT(DISTINCT symbol) ever,
        MIN(snap_date) mn, MAX(snap_date) mx FROM index_members_hist GROUP BY idx""").fetchall()
    print("\nStored point-in-time membership:")
    for row in r:
        print(f"  {row[0]}: {row[1]} snapshots, {row[2]} distinct symbols ever, {row[3]}..{row[4]}")
    con.close()


if __name__ == "__main__":
    main()
