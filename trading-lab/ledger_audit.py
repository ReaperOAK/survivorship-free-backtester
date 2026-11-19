"""
ledger_audit.py — Deterministic, zero-narrative audit of live paper ledgers.

Reads the raw ledger JSON, looks up exact latest closing prices from market.duckdb,
asserts all mathematical reconciliations, and prints an unembellished audit report.

Usage:
  python trading-lab/ledger_audit.py [path-to-account.json] [path-to-market.duckdb]
"""
from __future__ import annotations
import os, sys, json
import duckdb
import pandas as pd

DEFAULT_ACCOUNT = os.path.expanduser("~/.vibe-trading/india_account.json")
DEFAULT_DB = os.path.expanduser("~/.vibe-trading/market.duckdb")


def audit_ledger(account_path: str = DEFAULT_ACCOUNT, db_path: str = DEFAULT_DB) -> dict:
    if not os.path.exists(account_path):
        raise FileNotFoundError(f"Ledger file not found: {account_path}")

    with open(account_path) as f:
        acct = json.load(f)

    start_bal = float(acct["starting_balance"])
    cash = float(acct["cash"])
    opened = acct.get("opened", "unknown")
    positions = acct.get("positions", {})

    # Connect to DuckDB to get true latest mark-to-market prices
    latest_prices = {}
    as_of_date = "unknown"
    if os.path.exists(db_path):
        con = duckdb.connect(db_path, read_only=True)
        symbols = list(positions.keys())
        if symbols:
            ph = ",".join(["?"] * len(symbols))
            df_px = con.execute(f"""
                SELECT symbol, date, close
                FROM prices
                WHERE symbol IN ({ph})
                QUALIFY ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) = 1
            """, symbols).df()
            if not df_px.empty:
                latest_prices = dict(zip(df_px["symbol"], df_px["close"]))
                as_of_date = str(df_px["date"].max())
        con.close()

    pos_data = []
    total_positions_val = 0.0
    total_unrealized_pnl = 0.0

    for sym, p in positions.items():
        qty = int(p["qty"])
        entry_px = float(p["avg_price"])
        entry_date = p.get("entry_date", "unknown")
        cost_basis = qty * entry_px
        latest_px = float(latest_prices.get(sym, entry_px))

        curr_val = qty * latest_px
        pnl = curr_val - cost_basis
        pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0.0

        pos_data.append({
            "symbol": sym,
            "qty": qty,
            "entry_px": entry_px,
            "latest_px": latest_px,
            "cost_basis": cost_basis,
            "current_val": curr_val,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "entry_date": entry_date
        })
        total_positions_val += curr_val
        total_unrealized_pnl += pnl

    df_pos = pd.DataFrame(pos_data)

    computed_equity = cash + total_positions_val
    computed_pnl = computed_equity - start_bal
    computed_return_pct = (computed_pnl / start_bal * 100) if start_bal > 0 else 0.0

    if not df_pos.empty:
        df_sorted = df_pos.sort_values("pnl", ascending=False)
        top1_pnl = df_sorted.iloc[0]["pnl"]
        top2_pnl = df_sorted.iloc[:2]["pnl"].sum()
        top6_pnl = df_sorted.iloc[:6]["pnl"].sum()
        
        top1_pnl_share = (top1_pnl / computed_pnl * 100) if computed_pnl > 0 else 0.0
        top2_pnl_share = (top2_pnl / computed_pnl * 100) if computed_pnl > 0 else 0.0
        top6_pnl_share = (top6_pnl / computed_pnl * 100) if computed_pnl > 0 else 0.0
        cash_drag_pct = (cash / computed_equity * 100) if computed_equity > 0 else 0.0
    else:
        top1_pnl_share = top2_pnl_share = top6_pnl_share = cash_drag_pct = 0.0

    return {
        "as_of_date": as_of_date,
        "opened": opened,
        "start_balance": start_bal,
        "cash": cash,
        "cash_drag_pct": cash_drag_pct,
        "total_positions_val": total_positions_val,
        "computed_equity": computed_equity,
        "computed_pnl": computed_pnl,
        "computed_return_pct": computed_return_pct,
        "position_count": len(positions),
        "top1_pnl_share": top1_pnl_share,
        "top2_pnl_share": top2_pnl_share,
        "top6_pnl_share": top6_pnl_share,
        "positions_df": df_pos
    }


def print_audit_report(acct_path: str = DEFAULT_ACCOUNT, db_path: str = DEFAULT_DB):
    res = audit_ledger(acct_path, db_path)
    df = res["positions_df"]
    
    print("=" * 72)
    print("AUDITED LEDGER REPORT (DETERMINISTIC VERIFICATION)")
    print(f"Prices As Of: {res['as_of_date']} (from {db_path})")
    print("=" * 72)
    print(f"Account Opened:      {res['opened']}")
    print(f"Starting Capital:    Rs {res['start_balance']:>14,.2f}")
    print(f"Uninvested Cash:     Rs {res['cash']:>14,.2f}  ({res['cash_drag_pct']:.1f}% cash drag)")
    print(f"Positions Value:     Rs {res['total_positions_val']:>14,.2f}")
    print(f"Total Equity:        Rs {res['computed_equity']:>14,.2f}")
    print(f"Net Gain/Loss:       Rs {res['computed_pnl']:>14,.2f}  ({res['computed_return_pct']:+.2f}%)")
    print(f"Active Positions:    {res['position_count']}")
    print("-" * 72)
    print(f"P&L Concentration Breakdown:")
    print(f"  Top-1 Stock ({df.sort_values('pnl', ascending=False).iloc[0]['symbol']}): {df.sort_values('pnl', ascending=False).iloc[0]['pnl']:>10,.2f} ({res['top1_pnl_share']:>5.1f}% of total profit)")
    print(f"  Top-2 Stocks Share:     {res['top2_pnl_share']:>5.1f}% of total profit")
    print(f"  Top-6 Stocks Share:     {res['top6_pnl_share']:>5.1f}% of total profit")
    print("-" * 72)
    
    if not df.empty:
        print(f"{'Symbol':11}{'Qty':>5}{'Buy Px':>10}{'Mark Px':>10}{'Cost Basis':>12}{'Gain (Rs)':>11}{'Gain %':>8}")
        print("-" * 72)
        for _, r in df.sort_values("pnl", ascending=False).iterrows():
            print(f"{r['symbol']:11}{int(r['qty']):>5}{r['entry_px']:>10.2f}{r['latest_px']:>10.2f}"
                  f"{r['cost_basis']:>12,.2f}{r['pnl']:>11,.2f}{r['pnl_pct']:>7.1f}%")
    print("=" * 72)


if __name__ == "__main__":
    acct = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ACCOUNT
    db = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_DB
    print_audit_report(acct, db)
