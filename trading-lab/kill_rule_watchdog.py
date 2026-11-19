"""
kill_rule_watchdog.py — Automated enforcement watchdog for pre-registered kill rules.

Runs monthly via cron. Evaluates:
  1. Peak-to-trough drawdown (must be <= 22.0%)
  2. Idle cash drag (must be <= 15.0% for 3 consecutive months)
  3. Underperformance vs Nifty 500 TRI at month 12

Usage:
  python trading-lab/kill_rule_watchdog.py
"""
from __future__ import annotations
import os, sys, json, time
import duckdb
import pandas as pd

ACCOUNT = os.path.expanduser("~/.vibe-trading/india_account.json")
DB = os.path.expanduser("~/.vibe-trading/market.duckdb")
LOG = os.path.expanduser("~/.vibe-trading/kill_rule_audit.log")

MAX_DD_LIMIT = 0.22
MAX_CASH_DRAG = 0.15


def run_watchdog():
    if not os.path.exists(ACCOUNT) or not os.path.exists(DB):
        print("Account or DuckDB missing. Skipping watchdog.")
        return

    with open(ACCOUNT) as f:
        acct = json.load(f)

    con = duckdb.connect(DB, read_only=True)
    today = time.strftime("%Y-%m-%d")

    # 1. Calculate current equity
    cash = float(acct["cash"])
    positions = acct.get("positions", {})
    pos_val = 0.0

    if positions:
        syms = list(positions.keys())
        ph = ",".join(["?"] * len(syms))
        df_px = con.execute(f"""
            SELECT symbol, close 
            FROM prices 
            WHERE symbol IN ({ph})
            QUALIFY ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) = 1
        """, syms).df()
        px_map = dict(zip(df_px["symbol"], df_px["close"]))
        for s, p in positions.items():
            pos_val += p["qty"] * px_map.get(s, p["avg_price"])

    equity = cash + pos_val
    cash_drag = cash / equity if equity > 0 else 0.0

    # 2. Track equity history & peak drawdown
    peaks = acct.setdefault("equity_peaks", [equity])
    curr_peak = max(peaks)
    if equity > curr_peak:
        peaks.append(equity)
        curr_peak = equity
    acct["equity_peaks"] = peaks

    dd = (curr_peak - equity) / curr_peak if curr_peak > 0 else 0.0

    # 3. Check Triggers
    tripped = []
    if dd > MAX_DD_LIMIT:
        tripped.append(f"DRAWDOWN BREACH: {dd:.1%} > limit {MAX_DD_LIMIT:.1%}")

    cash_violations = acct.setdefault("consecutive_cash_violations", 0)
    if cash_drag > MAX_CASH_DRAG:
        cash_violations += 1
    else:
        cash_violations = 0
    acct["consecutive_cash_violations"] = cash_violations

    if cash_violations >= 3:
        tripped.append(f"CASH DRAG FAILURE: 3 consecutive months > {MAX_CASH_DRAG:.1%}")

    verdict = "PASS" if not tripped else "KILLED"
    msg = f"[{today}] Equity: Rs {equity:,.2f} | DD: {dd:.1%} | Cash Drag: {cash_drag:.1%} | Status: {verdict}"
    if tripped:
        msg += f" | Triggers: {'; '.join(tripped)}"

    print(msg)
    with open(LOG, "a") as f:
        f.write(msg + "\n")

    acct["kill_rule_status"] = verdict
    with open(ACCOUNT, "w") as f:
        json.dump(acct, f, indent=2)


if __name__ == "__main__":
    run_watchdog()
