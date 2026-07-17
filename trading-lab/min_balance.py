"""
min_balance.py — the minimum balance to actually RUN a whole-share strategy.

Two thresholds per strategy (whole shares, NSE):
  * BARE minimum   = can hold >=1 whole share of each of the N held names
                     (worst case = the N most expensive names).
  * COMFORTABLE min = capital where whole-share rounding wastes < ~10% as idle
                     cash (positions roughly match target weights).
Uses the current cached universe prices.
"""
from __future__ import annotations
import os, sys, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(__file__))
import india_signal as strat

def universe_prices():
    df, held, weights, cash = strat.compute_targets()
    return df["price"].astype(float).sort_values()  # Series: symbol -> price

def comfortable_min(prices_of_held, target_frac=0.90):
    """Smallest capital where equal-weight whole-share deploys >= target_frac."""
    n = len(prices_of_held)
    for C in range(5000, 2_000_001, 5000):
        per = C / n
        shares = np.floor(per / prices_of_held)
        deployed = float((shares * prices_of_held).sum())
        if deployed / C >= target_frac and (shares >= 1).all():
            return C
    return None

def main():
    prices = universe_prices()
    print(f"Universe: {len(prices)} stocks, price range Rs {prices.min():,.0f}-{prices.max():,.0f}\n")
    print(f"{'strategy (hold N)':20}{'bare min':>14}{'comfortable min':>18}")
    print("-" * 52)
    for N in [6, 12]:
        priciest = prices.tail(N)                 # worst-case selection
        bare = float(priciest.sum())              # 1 share of each of the N priciest
        comf = comfortable_min(priciest.values)
        comf_s = f"Rs {comf:,.0f}" if comf else ">Rs 20L"
        print(f"hold-{N:<15}Rs {bare:>10,.0f}{comf_s:>18}")
    print("\nInterpretation for a Rs 10,000 account:")
    print("  -> below the bare minimum for BOTH -> can't run diversified stocks.")
    print("  -> honest path: Nifty index fund/ETF (fractional units) until the")
    print("     SIP grows the balance past the comfortable minimum.")

if __name__ == "__main__":
    main()
