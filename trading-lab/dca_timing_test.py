"""
dca_timing_test.py — does the YouTube "buy only on RED days" trick actually beat a
plain SIP? Settle it with data instead of vibes.

Three ways to deploy the SAME total budget (Rs 1/trading-day) into a fund:
  A) MONTHLY SIP  — accrue Rs1/day, invest the lump on the 1st trading day of each month
  B) DAILY DCA    — invest Rs1 every single trading day
  C) RED-DAY DCA  — the video's trick: accrue Rs1/day; invest the whole stack ONLY on a
                    red (down) day; on green days hold and let it pile up
All three ALLOCATE the same Rs N (leftover un-deployed cash is counted at face value),
so final total value is an apples-to-apples comparison.

Runs on (1) a real momentum-30 fund NAV and (2) a 20-yr store proxy spanning real crashes.
"""
from __future__ import annotations
import os, warnings
import numpy as np
import pandas as pd
import duckdb
import httpx

warnings.filterwarnings("ignore")
DB = os.path.expanduser("~/.vibe-trading/market.duckdb")


def run_methods(prices: pd.Series):
    """prices: daily price/NAV series (ascending date index). Returns a stats dict per method."""
    prices = prices.dropna()
    px = prices.values
    red = np.r_[False, px[1:] < px[:-1]]          # today < yesterday
    n = len(px)
    final_px = px[-1]
    out = {}

    # A) monthly SIP: invest accrued budget on first trading day of each new month
    units = cash = 0.0; pend = 0.0; last_m = None
    for i, d in enumerate(prices.index):
        pend += 1.0
        m = (d.year, d.month)
        if m != last_m:
            units += pend / px[i]; pend = 0.0; last_m = m
    cash = pend
    out["MONTHLY SIP"] = (units, cash, n)

    # B) daily DCA: invest Rs1 every day
    units = np.sum(1.0 / px)
    out["DAILY DCA"] = (units, 0.0, n)

    # C) red-day DCA: accrue Rs1/day, deploy the stack only on red days
    units = 0.0; pend = 0.0
    for i in range(n):
        pend += 1.0
        if red[i]:
            units += pend / px[i]; pend = 0.0
    cash = pend                                    # leftover never hit a red day
    out["RED-DAY DCA (the trick)"] = (units, cash, n)

    rows = {}
    for name, (units, cash, alloc) in out.items():
        val = units * final_px + cash
        rows[name] = dict(final=val, invested=alloc, mult=val / alloc,
                          avg_cost=(alloc - cash) / units if units else np.nan,
                          deployed_pct=(alloc - cash) / alloc)
    return rows


def show(title, prices):
    r = run_methods(prices)
    base = r["DAILY DCA"]["final"]
    print(f"\n{title}  ({prices.index.min().date()}..{prices.index.max().date()}, "
          f"{len(prices)} days, final px {prices.iloc[-1]:.2f})")
    print(f"{'method':26}{'final/1rs':>11}{'x vs daily':>12}{'avg cost':>11}{'deployed':>10}")
    print("-" * 70)
    for name in ["MONTHLY SIP", "DAILY DCA", "RED-DAY DCA (the trick)"]:
        s = r[name]
        print(f"{name:26}{s['final']/s['invested']:>10.3f}x{(s['final']/base-1)*100:>+10.2f}%"
              f"{s['avg_cost']:>11.2f}{s['deployed_pct']:>9.0%}")


def kotak_momentum30():
    d = httpx.get("https://api.mfapi.in/mf/151781", timeout=30).json()      # Kotak Nifty200 Momentum30
    df = pd.DataFrame(d["data"])
    df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y")
    df["nav"] = df["nav"].astype(float)
    return df.sort_values("date").set_index("date")["nav"]


def store_proxy():
    con = duckdb.connect(DB, read_only=True)
    basket = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'ITC', 'HINDUNILVR', 'SBIN',
              'LT', 'AXISBANK', 'KOTAKBANK', 'BHARTIARTL', 'ASIANPAINT', 'MARUTI', 'SUNPHARMA',
              'WIPRO', 'ONGC', 'NTPC', 'TITAN', 'NESTLEIND']
    ph = ",".join(["?"] * len(basket))
    df = con.execute(f"SELECT date,symbol,close FROM prices WHERE symbol IN ({ph}) "
                     f"AND date>='2006-01-01' ORDER BY date", basket).df()
    con.close()
    wide = df.pivot(index="date", columns="symbol", values="close")
    wide.index = pd.to_datetime(wide.index)
    proxy = (1 + wide.pct_change().mean(axis=1).fillna(0)).cumprod() * 100    # equal-wt broad proxy
    return proxy


def main():
    print("=" * 70)
    print("Does 'invest only on RED days' beat a plain SIP?  (same total budget)")
    print("=" * 70)
    try:
        show("REAL FUND — Kotak Nifty 200 Momentum 30", kotak_momentum30())
    except Exception as e:
        print(f"(fund fetch failed: {e})")
    show("20-YR BROAD PROXY (our store — spans 2008/2020/2022 crashes)", store_proxy())
    print("\nx vs daily = how much better/worse than plain daily DCA. avg cost = avg price paid/unit.")
    print("Verdict printed by the numbers, not by a YouTuber.")


if __name__ == "__main__":
    main()
