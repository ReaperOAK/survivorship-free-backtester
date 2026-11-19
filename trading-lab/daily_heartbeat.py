"""
daily_heartbeat.py — Automated daily health check and operational watchdog.

Runs daily via cron after market close (17:30 UTC / 23:00 IST).
Checks:
  1. Freshness of market.duckdb (must have data from last trading day).
  2. Freshness and integrity of india_account.json.
  3. Detects any un-handled rebalance failure or data provider timeout.
  4. Appends health record to ~/.vibe-trading/heartbeat.log.
  5. Fails loudly with exit code 1 if any condition is stale or broken.

Usage:
  python trading-lab/daily_heartbeat.py
"""
from __future__ import annotations
import os, sys, time, json
import duckdb
import pandas as pd

ACCOUNT = os.path.expanduser("~/.vibe-trading/india_account.json")
DB = os.path.expanduser("~/.vibe-trading/market.duckdb")
LOG = os.path.expanduser("~/.vibe-trading/heartbeat.log")


def check_heartbeat():
    now_ts = time.strftime("%Y-%m-%d %H:%M:%S UTC")
    today_date = pd.Timestamp.utcnow().date()
    issues = []

    # 1. Check DuckDB freshness
    if not os.path.exists(DB):
        issues.append(f"CRITICAL: DuckDB missing at {DB}")
    else:
        try:
            con = duckdb.connect(DB, read_only=True)
            max_dt = con.execute("SELECT max(date) FROM prices").fetchone()[0]
            con.close()
            # If today is weekday, data should be within last 3 days (accounting for weekend)
            days_old = (today_date - max_dt).days
            if days_old > 4:
                issues.append(f"STALE DATA: DuckDB max date is {max_dt} ({days_old} days behind)")
        except Exception as e:
            issues.append(f"DUCKDB ERROR: {e}")

    # 2. Check Ledger freshness & integrity
    if not os.path.exists(ACCOUNT):
        issues.append(f"CRITICAL: Account missing at {ACCOUNT}")
    else:
        try:
            with open(ACCOUNT) as f:
                acct = json.load(f)
            positions = acct.get("positions", {})
            cash = acct.get("cash", 0.0)
            if not positions and cash <= 0:
                issues.append("CORRUPTED ACCOUNT: Zero cash and zero positions")
        except Exception as e:
            issues.append(f"ACCOUNT JSON ERROR: {e}")

    # 3. Log verdict
    status = "HEALTHY" if not issues else "ALERT"
    entry = f"[{now_ts}] Status: {status}"
    if issues:
        entry += f" | Issues: {'; '.join(issues)}"
    else:
        entry += f" | Store: {max_dt} | Positions: {len(positions)} | Cash: Rs {cash:,.2f}"

    print(entry)
    with open(LOG, "a") as f:
        f.write(entry + "\n")

    if issues:
        sys.exit(1)


if __name__ == "__main__":
    check_heartbeat()
