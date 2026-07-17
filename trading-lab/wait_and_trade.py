"""
wait_and_trade.py — wait out the Yahoo data block, then trade automatically.

Every ~20 min: gently probe one US symbol. Once the feed responds, fetch the
whole universe into the CSV cache, then run the $100 paper rebalance and print
a plain-English report. Gives up after a few hours if still blocked.

Gentle by design (1 probe per cycle) so we don't keep re-arming the block.
"""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
import momentum_signal as strat
import warm_cache
import paper_ledger as pl

PROBE = "SPY"
MAX_ATTEMPTS = 6
WAIT = 1200          # 20 min between attempts
GAP = 6              # between symbols once unblocked


def main():
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n[attempt {attempt}/{MAX_ATTEMPTS}] probing {PROBE} ...", flush=True)
        unblocked = warm_cache.have_fresh(PROBE) or warm_cache.fetch_one(PROBE, "yfinance")
        if unblocked:
            print("Data feed is responding -> fetching the full universe (gently).", flush=True)
            for c in strat.US:
                if not warm_cache.have_fresh(c):
                    ok = warm_cache.fetch_one(c, "yfinance")
                    print(f"  {'ok ' if ok else 'miss'} {c}", flush=True)
                    time.sleep(GAP)
            for ls in strat.CRYPTO:
                if not warm_cache.have_fresh(ls):
                    warm_cache.fetch_one(ls, "ccxt"); time.sleep(2)
            cached = sum(1 for c in strat.US if warm_cache.have_fresh(c))
            print(f"US symbols cached: {cached}/{len(strat.US)}", flush=True)
            if cached >= 12:
                a = pl.load_acct() or pl.start(100.0)
                print("\n" + "=" * 50 + "\nRUNNING THE STRATEGY ON YOUR $100 ACCOUNT\n" + "=" * 50, flush=True)
                pl.rebalance(a)
                print("\n[wait_and_trade] TRADE_COMPLETE", flush=True)
                return
            print("Not enough symbols cached yet; will retry.", flush=True)
        else:
            print("Still blocked.", flush=True)
        if attempt < MAX_ATTEMPTS:
            print(f"Sleeping {WAIT // 60} min before next try...", flush=True)
            time.sleep(WAIT)
    print("\n[wait_and_trade] GAVE_UP — data feed still blocked after all attempts. "
          "Re-run trading-lab/wait_and_trade.py later.", flush=True)


if __name__ == "__main__":
    main()
