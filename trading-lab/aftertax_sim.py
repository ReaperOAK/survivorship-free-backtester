"""
aftertax_sim.py — the number that actually lands in your pocket.

Lot-level (FIFO) portfolio simulator that charges REAL Indian equity tax:
  - Short-term capital gains (held < 12 months): 20%
  - Long-term  capital gains (held >= 12 months): 12.5% above a Rs 1.25L/yr exemption
  - trading cost 0.05% per traded value
Tax is settled each fiscal year-end (Mar 31), paid from the portfolio (so it stops
compounding) — exactly what a real taxable account in India experiences.

We compare the tournament's contenders PRE-tax vs AFTER-tax to see if the high-turnover
"champion" survives the taxman, or whether tax-efficient buy&hold closes the gap.

  python aftertax_sim.py [nifty500|nifty200] [topk]
"""
from __future__ import annotations
import os, sys, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(__file__))
from strategy_tournament import (load, indicators, market_regime, rebal_dates,
                                 build_W, ANN)

COST, STCG, LTCG, LTCG_EXEMPT = 0.0005, 0.20, 0.125, 125_000
CAP0 = 1_000_000.0     # notional Rs 10L (above min-balance; tax drag is ~scale-free)


def fifo_sell(lots, sell_sh, price, date, acc):
    """Sell sell_sh shares FIFO from a symbol's lots; accrue realized gain by tenure."""
    remaining, proceeds = sell_sh, 0.0
    while remaining > 1e-9 and lots:
        sh, entry_px, entry_dt = lots[0]
        take = min(sh, remaining)
        gain = take * (price - entry_px)
        if (date - entry_dt).days >= 365:
            acc["ltcg"] += gain
        else:
            acc["stcg"] += gain
        proceeds += take * price
        lots[0][0] -= take
        remaining -= take
        if lots[0][0] <= 1e-9:
            lots.pop(0)
    return proceeds


def raise_cash(cash, positions, px_row, need, acc):
    """Sell holdings pro-rata (by value) to raise `need` rupees (e.g. to pay tax)."""
    if cash >= need:
        return cash
    holdings = {s: sum(l[0] for l in lots) * px_row[s]
                for s, lots in positions.items() if s in px_row and pd.notna(px_row[s])}
    tot = sum(v for v in holdings.values() if v > 0)
    if tot <= 0:
        return cash
    want = (need - cash) / (1 - COST)
    for s, val in holdings.items():
        if val <= 0:
            continue
        sell_val = min(val, want * val / tot)
        price = px_row[s]
        proceeds = fifo_sell(positions[s], sell_val / price, price, px_row.name, acc)
        cash += proceeds * (1 - COST)
        if not positions[s]:
            positions.pop(s, None)
    return cash


def _pv(positions, row):
    return sum(sum(l[0] for l in lots) * row[s]
               for s, lots in positions.items() if pd.notna(row.get(s)))


def _rebalance_to(positions, cash, row, tw, acc, traded, d):
    """Trade current holdings toward target weights `tw` (a Series). Returns new cash."""
    equity = cash + _pv(positions, row)
    for s in list(positions):                          # SELL side first (free up cash)
        if s not in row or pd.isna(row[s]):
            continue
        price = row[s]
        cur_val = sum(l[0] for l in positions[s]) * price
        tgt_val = float(tw.get(s, 0.0)) * equity
        if tgt_val < cur_val - 1e-6:
            proceeds = fifo_sell(positions[s], (cur_val - tgt_val) / price, price, d, acc)
            cash += proceeds * (1 - COST)
            traded[0] += (cur_val - tgt_val)
            if not positions[s]:
                positions.pop(s, None)
    for s in tw[tw > 0].index:                         # BUY side
        if s not in row or pd.isna(row[s]):
            continue
        price = row[s]
        cur_val = sum(l[0] for l in positions.get(s, [])) * price
        tgt_val = float(tw[s]) * equity
        if tgt_val > cur_val + 1e-6:
            buy_val = min(tgt_val - cur_val, cash / (1 + COST))
            if buy_val > 1e-6:
                positions.setdefault(s, []).append([buy_val / price, price, d])
                cash -= buy_val * (1 + COST)
                traded[0] += buy_val
    return cash


def simulate(px, W, taxed=True, regime=None):
    """Event-driven FIFO lot sim. If `regime` (daily bool Series) is given, liquidate
    to cash the day it turns risk-OFF and re-enter the last monthly target when risk-ON
    (a realistic daily stop-rule) — every liquidation realizes gains (taxed).
    Returns (equity_curve, total_tax, oneway_turnover_frac)."""
    pxf = px.ffill()
    reb = set(rebal_dates(px))
    cols = px.columns
    cash, positions = CAP0, {}
    acc = {"stcg": 0.0, "ltcg": 0.0}
    total_tax, traded = 0.0, [0.0]
    eq = pd.Series(index=px.index, dtype=float)
    fy = lambda d: d.year if d.month >= 4 else d.year - 1
    cur_fy, last_w, risk_off = None, pd.Series(0.0, index=cols), False
    zeros = pd.Series(0.0, index=cols)

    for d in px.index:
        row = pxf.loc[d]
        if cur_fy is None:
            cur_fy = fy(d)
        if fy(d) != cur_fy:                            # fiscal year-end -> settle tax from portfolio
            if taxed:
                tax = STCG * max(acc["stcg"], 0) + LTCG * max(acc["ltcg"] - LTCG_EXEMPT, 0)
                if tax > 0:
                    cash = raise_cash(cash, positions, row, tax, acc)
                    cash -= tax
                    total_tax += tax
            acc = {"stcg": 0.0, "ltcg": 0.0}
            cur_fy = fy(d)

        if regime is not None:                         # daily regime stop-rule
            on = bool(regime.get(d, True))
            if not on and not risk_off:
                cash = _rebalance_to(positions, cash, row, zeros, acc, traded, d)   # liquidate
                risk_off = True
            elif on and risk_off:
                risk_off = False
                cash = _rebalance_to(positions, cash, row, last_w, acc, traded, d)  # re-enter

        if d in reb:
            last_w = W.loc[d]
            if not risk_off:
                cash = _rebalance_to(positions, cash, row, last_w, acc, traded, d)

        eq[d] = cash + _pv(positions, row)

    yrs = len(eq) / ANN
    return eq.dropna(), total_tax, (traded[0] / 2) / CAP0 / yrs


def curve_stats(eq):
    r = eq.pct_change().dropna(); yrs = len(r) / ANN
    return dict(cagr=(eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1,
                sharpe=r.mean() / r.std() * np.sqrt(ANN),
                maxdd=(eq / eq.cummax() - 1).min())


def main():
    idx = sys.argv[1] if len(sys.argv) > 1 else "nifty500"
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    px, pit, have, ever = load(idx)
    ind = indicators(px)
    regime = market_regime(px)
    reb = rebal_dates(px)
    regime_at = {t: bool(regime.get(t, True)) for t in reb}

    # contender weight matrices
    Wbh = build_W(px, ind, pit, "buyhold", k, False, "equal")
    Wmt = build_W(px, ind, pit, "car", k, True, "equal")
    Wlv = build_W(px, ind, pit, "lowvol", k, False, "equal")
    Wmv = build_W(px, ind, pit, "momvol", k, True, "equal")
    Wens = (Wmt + Wlv + Wmv) / 3.0

    # (label, weight-matrix, daily-regime-or-None)
    strategies = [("buy&hold", Wbh, None), ("mom+trend k%d" % k, Wmt, None),
                  ("ENSEMBLE", Wens, None), ("ENSEMBLE + regime-cash", Wens, regime)]

    print(f"\nAFTER-TAX reality — {idx} point-in-time ({have}/{ever} priced), "
          f"{px.index.min().date()}..{px.index.max().date()}")
    print(f"Indian equity tax: STCG {STCG:.0%} (<1yr), LTCG {LTCG:.1%} (>1yr, >Rs1.25L/yr). "
          f"Notional Rs {CAP0/1e5:.0f}L. Regime = daily stop-rule.\n")
    hdr = f"{'strategy':24}{'PRE Sharpe':>11}{'PRE CAGR':>10}{'  |':>4}{'NET Sharpe':>11}{'NET CAGR':>10}{'tax drag':>10}{'turn/yr':>9}"
    print(hdr); print("-" * len(hdr))
    rows = []
    for name, W, reg in strategies:
        eq_pre, _, turn = simulate(px, W, taxed=False, regime=reg)
        eq_net, tax, _ = simulate(px, W, taxed=True, regime=reg)
        sp, sn = curve_stats(eq_pre), curve_stats(eq_net)
        drag = sp["cagr"] - sn["cagr"]
        rows.append((name, sn["sharpe"], sn["cagr"]))
        print(f"{name:24}{sp['sharpe']:>11.2f}{sp['cagr']:>9.1%}{'  |':>4}"
              f"{sn['sharpe']:>11.2f}{sn['cagr']:>9.1%}{drag*100:>8.1f}pp{turn:>9.0%}")
    best = max(rows, key=lambda r: r[1])
    print(f"\nAFTER-TAX winner (by Sharpe): {best[0]} — net Sharpe {best[1]:.2f}, net CAGR {best[2]:.1%}")
    print("Note: LTCG Rs1.25L/yr exemption favors low-turnover buy&hold. Past != future.")


if __name__ == "__main__":
    main()
