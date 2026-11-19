"""
india_ledger.py — LOCAL pretend-money account for INDIAN stocks (in rupees).

Starts with ₹10,00,000. Reads india_signal's ensemble picks and buys/sells
to match, using real recent NSE prices + realistic execution cost. Stored in one
JSON file. 

Fail-Loudly Rule: If any held symbol cannot be priced in DuckDB, raises a RuntimeError
rather than silently masking losses at cost basis.

  python india_ledger.py start [--cash 1000000]
  python india_ledger.py rebalance
  python india_ledger.py status
  python india_ledger.py cron
"""
from __future__ import annotations
import os, sys, json, argparse
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import india_signal as strat

ACCOUNT = os.path.expanduser("~/.vibe-trading/india_account.json")
DB = os.path.expanduser("~/.vibe-trading/market.duckdb")
COST = 0.002  # 0.20% round-trip friction baseline (STT, stamp, GST)


def _today():
    return (pd.Timestamp.utcnow().normalize() - pd.Timedelta(days=1)).strftime("%Y-%m-%d")


def load_acct():
    return json.load(open(ACCOUNT)) if os.path.exists(ACCOUNT) else None


def save_acct(a):
    os.makedirs(os.path.dirname(ACCOUNT), exist_ok=True)
    json.dump(a, open(ACCOUNT, "w"), indent=2)


def get_latest_price(sym: str) -> float:
    """Lookup latest closing price for sym from DuckDB; raise RuntimeError if missing."""
    if os.path.exists(DB):
        try:
            import duckdb
            con = duckdb.connect(DB, read_only=True)
            row = con.execute("SELECT close FROM prices WHERE symbol = ? ORDER BY date DESC LIMIT 1", [sym]).fetchone()
            con.close()
            if row and row[0] is not None:
                return float(row[0])
        except Exception as e:
            raise RuntimeError(f"Database error looking up price for '{sym}': {e}")
    raise RuntimeError(f"CRITICAL: No market price found for held symbol '{sym}'. Aborting rather than masking as purchase cost.")


def start(cash):
    a = {"starting_balance": cash, "cash": cash, "positions": {}, "history": [], "opened": _today()}
    save_acct(a)
    print(f"Opened a pretend account with Rs {cash:,.2f}. All cash for now.")
    return a


def _prices_and_targets():
    df, held, weights, cash = strat.compute_targets()
    prices = {s: float(df.loc[s, "price"]) for s in df.index} if not df.empty else {}
    return prices, {k: v for k, v in weights.items() if v > 0}, df, held, cash


def equity(a, prices):
    val = a["cash"]
    for s, p in a["positions"].items():
        if s not in prices:
            prices[s] = get_latest_price(s)
        val += p["qty"] * prices[s]
    return val


def rebalance(a):
    prices, targets, df, held, cash_frac = _prices_and_targets()
    if not prices:
        print("Could not get market data right now (provider busy). Try again shortly.")
        return None
    
    # Ensure every single held position is priced from DuckDB before attempting rebalance
    for s in list(a["positions"].keys()):
        if s not in prices:
            prices[s] = get_latest_price(s)

    total = equity(a, prices)
    print(f"Account value right now: Rs {total:,.2f}\n")
    min_bal = getattr(df, "attrs", {}).get("min_balance")
    if min_bal and total < min_bal:
        strat_name = getattr(df, "attrs", {}).get("strategy", "momentum")
        uni = getattr(df, "attrs", {}).get("universe", "nifty500")
        print(f"NOTE: '{strat_name}' on {uni} needs ~Rs {min_bal:,.0f} to run with WHOLE shares.")

    target_dollars = {s: w * total for s, w in targets.items()}
    trades = []

    # 1) SELL whole shares of anything overweight or no longer a target
    for s in list(a["positions"].keys()):
        cur_qty = int(a["positions"][s]["qty"])
        px = prices[s]
        tgt_qty = int(target_dollars.get(s, 0.0) // px) if px else 0
        if tgt_qty < cur_qty:
            sell_qty = cur_qty - tgt_qty
            proceeds = sell_qty * px * (1 - COST)
            a["cash"] += proceeds
            if tgt_qty <= 0:
                del a["positions"][s]
            else:
                a["positions"][s]["qty"] = tgt_qty
            trades.append(("SELL", s, sell_qty, px, proceeds))

    # 2) BUY whole shares toward targets (biggest intended positions first)
    for s in sorted(target_dollars, key=target_dollars.get, reverse=True):
        px = prices[s]
        cur_qty = int(a["positions"].get(s, {}).get("qty", 0))
        want = int(target_dollars[s] // px) - cur_qty
        if want <= 0:
            continue
        affordable = int(a["cash"] // (px * (1 + COST)))
        buy_qty = min(want, affordable)
        if buy_qty <= 0:
            continue
        spend = buy_qty * px * (1 + COST)
        a["cash"] -= spend
        pos = a["positions"].get(s, {"qty": 0, "avg_price": px, "entry_date": _today()})
        new_qty = pos["qty"] + buy_qty
        pos["avg_price"] = (pos["qty"] * pos["avg_price"] + buy_qty * px) / new_qty if new_qty else px
        pos["qty"] = new_qty
        pos.setdefault("entry_date", _today())
        a["positions"][s] = pos
        trades.append(("BUY", s, buy_qty, px, spend))

    for act, s, q, px, d in trades:
        a["history"].append({"date": _today(), "action": act, "symbol": s,
                             "qty": int(q), "price": round(px, 2), "rupees": round(d, 2)})
    save_acct(a)
    if not trades:
        print("No trades needed — already matching the strategy (or it says stay in cash).")
    else:
        print("Trades just made:")
        for act, s, q, px, d in trades:
            print(f"  {act:4} {int(q):>3} share(s) of {s:11} @ Rs {px:,.2f}  = Rs {d:,.2f}")
    print()
    _report(a, prices)
    return a


def contribute(a, amount):
    """Monthly SIP: add fresh cash, then rebalance."""
    a["cash"] += amount
    a["starting_balance"] += amount
    a["history"].append({"date": _today(), "action": "DEPOSIT", "symbol": "-",
                         "qty": 0, "price": 0, "rupees": amount})
    save_acct(a)
    print(f"Added Rs {amount:,.2f} (monthly SIP). Now investing it...\n")
    return rebalance(a)


def status(a):
    prices, *_ = _prices_and_targets()
    # Explicitly verify and load prices for all held positions; fail loudly if missing
    for s in list(a["positions"].keys()):
        if s not in prices:
            prices[s] = get_latest_price(s)
    _report(a, prices)


def _report(a, prices):
    total = equity(a, prices)
    start_bal = a["starting_balance"]
    pnl = total - start_bal
    pct = pnl / start_bal * 100 if start_bal else 0
    print("=" * 52)
    print(f"YOUR PRETEND ACCOUNT (INR)  (opened {a['opened']})")
    print("=" * 52)
    print(f"Started with:   Rs {start_bal:,.2f}")
    print(f"Cash (unused):  Rs {a['cash']:,.2f}")
    if a["positions"]:
        print("You own:")
        for s, p in a["positions"].items():
            if s not in prices:
                prices[s] = get_latest_price(s)
            px = prices[s]
            val = p["qty"] * px
            gain = (px - p["avg_price"]) * p["qty"]
            print(f"  {s:11} {int(p['qty'])} sh | bought Rs {p['avg_price']:,.2f} since {p['entry_date']}"
                  f" | now Rs {px:,.2f} | worth Rs {val:,.2f} ({'+' if gain>=0 else ''}Rs {gain:,.2f})")
    else:
        print("You own: nothing (100% cash)")
    print("-" * 52)
    print(f"TOTAL VALUE:    Rs {total:,.2f}")
    print(f"You are {'UP' if pnl>=0 else 'DOWN'} Rs {abs(pnl):,.2f}  ({'+' if pnl>=0 else ''}{pct:.1f}%) since start")
    print("=" * 52)


def cron(a):
    """Idempotent monthly auto-rebalance for the research account (ensemble_regime).
    CRITICAL FIX: Only advances last_rebalance_month if rebalance() successfully executes!"""
    month = pd.Timestamp.utcnow().strftime("%Y-%m")
    if a.get("last_rebalance_month") != month:
        print(f"[{_today()}] New month ({month}) — monthly rebalance (ensemble_regime):")
        res = rebalance(a)
        if res is not None:
            a = res
            a["last_rebalance_month"] = month
            save_acct(a)
        else:
            print(f"[{_today()}] Rebalance aborted due to market data error. Will retry tomorrow.")
    else:
        print(f"[{_today()}] Already rebalanced for {month} — status only.")
        status(a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["start", "rebalance", "status", "contribute", "cron"])
    ap.add_argument("--cash", type=float, default=1000000.0)
    args = ap.parse_args()
    a = load_acct()
    if args.cmd == "start":
        start(args.cash)
    elif a is None:
        print("No account yet. Run: python india_ledger.py start --cash 1000000")
    elif args.cmd == "rebalance":
        rebalance(a)
    elif args.cmd == "contribute":
        contribute(a, args.cash)
    elif args.cmd == "status":
        status(a)
    elif args.cmd == "cron":
        cron(a)


if __name__ == "__main__":
    main()
