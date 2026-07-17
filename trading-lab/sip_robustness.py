"""
sip_robustness.py — two honesty checks on the Plan-D "buy-the-dip-with-new-money" winner:

  PART 1  Threshold sweep: does Plan D's edge survive at -5% / -10% / -15% / -20% dip
          triggers, or was -10% a lucky cutoff? (robust edge = wins at ALL thresholds)

  PART 2  "Best of both": can we keep D's return boost AND add regime crash-protection?
          A  baseline (both held)
          D  drawdown-tilt new money -> momentum (the returns winner)
          B  regime-switch momentum (the safety winner)
          F1 PROTECT + DIP: regime-switch the existing momentum pile to cash on risk-off,
             but still funnel new dip-money toward momentum (deploy when risk-on)
          F3 GATED DIP: only do the dip-tilt when the market is down >X% AND still in
             its uptrend (buy confirmed pullbacks, don't catch falling knives) — no selling

All Rs 2,000/mo, after-tax, Nifty 500 fund proxies (survivorship-corrected).
"""
from __future__ import annotations
import os, sys, warnings
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(__file__))
from strategy_tournament import load, indicators, market_regime, build_W
from sip_strategies import Sleeve, nav, after_tax


def finish(P, M, val, extra_cash, nav_plain, nav_mom, last, acc):
    gross = P.sell_all(nav_plain[last], last, acc) + M.sell_all(nav_mom[last], last, acc) + extra_cash
    net, tax = after_tax(gross, acc)
    return dict(net=net, dd=float((val / val.cummax() - 1).min()), tax=tax)


def plan_baseline(ctx):
    P, M, acc, val = Sleeve(), Sleeve(), {"stcg": 0, "ltcg": 0}, pd.Series(index=ctx["idx"], dtype=float)
    for d in ctx["idx"]:
        if d in ctx["sips"]:
            P.buy(1000, ctx["np"][d], d); M.buy(1000, ctx["nm"][d], d)
        val[d] = P.value(ctx["np"][d]) + M.value(ctx["nm"][d])
    return finish(P, M, val, 0.0, ctx["np"], ctx["nm"], ctx["last"], acc)


def plan_D(ctx, thr):
    P, M, acc, val = Sleeve(), Sleeve(), {"stcg": 0, "ltcg": 0}, pd.Series(index=ctx["idx"], dtype=float)
    for d in ctx["idx"]:
        if d in ctx["sips"]:
            if ctx["mdd"][d] <= thr:
                M.buy(2000, ctx["nm"][d], d)
            else:
                P.buy(1000, ctx["np"][d], d); M.buy(1000, ctx["nm"][d], d)
        val[d] = P.value(ctx["np"][d]) + M.value(ctx["nm"][d])
    return finish(P, M, val, 0.0, ctx["np"], ctx["nm"], ctx["last"], acc)


def plan_B(ctx):
    P, M, acc = Sleeve(), Sleeve(), {"stcg": 0, "ltcg": 0}
    val, cashM = pd.Series(index=ctx["idx"], dtype=float), 0.0
    for d in ctx["idx"]:
        on = bool(ctx["reg"].get(d, True))
        if not on and M.units() > 0: cashM += M.sell_all(ctx["nm"][d], d, acc)
        elif on and cashM > 0: M.buy(cashM, ctx["nm"][d], d); cashM = 0.0
        if d in ctx["sips"]:
            P.buy(1000, ctx["np"][d], d)
            if on: M.buy(1000, ctx["nm"][d], d)
            else: cashM += 1000
        val[d] = P.value(ctx["np"][d]) + M.value(ctx["nm"][d]) + cashM
    return finish(P, M, val, cashM, ctx["np"], ctx["nm"], ctx["last"], acc)


def plan_F1(ctx, thr=-0.10):
    """Protect the pile (regime-switch existing momentum to cash) + still funnel dip-money to momentum."""
    P, M, acc = Sleeve(), Sleeve(), {"stcg": 0, "ltcg": 0}
    val, cashM = pd.Series(index=ctx["idx"], dtype=float), 0.0
    for d in ctx["idx"]:
        on = bool(ctx["reg"].get(d, True))
        if not on and M.units() > 0: cashM += M.sell_all(ctx["nm"][d], d, acc)
        elif on and cashM > 0: M.buy(cashM, ctx["nm"][d], d); cashM = 0.0
        if d in ctx["sips"]:
            dip = ctx["mdd"][d] <= thr
            if dip:                                  # dip: all Rs2k toward momentum
                if on: M.buy(2000, ctx["nm"][d], d)
                else: cashM += 2000                  # risk-off: park, deploy when risk-on
            else:
                P.buy(1000, ctx["np"][d], d)
                if on: M.buy(1000, ctx["nm"][d], d)
                else: cashM += 1000
        val[d] = P.value(ctx["np"][d]) + M.value(ctx["nm"][d]) + cashM
    return finish(P, M, val, cashM, ctx["np"], ctx["nm"], ctx["last"], acc)


def plan_F3(ctx, thr=-0.10):
    """Gated dip: tilt to momentum only when down >thr AND still in uptrend (no selling)."""
    P, M, acc, val = Sleeve(), Sleeve(), {"stcg": 0, "ltcg": 0}, pd.Series(index=ctx["idx"], dtype=float)
    for d in ctx["idx"]:
        on = bool(ctx["reg"].get(d, True))
        if d in ctx["sips"]:
            if ctx["mdd"][d] <= thr and on:
                M.buy(2000, ctx["nm"][d], d)
            else:
                P.buy(1000, ctx["np"][d], d); M.buy(1000, ctx["nm"][d], d)
        val[d] = P.value(ctx["np"][d]) + M.value(ctx["nm"][d])
    return finish(P, M, val, 0.0, ctx["np"], ctx["nm"], ctx["last"], acc)


def main():
    px, pit, have, ever = load("nifty500")
    ind = indicators(px)
    reg = market_regime(px)
    np_ = nav(px, build_W(px, ind, pit, "buyhold", 20, False, "equal"))
    nm = nav(px, build_W(px, ind, pit, "car", 50, False, "equal"))
    mdd = np_ / np_.cummax() - 1
    seen, sips = set(), set()
    for d in px.index:
        k = (d.year, d.month)
        if k not in seen: seen.add(k); sips.add(d)
    invested = 2000.0 * len(sips)
    ctx = dict(idx=px.index, last=px.index[-1], sips=sips, np=np_, nm=nm, mdd=mdd, reg=reg)

    base = plan_baseline(ctx)["net"]
    print(f"\nSIP ROBUSTNESS — Nifty 500 funds, {px.index.min().date()}..{px.index.max().date()}, "
          f"Rs2k/mo, Rs {invested:,.0f} in, after-tax\n")

    print("PART 1 — Plan D 'buy-the-dip' at different triggers (is -10% a fluke?)")
    print(f"{'dip trigger':16}{'after-tax final':>17}{'x money':>9}{'worst drop':>12}{'vs baseline':>13}")
    print("-" * 67)
    for thr in (-0.05, -0.10, -0.15, -0.20):
        s = plan_D(ctx, thr)
        print(f"{f'market <= {thr:.0%}':16}{s['net']:>16,.0f}{s['net']/invested:>8.2f}x"
              f"{s['dd']:>11.0%}{(s['net']/base-1)*100:>+11.1f}%")
    print(f"{'baseline (no tilt)':16}{base:>16,.0f}{base/invested:>8.2f}x{plan_baseline(ctx)['dd']:>11.0%}{'—':>13}")

    print("\nPART 2 — best of both: dip-buying (returns) + regime (safety)")
    print(f"{'plan':40}{'after-tax final':>16}{'x':>7}{'worst drop':>12}{'vs base':>10}")
    print("-" * 85)
    plans = {
        "A) baseline (both held)": plan_baseline(ctx),
        "D) dip-tilt -10% (returns winner)": plan_D(ctx, -0.10),
        "B) regime-switch (safety winner)": plan_B(ctx),
        "F1) protect pile + dip-buy new money": plan_F1(ctx, -0.10),
        "F3) gated dip (dip + in uptrend only)": plan_F3(ctx, -0.10),
    }
    best = max(p["net"] for p in plans.values())
    for name, s in plans.items():
        flag = "  <<" if s["net"] == best else ""
        print(f"{name:40}{s['net']:>15,.0f}{s['net']/invested:>7.2f}x{s['dd']:>11.0%}"
              f"{(s['net']/base-1)*100:>+9.1f}%{flag}")
    print("\nStrong era 2017-26; conservative tax; NAV proxies. Past != future.")


if __name__ == "__main__":
    main()
