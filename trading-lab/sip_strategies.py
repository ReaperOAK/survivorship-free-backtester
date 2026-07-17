"""
sip_strategies.py — bake-off of ways to run the SAME Rs 2,000/month budget
(the user's plan = Rs1k plain Nifty500 index + Rs1k Nifty500 Momentum50):

  A) BASELINE      — Rs1k plain + Rs1k momentum, both bought-and-held
  B) REGIME-SWITCH — plain held; momentum switches to cash when market < 200-day trend
  C) ANNUAL REBAL  — both held, rebalanced back to 50/50 once a year (harvest the rebal bonus)
  D) DRAWDOWN-TILT — normal Rs1k/Rs1k, BUT when market is >10% off its peak, put the whole
                     Rs2k into momentum that month (buy the dip harder in the rebound sleeve)
  E) CRASH-RESERVE — invest Rs1.5k/mo, stash Rs0.5k/mo in a liquid fund (earns ~6%/yr),
                     dump the reserve into momentum when the market falls >15% from its peak
                     (the user's "lump sum during a crash" idea, done right)

All after-tax (fund churn is tax-free to you; you pay only on YOUR redemptions/switches:
LTCG 12.5% over Rs1.25L exemption, STCG 20%). Same Rs2k/mo committed in every plan.
NAV proxies from the survivorship-corrected Nifty 500 point-in-time backtest.
"""
from __future__ import annotations
import os, sys, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(__file__))
from strategy_tournament import load, indicators, market_regime, build_W

COST, ANN, STCG, LTCG, EXEMPT = 0.0005, 252, 0.20, 0.125, 125_000
LIQ_DAILY = (1 + 0.06) ** (1 / ANN) - 1        # reserve parked in a ~6%/yr liquid fund


def nav(px, W):
    rets = px.pct_change().clip(-0.35, 0.35).fillna(0)
    Wp = W.shift(1).fillna(0)
    turn = Wp.diff().abs().sum(axis=1).fillna(0)
    r = (Wp * rets).sum(axis=1) - turn * COST
    return (1 + r.fillna(0)).cumprod() * 100.0


class Sleeve:
    def __init__(self): self.lots = []          # [units, cost_nav, buy_date]
    def buy(self, rupees, nv, d):
        if rupees > 1e-9: self.lots.append([rupees / nv, nv, d])
    def units(self): return sum(l[0] for l in self.lots)
    def value(self, nv): return self.units() * nv
    def sell_value(self, rupees, nv, d, acc):
        rem, proceeds = min(self.units(), rupees / nv), 0.0
        target = rem
        while target > 1e-12 and self.lots:
            u, cost, bd = self.lots[0]
            take = min(u, target)
            acc["ltcg" if (d - bd).days >= 365 else "stcg"] += take * (nv - cost)
            proceeds += take * nv; self.lots[0][0] -= take; target -= take
            if self.lots[0][0] <= 1e-12: self.lots.pop(0)
        return proceeds
    def sell_all(self, nv, d, acc): return self.sell_value(self.units() * nv + 1, nv, d, acc)


def after_tax(gross, acc):
    # conservative: apply the Rs1.25L LTCG exemption ONCE (real investors get it yearly -> real tax <= this)
    tax = STCG * max(acc["stcg"], 0) + LTCG * max(acc["ltcg"] - EXEMPT, 0)
    return gross - tax, tax


def run(px, nav_plain, nav_mom, regime, mdd, sips, years_first):
    idx = px.index
    last = idx[-1]
    plans = {}

    def finish(P, M, val, extra_cash, acc):
        gross = P.sell_all(nav_plain[last], last, acc) + M.sell_all(nav_mom[last], last, acc) + extra_cash
        net, tax = after_tax(gross, acc)
        dd = float((val / val.cummax() - 1).min())
        return dict(net=net, dd=dd, tax=tax)

    # A) baseline
    P, M, acc, val = Sleeve(), Sleeve(), {"stcg": 0, "ltcg": 0}, pd.Series(index=idx, dtype=float)
    for d in idx:
        if d in sips: P.buy(1000, nav_plain[d], d); M.buy(1000, nav_mom[d], d)
        val[d] = P.value(nav_plain[d]) + M.value(nav_mom[d])
    plans["A) baseline (both held)"] = finish(P, M, val, 0.0, acc)

    # B) regime-switch momentum
    P, M, acc, val, cashM = Sleeve(), Sleeve(), {"stcg": 0, "ltcg": 0}, pd.Series(index=idx, dtype=float), 0.0
    for d in idx:
        on = bool(regime.get(d, True))
        if not on and M.units() > 0: cashM += M.sell_all(nav_mom[d], d, acc)
        elif on and cashM > 0: M.buy(cashM, nav_mom[d], d); cashM = 0.0
        if d in sips:
            P.buy(1000, nav_plain[d], d)
            if on: M.buy(1000, nav_mom[d], d)
            else: cashM += 1000
        val[d] = P.value(nav_plain[d]) + M.value(nav_mom[d]) + cashM
    plans["B) regime-switch momentum"] = finish(P, M, val, cashM, acc)

    # C) annual rebalance to 50/50
    P, M, acc, val = Sleeve(), Sleeve(), {"stcg": 0, "ltcg": 0}, pd.Series(index=idx, dtype=float)
    done_year = set()
    for d in idx:
        if d in sips: P.buy(1000, nav_plain[d], d); M.buy(1000, nav_mom[d], d)
        if d in sips and d.year not in done_year and d.year > years_first:
            vp, vm = P.value(nav_plain[d]), M.value(nav_mom[d]); tgt = (vp + vm) / 2
            if vp > tgt + 1: M.buy(P.sell_value(vp - tgt, nav_plain[d], d, acc), nav_mom[d], d)
            elif vm > tgt + 1: P.buy(M.sell_value(vm - tgt, nav_mom[d], d, acc), nav_plain[d], d)
            done_year.add(d.year)
        val[d] = P.value(nav_plain[d]) + M.value(nav_mom[d])
    plans["C) annual rebalance 50/50"] = finish(P, M, val, 0.0, acc)

    # D) drawdown-tilt new money into momentum
    P, M, acc, val = Sleeve(), Sleeve(), {"stcg": 0, "ltcg": 0}, pd.Series(index=idx, dtype=float)
    for d in idx:
        if d in sips:
            if mdd[d] <= -0.10: M.buy(2000, nav_mom[d], d)
            else: P.buy(1000, nav_plain[d], d); M.buy(1000, nav_mom[d], d)
        val[d] = P.value(nav_plain[d]) + M.value(nav_mom[d])
    plans["D) drawdown-tilt to momentum"] = finish(P, M, val, 0.0, acc)

    # E) crash-reserve (the user's lump-sum-on-crash idea)
    P, M, acc, val, reserve, armed = Sleeve(), Sleeve(), {"stcg": 0, "ltcg": 0}, pd.Series(index=idx, dtype=float), 0.0, True
    for d in idx:
        reserve *= (1 + LIQ_DAILY)                       # reserve earns liquid-fund interest
        if d in sips: P.buy(750, nav_plain[d], d); M.buy(750, nav_mom[d], d); reserve += 500
        if mdd[d] <= -0.15 and armed and reserve > 0:    # deep crash -> deploy the stack
            M.buy(reserve, nav_mom[d], d); reserve = 0.0; armed = False
        if mdd[d] > -0.05: armed = True                  # re-arm after recovery
        val[d] = P.value(nav_plain[d]) + M.value(nav_mom[d]) + reserve
    plans["E) crash-reserve -> momentum"] = finish(P, M, val, reserve, acc)
    return plans


def main():
    px, pit, have, ever = load("nifty500")
    ind = indicators(px)
    regime = market_regime(px)
    nav_plain = nav(px, build_W(px, ind, pit, "buyhold", 20, False, "equal"))
    nav_mom = nav(px, build_W(px, ind, pit, "car", 50, False, "equal"))
    mdd = nav_plain / nav_plain.cummax() - 1                       # market drawdown from peak

    seen, sips = set(), set()
    for d in px.index:
        k = (d.year, d.month)
        if k not in seen: seen.add(k); sips.add(d)
    n_months = len(sips)
    invested = 2000.0 * n_months
    years_first = px.index[0].year

    plans = run(px, nav_plain, nav_mom, regime, mdd, sips, years_first)

    print(f"\nSIP STRATEGY BAKE-OFF — Nifty 500 funds, {px.index.min().date()}..{px.index.max().date()}")
    print(f"Rs 2,000/mo total ({n_months} months, Rs {invested:,.0f} in). All after-tax.\n")
    print(f"{'plan':34}{'after-tax final':>16}{'x money':>9}{'worst drop':>12}{'tax':>9}")
    print("-" * 80)
    base = plans["A) baseline (both held)"]["net"]
    for name, s in sorted(plans.items(), key=lambda kv: kv[1]["net"], reverse=True):
        flag = "  <<" if s["net"] == max(p["net"] for p in plans.values()) else ""
        print(f"{name:34}{s['net']:>15,.0f}{s['net']/invested:>8.2f}x{s['dd']:>11.0%}{s['tax']:>9,.0f}{flag}")
    print(f"\nvs baseline A: " + ", ".join(
        f"{n.split(')')[0]} {(s['net']/base-1)*100:+.1f}%" for n, s in plans.items() if not n.startswith('A')))
    print("Conservative tax (Rs1.25L exemption applied once). Strong era 2017-26; past != future.")


if __name__ == "__main__":
    main()
