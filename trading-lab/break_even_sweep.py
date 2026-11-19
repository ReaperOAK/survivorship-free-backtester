"""
break_even_sweep.py — Parameter sweep to discover the break-even friction threshold.

Sweeps round-trip execution friction from 0.10% to 1.00% on the canonical
ensemble strategy over the survivorship-corrected Nifty 500 universe (2017–2026),
accounting for explicit daily liquidation when the 200-SMA regime trips.

Usage:
  python trading-lab/break_even_sweep.py [nifty500|nifty200]
"""
from __future__ import annotations
import os, sys, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(__file__))
from strategy_tournament import (load, indicators, market_regime, rebal_dates,
                                 build_W, stats)

DP_CHARGE_PER_SELL = 15.93     # CDSL flat DP fee in INR per sell transaction
DEFAULT_CAPITAL = 1_000_000.0   # Rs 10 Lakh notional portfolio
ANN = 252


def run_friction_sweep(idx: str = "nifty500", topk: int = 20):
    px, pit, have, ever = load(idx)
    ind = indicators(px)
    regime = market_regime(px)
    reb = rebal_dates(px)

    # 1. Benchmark (Buy & Hold)
    Wbh = build_W(px, ind, pit, "buyhold", topk, False, "equal")
    Wp_bh = Wbh.shift(1).fillna(0)
    turn_bh = Wp_bh.diff().abs().sum(axis=1).fillna(0)
    rets = px.pct_change().clip(-0.35, 0.35).fillna(0)
    r_bh = (Wp_bh * rets).sum(axis=1) - turn_bh * 0.001
    s_bh = stats(r_bh, turn_bh)

    # 2. Canonical Ensemble Weights (1/3 Mom + 1/3 Low-Vol + 1/3 Mom-Vol)
    Wmt = build_W(px, ind, pit, "car", topk, True, "equal")
    Wlv = build_W(px, ind, pit, "lowvol", topk, False, "equal")
    Wmv = build_W(px, ind, pit, "momvol", topk, True, "equal")
    Wens = (Wmt + Wlv + Wmv) / 3.0

    # Explicit daily regime liquidation matrix:
    # When market < 200 SMA, weights drop to 0.0 (liquidating all positions)
    W_canonical = Wens.mul(regime.shift(1).fillna(True).astype(float), axis=0)
    Wp = W_canonical.shift(1).fillna(0)
    turn = Wp.diff().abs().sum(axis=1).fillna(0)

    # Calculate flat DP fee drag per year
    pos_diff = Wp.diff().fillna(0)
    sells_per_year = (pos_diff < -0.001).sum(axis=1).sum() / (len(px) / ANN)
    annual_dp_drag = (sells_per_year * DP_CHARGE_PER_SELL) / DEFAULT_CAPITAL

    print(f"\n{'='*75}")
    print(f"CANONICAL BREAK-EVEN FRICTION SWEEP — {idx} ({have}/{ever} stocks)")
    print(f"Survivorship-corrected, 2017..2026 | Daily Regime Stop with Turnover Costs")
    print(f"Notional: Rs {DEFAULT_CAPITAL/1e5:.0f}L | Sells/yr: {sells_per_year:.0f} | DP fee drag: ~{annual_dp_drag*100:.3f}%/yr")
    print(f"Baseline Benchmark (Buy & Hold): Sharpe {s_bh['sharpe']:.2f}, CAGR {s_bh['cagr']:.1%}, MaxDD {s_bh['maxdd']:.0%}")
    print(f"{'='*75}\n")

    friction_levels = [0.0005, 0.0010, 0.0015, 0.0020, 0.0025, 0.0030, 0.0040, 0.0050]
    
    print(f"{'Cost / Turn':>12}  {'Round-Trip':>12}  {'Sharpe':>8}  {'CAGR':>8}  {'MaxDD':>8}  {'Edge vs B&H':>13}")
    print("-" * 70)

    breakeven_cost = None
    for cost in friction_levels:
        r = (Wp * rets).sum(axis=1) - turn * cost - (annual_dp_drag / ANN)
        s = stats(r, turn)
        
        edge_sharpe = s["sharpe"] - s_bh["sharpe"]
        status_flag = "  << BEATS B&H" if edge_sharpe > 0 else "  << LOSES TO B&H"
        
        if breakeven_cost is None and edge_sharpe <= 0:
            breakeven_cost = cost

        print(f"{cost*100:>10.2f}%  {cost*200:>10.2f}%  {s['sharpe']:>8.2f}  {s['cagr']:>7.1%}  {s['maxdd']:>7.1%}  {edge_sharpe:>+10.2f} SR{status_flag}")

    print("-" * 70)
    print("MANDATORY INDIAN FRICTION BREAKDOWN (Delivery Equities):")
    print("  • STT: 0.10% on Buy + 0.10% on Sell = 0.20% Round-Trip")
    print("  • Stamp Duty (0.015%), GST (18%) on charges, SEBI fees: ~0.02%")
    print(f"  • Flat DP Fee (CDSL): Rs 15.93/sell = ~{annual_dp_drag*100:.2f}% annual drag on Rs 10L")
    print("  • Realistic baseline friction: ~0.12% per turn (0.24% round-trip) BEFORE spread/impact.")
    
    if breakeven_cost is not None:
        print(f"\nCRITICAL THRESHOLD: Strategy Sharpe drops below Buy & Hold at ~{breakeven_cost*200:.2f}% round-trip friction.")
    else:
        print(f"\nCRITICAL THRESHOLD: Strategy Sharpe remained above Buy & Hold up to 1.00% round-trip friction.")
    print(f"{'='*75}\n")


if __name__ == "__main__":
    idx = sys.argv[1] if len(sys.argv) > 1 else "nifty500"
    run_friction_sweep(idx)
