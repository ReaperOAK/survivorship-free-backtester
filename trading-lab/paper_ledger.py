"""
paper_ledger.py — a LOCAL, pretend-money trading account (no external anything).

Starts with a fake balance (default $100). It reads the momentum strategy's
picks (signal.compute_targets) and buys/sells to match, using real recent
prices and a realistic 0.1% trading cost. Fractional shares allowed (so $100
can still spread across names). Everything is stored in one plain JSON file.

Plain-English on purpose. Commands:
  python paper_ledger.py start [--cash 100]   # open the account
  python paper_ledger.py rebalance            # act on today's strategy picks
  python paper_ledger.py status               # show holdings + profit/loss
"""
from __future__ import annotations
import os, sys, json, argparse
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import momentum_signal as strat  # our momentum signal (compute_targets, load)

ACCOUNT = os.path.expanduser("~/.vibe-trading/paper_account.json")
COST = 0.001  # 0.1% per trade (broker fee + slippage stand-in)


def _today():
    return (pd.Timestamp.utcnow().normalize() - pd.Timedelta(days=1)).strftime("%Y-%m-%d")


def load_acct():
    if not os.path.exists(ACCOUNT):
        return None
    return json.load(open(ACCOUNT))


def save_acct(a):
    os.makedirs(os.path.dirname(ACCOUNT), exist_ok=True)
    json.dump(a, open(ACCOUNT, "w"), indent=2)


def start(cash):
    a = {"starting_balance": cash, "cash": cash, "positions": {}, "history": [],
         "opened": _today()}
    save_acct(a)
    print(f"Opened a pretend account with ${cash:.2f}. All cash for now.")
    return a


def _prices_and_targets():
    """Return (price_map, target_weights, note). Uses the momentum strategy."""
    df, held, weights, cash = strat.compute_targets()
    prices = {s: float(df.loc[s, "price"]) for s in df.index} if not df.empty else {}
    return prices, {k: v for k, v in weights.items() if v > 0}, df, held, cash


def equity(a, prices):
    val = a["cash"]
    for s, p in a["positions"].items():
        px = prices.get(s, p["avg_price"])
        val += p["qty"] * px
    return val


def rebalance(a):
    prices, targets, df, held, cash_frac = _prices_and_targets()
    if not prices:
        print("Could not get market data right now (provider busy). Try again shortly.")
        return a
    total = equity(a, prices)
    print(f"Account value right now: ${total:.2f}\n")

    # target dollar amount per symbol
    target_dollars = {s: w * total for s, w in targets.items()}
    trades = []

    # 1) SELL anything we hold that's no longer a target (or overweight)
    for s in list(a["positions"].keys()):
        cur_qty = a["positions"][s]["qty"]
        px = prices.get(s, a["positions"][s]["avg_price"])
        tgt_qty = target_dollars.get(s, 0.0) / px if px else 0.0
        if tgt_qty < cur_qty - 1e-9:
            sell_qty = cur_qty - tgt_qty
            proceeds = sell_qty * px * (1 - COST)
            a["cash"] += proceeds
            if tgt_qty <= 1e-9:
                del a["positions"][s]
            else:
                a["positions"][s]["qty"] = tgt_qty
            trades.append(("SELL", s, sell_qty, px, proceeds))

    # 2) BUY toward targets
    for s, tgt_d in target_dollars.items():
        px = prices[s]
        cur_qty = a["positions"].get(s, {}).get("qty", 0.0)
        cur_d = cur_qty * px
        if tgt_d > cur_d + 1e-9:
            spend = min(tgt_d - cur_d, a["cash"])
            if spend <= 0.01:
                continue
            buy_qty = spend * (1 - COST) / px
            a["cash"] -= spend
            pos = a["positions"].get(s, {"qty": 0.0, "avg_price": px, "entry_date": _today()})
            new_qty = pos["qty"] + buy_qty
            pos["avg_price"] = (pos["qty"] * pos["avg_price"] + buy_qty * px) / new_qty if new_qty else px
            pos["qty"] = new_qty
            pos.setdefault("entry_date", _today())
            a["positions"][s] = pos
            trades.append(("BUY", s, buy_qty, px, spend))

    for act, s, q, px, d in trades:
        a["history"].append({"date": _today(), "action": act, "symbol": s,
                             "qty": round(q, 6), "price": round(px, 2), "dollars": round(d, 2)})
    save_acct(a)

    if not trades:
        print("No trades needed — already matching the strategy (or it says stay in cash).")
    else:
        print("Trades just made:")
        for act, s, q, px, d in trades:
            print(f"  {act:4} {q:.4f} of {s:8} @ ${px:,.2f}  = ${d:,.2f}")
    print()
    _report(a, prices, df, held, cash_frac)
    return a


def status(a):
    prices, targets, df, held, cash_frac = _prices_and_targets()
    if not prices:
        # fall back to stored avg prices
        prices = {s: p["avg_price"] for s, p in a["positions"].items()}
    _report(a, prices, df, held, cash_frac)


def _report(a, prices, df=None, held=None, cash_frac=None):
    total = equity(a, prices)
    start_bal = a["starting_balance"]
    pnl = total - start_bal
    pct = pnl / start_bal * 100 if start_bal else 0
    print("=" * 46)
    print(f"YOUR PRETEND ACCOUNT  (opened {a['opened']})")
    print("=" * 46)
    print(f"Started with:   ${start_bal:,.2f}")
    print(f"Cash (unused):  ${a['cash']:,.2f}")
    if a["positions"]:
        print("You own:")
        for s, p in a["positions"].items():
            px = prices.get(s, p["avg_price"])
            val = p["qty"] * px
            gain = (px - p["avg_price"]) * p["qty"]
            print(f"  {s:8} {p['qty']:.4f} units | bought @ ${p['avg_price']:,.2f} "
                  f"since {p['entry_date']} | now ${px:,.2f} | worth ${val:,.2f} "
                  f"({'+' if gain>=0 else ''}${gain:,.2f})")
    else:
        print("You own: nothing (100% cash)")
    print("-" * 46)
    print(f"TOTAL VALUE:    ${total:,.2f}")
    updown = "UP" if pnl >= 0 else "DOWN"
    print(f"You are {updown} ${abs(pnl):,.2f}  ({'+' if pnl>=0 else ''}{pct:.1f}%) since you started")
    print("=" * 46)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["start", "rebalance", "status"])
    ap.add_argument("--cash", type=float, default=100.0)
    args = ap.parse_args()
    a = load_acct()
    if args.cmd == "start":
        start(args.cash)
    elif a is None:
        print("No account yet. Run: python paper_ledger.py start --cash 100")
    elif args.cmd == "rebalance":
        rebalance(a)
    elif args.cmd == "status":
        status(a)


if __name__ == "__main__":
    main()
