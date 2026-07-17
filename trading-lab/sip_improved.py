"""
sip_improved.py — is there a SIMILAR-BUT-BETTER version of the plan:
  Rs 1,000/month into a plain Nifty 500 index fund  +  Rs 1,000/month into Nifty 500 Momentum 50?

We test the one upgrade with real evidence — the REGIME overlay (crash-dodge) — applied
to the momentum sleeve of a monthly SIP into FUNDS, with correct fund + retail tax:
  - inside a fund, its own churn is tax-free to you; you pay only when YOU redeem units
  - LTCG 12.5% above Rs 1.25L/yr (so at Rs1k/mo, holding is ~tax-free); STCG 20% (<1yr)

  PLAN A (your plan): SIP plain + SIP momentum, both bought-and-held.
  PLAN B (upgrade):   SIP plain (held) + SIP momentum that SWITCHES to a liquid/cash fund
                      whenever the market is below its 200-day trend (regime risk-off).

Fund NAV proxies come from our survivorship-corrected Nifty 500 point-in-time backtest.
"""
from __future__ import annotations
import os, sys, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(__file__))
from strategy_tournament import load, indicators, market_regime, rebal_dates, build_W

COST, ANN, STCG, LTCG, EXEMPT, AMT = 0.0005, 252, 0.20, 0.125, 125_000, 1000.0


def nav(px, W):
    rets = px.pct_change().clip(-0.35, 0.35).fillna(0)
    Wp = W.shift(1).fillna(0)
    turn = Wp.diff().abs().sum(axis=1).fillna(0)
    r = (Wp * rets).sum(axis=1) - turn * COST
    return (1 + r.fillna(0)).cumprod() * 100.0


def sip_dates(index):
    seen, out = set(), []
    for d in index:
        key = (d.year, d.month)
        if key not in seen:
            seen.add(key); out.append(d)
    return set(out)


def _units(lots):
    return sum(l[0] for l in lots)


def _sell_all(lots, nav_now, d, acc):
    for u, cost, bd in lots:
        gain = u * (nav_now - cost)
        acc["ltcg" if (d - bd).days >= 365 else "stcg"] += gain
    proceeds = _units(lots) * nav_now
    lots.clear()
    return proceeds


def _fy(d):
    return d.year if d.month >= 4 else d.year - 1


def sip_hold(navser, sips):
    """Buy AMT of units each SIP date, hold to the end. Returns (daily_value, lots)."""
    lots, val = [], pd.Series(index=navser.index, dtype=float)
    for d in navser.index:
        if d in sips:
            lots.append([AMT / navser[d], navser[d], d])
        val[d] = _units(lots) * navser[d]
    return val, lots


def sip_regime(navser, regime, sips):
    """SIP into the fund, but sit in cash whenever risk-off. Switches realize gains (taxed
    at fiscal year-end). Returns (daily_value, lots, cash, total_tax_paid)."""
    lots, cash, acc = [], 0.0, {"stcg": 0.0, "ltcg": 0.0}
    total_tax, cur_fy = 0.0, None
    val = pd.Series(index=navser.index, dtype=float)
    for d in navser.index:
        nv = navser[d]
        if cur_fy is None:
            cur_fy = _fy(d)
        if _fy(d) != cur_fy:                                   # settle tax for the year
            tax = STCG * max(acc["stcg"], 0) + LTCG * max(acc["ltcg"] - EXEMPT, 0)
            if tax > 0:
                if cash < tax and lots:                        # sell units to fund the tax
                    need = (tax - cash)
                    sell_u = min(_units(lots), need / nv)
                    # FIFO
                    rem = sell_u
                    while rem > 1e-12 and lots:
                        u, cost, bd = lots[0]
                        take = min(u, rem)
                        acc["ltcg" if (d - bd).days >= 365 else "stcg"] += take * (nv - cost)
                        cash += take * nv; lots[0][0] -= take; rem -= take
                        if lots[0][0] <= 1e-12:
                            lots.pop(0)
                cash -= tax; total_tax += tax
            acc = {"stcg": 0.0, "ltcg": 0.0}; cur_fy = _fy(d)

        on = bool(regime.get(d, True))
        if not on and lots:                                    # risk-off -> liquidate to cash
            cash += _sell_all(lots, nv, d, acc)
        elif on and cash > 0:                                  # risk-on -> deploy cash
            lots.append([cash / nv, nv, d]); cash = 0.0

        if d in sips:                                          # monthly contribution
            if on:
                lots.append([AMT / nv, nv, d])
            else:
                cash += AMT

        val[d] = _units(lots) * nv + cash
    return val, lots, cash, total_tax


def redeem_after_tax(lots, cash, nav_last, d_last):
    """Final redemption tax (with the yearly LTCG exemption applied once at the end)."""
    acc = {"stcg": 0.0, "ltcg": 0.0}
    proceeds = cash + _sell_all(lots, nav_last, d_last, acc)
    tax = STCG * max(acc["stcg"], 0) + LTCG * max(acc["ltcg"] - EXEMPT, 0)
    return proceeds - tax


def maxdd(series):
    return float((series / series.cummax() - 1).min())


def main():
    px, pit, have, ever = load("nifty500")
    ind = indicators(px)
    regime = market_regime(px)

    nav_plain = nav(px, build_W(px, ind, pit, "buyhold", 20, False, "equal"))      # ~Nifty 500 index
    nav_mom = nav(px, build_W(px, ind, pit, "car", 50, False, "equal"))            # ~Momentum 50 (fully invested)
    sips = sip_dates(px.index)
    n_months = len(sips)
    invested_each = AMT * n_months

    # sleeves
    vp, lots_p = sip_hold(nav_plain, sips)                          # plain, held (both plans)
    vA, lots_mA = sip_hold(nav_mom, sips)                           # PLAN A momentum: held
    vB, lots_mB, cashB, taxB_mid = sip_regime(nav_mom, regime, sips)  # PLAN B momentum: regime-switched

    # combined daily portfolio value
    portA = (vp + vA).dropna()
    portB = (vp + vB).dropna()
    last, dlast = px.index[-1], px.index[-1]

    # after-tax terminal value (redeem everything)
    finA = redeem_after_tax(list(lots_p), 0.0, nav_plain[last], dlast) + \
           redeem_after_tax(list(lots_mA), 0.0, nav_mom[last], dlast)
    finB = redeem_after_tax(list(lots_p), 0.0, nav_plain[last], dlast) + \
           redeem_after_tax(list(lots_mB), cashB, nav_mom[last], dlast) - taxB_mid

    tot_invested = 2 * invested_each
    print(f"\nYOUR SIP PLAN vs an evidence-based upgrade — Nifty 500 funds, "
          f"{px.index.min().date()}..{last.date()}")
    print(f"Rs {AMT:,.0f}/mo into EACH of (plain index + momentum-50), {n_months} months, "
          f"Rs {tot_invested:,.0f} total in.\n")
    print(f"{'plan':44}{'after-tax final':>17}{'x money':>9}{'worst drop':>12}")
    print("-" * 82)
    print(f"{'A) your plan: plain + momentum, both HELD':44}"
          f"{finA:>16,.0f}{finA/tot_invested:>8.2f}x{maxdd(portA):>11.0%}")
    print(f"{'B) upgrade: plain HELD + momentum REGIME-switched':44}"
          f"{finB:>16,.0f}{finB/tot_invested:>8.2f}x{maxdd(portB):>11.0%}")
    print(f"\nPlan B mid-way switching tax paid: Rs {taxB_mid:,.0f} "
          f"(STCG from regime exits — the cost of the crash-dodge).")
    print("Note: fund NAV proxies from survivorship-corrected backtest; a strong era; past != future.")


if __name__ == "__main__":
    main()
