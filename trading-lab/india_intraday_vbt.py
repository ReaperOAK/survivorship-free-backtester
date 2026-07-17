"""
india_intraday_vbt.py — intraday on Indian stocks, tested in vectorbt with
REAL Indian costs. Settles the intraday question with the proper engine.

Hourly bars (RELIANCE, HDFCBANK, Nifty). Three intraday strategies. Three cost
levels via vectorbt's from_signals:
  1) GROSS            — no costs (the fantasy)
  2) %-only (0.05%)   — STT + exchange/GST/SEBI, IGNORING brokerage
  3) REAL small acct  — the above PLUS Rs 20 flat brokerage PER ORDER on a
                        Rs 10,000 account (fixed_fees=20) — the actual killer.
"""
from __future__ import annotations
import os, glob, warnings
import numpy as np
import pandas as pd
import vectorbt as vbt

warnings.filterwarnings("ignore")
CACHE = os.path.expanduser("~/.vibe-trading/intraday_cache")
INIT = 10000


def rsi(s, n):
    d = s.diff(); up = d.clip(lower=0).rolling(n).mean(); dn = (-d.clip(upper=0)).rolling(n).mean()
    return 100 - 100/(1 + up/dn.replace(0, np.nan))


def signals(c):
    out = {}
    out["mom_ema12"] = (c > c.ewm(span=12).mean())
    hi = c.rolling(24).max(); lo = c.rolling(24).min()
    br = pd.Series(np.nan, index=c.index); br[c >= hi] = 1; br[c <= lo] = 0
    out["breakout24"] = br.ffill().fillna(0).astype(bool)
    r = rsi(c, 6); mr = pd.Series(np.nan, index=c.index); mr[r < 25] = 1; mr[r > 60] = 0
    out["rsi_meanrev"] = mr.ffill().fillna(0).astype(bool)
    return out


def run(close, entries, exits, fees, fixed):
    pf = vbt.Portfolio.from_signals(close, entries, exits, init_cash=INIT,
                                    fees=fees, fixed_fees=fixed, freq="1H")
    return float(pf.total_return()) * 100, float(pf.sharpe_ratio()), int(pf.trades.count())


def main():
    files = sorted(glob.glob(f"{CACHE}/*_1H.csv"))
    for f in files:
        name = os.path.basename(f).replace("_1H.csv", "").replace("_NSEI", "NIFTY").replace("_NS", "")
        df = pd.read_csv(f, index_col=0, parse_dates=True)
        close = df["close"].dropna()
        # buy & hold benchmark
        bh = float((close.iloc[-1]/close.iloc[0]-1)*100)
        print(f"\n===== {name}  (hourly, {len(close)} bars; buy&hold {bh:+.0f}%) =====")
        print(f"  {'strategy':13}{'trades':>8}{'GROSS ret':>11}{'net %-only':>12}{'net +Rs20/order':>16}")
        for sname, ent in signals(close).items():
            ex = ~ent  # exit when signal off
            g_ret, g_sh, n = run(close, ent, ex, 0.0, 0.0)
            p_ret, p_sh, _ = run(close, ent, ex, 0.0005, 0.0)
            r_ret, r_sh, _ = run(close, ent, ex, 0.0005, 20.0)
            print(f"  {sname:13}{n:>8}{g_ret:>10.0f}%{p_ret:>11.0f}%{r_ret:>15.0f}%")
    print("\nRead the last column: that's what a Rs 10,000 account actually keeps")
    print("after the Rs 20/order brokerage. If it's deeply negative, intraday is a")
    print("guaranteed loss here regardless of how good the signal looks gross.")


if __name__ == "__main__":
    main()
