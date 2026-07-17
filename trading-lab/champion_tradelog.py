"""
champion_tradelog.py — the human-readable diary of the champion strategy
(ensemble + regime-cash) over the survivorship-corrected backtest: what it would
have told you to BUY each month, and exactly WHEN it pulled everything to cash.

Answers the original ask: "which strategy would have told me to buy what, when."

Writes a full month-by-month CSV + prints the highlights (cash periods, sample months).

  python champion_tradelog.py [nifty500|nifty200] [topk]
"""
from __future__ import annotations
import os, sys, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(__file__))
from strategy_tournament import load, indicators, market_regime, rebal_dates, build_W

OUT = os.path.expanduser("~/.vibe-trading/explore")


def main():
    idx = sys.argv[1] if len(sys.argv) > 1 else "nifty500"
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    px, pit, have, ever = load(idx)
    ind = indicators(px)
    regime = market_regime(px)
    reb = rebal_dates(px)

    Wmt = build_W(px, ind, pit, "car", k, True, "equal")
    Wlv = build_W(px, ind, pit, "lowvol", k, False, "equal")
    Wmv = build_W(px, ind, pit, "momvol", k, True, "equal")
    Wens = (Wmt + Wlv + Wmv) / 3.0

    # 1) regime-off intervals (fully in cash)
    offs, prev, start = [], True, None
    for d in px.index:
        on = bool(regime.get(d, True))
        if prev and not on:
            start = d
        if not prev and on:
            offs.append((start.date(), d.date()))
        prev = on
    if not prev and start is not None:
        offs.append((start.date(), px.index[-1].date()))

    # 2) month-by-month holdings
    rows = []
    months_cash = 0
    for t in reb:
        on = bool(regime.get(t, True))
        w = Wens.loc[t]
        held = w[w > 0].sort_values(ascending=False)
        if not on or held.empty:
            months_cash += 1
            rows.append(dict(month=t.date(), state="CASH (risk-off)", n_names=0, holdings=""))
        else:
            holdings = "; ".join(f"{s} {held[s]*100:.1f}%" for s in held.index)
            rows.append(dict(month=t.date(), state="invested", n_names=int((w > 0).sum()),
                             holdings=holdings))
    log = pd.DataFrame(rows)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"champion_tradelog_{idx}.csv")
    log.to_csv(path, index=False)

    # ---- highlights ----
    print(f"\nCHAMPION trade log — ensemble + regime-cash, {idx} point-in-time")
    print(f"({have}/{ever} priced, {px.index.min().date()}..{px.index.max().date()}, "
          f"{len(reb)} monthly decisions)\n")
    print(f"WENT TO CASH (regime risk-off) during {len(offs)} stretch(es) "
          f"— {months_cash}/{len(reb)} months in cash:")
    for a, b in offs:
        print(f"   • {a}  →  {b}")
    print(f"\n(These are the crash-dodges — e.g. COVID 2020, the 2022 drawdown. "
          f"Full month-by-month file: {path})\n")

    def show(label, t):
        r = log[log["month"] == t]
        if r.empty:
            return
        r = r.iloc[0]
        print(f"── {label} ({r['month']}): {r['state']}"
              + (f", {r['n_names']} names" if r['n_names'] else ""))
        if r["holdings"]:
            names = r["holdings"].split("; ")
            print("   " + "  ".join(names[:12]) + (" ..." if len(names) > 12 else ""))

    show("FIRST decision", log.iloc[0]["month"])
    # a month near the COVID crash and the latest
    covid = [t for t in reb if t.year == 2020 and t.month in (3, 4)]
    if covid:
        show("COVID crash", covid[0].date())
    show("MOST RECENT", log.iloc[-1]["month"])
    print(f"\nOpen the CSV to see every month's exact buy-list. Past ≠ future; "
          f"survivorship-corrected but pre-personal-tax in this log.")


if __name__ == "__main__":
    main()
