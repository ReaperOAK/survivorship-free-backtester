"""
research_v1 — transparent, look-ahead-safe strategy screen.

Discipline:
  * Signal computed from data up to & including close_t, then SHIFTED 1 bar
    (position applied to next-day return) -> no look-ahead.
  * Transaction cost charged on turnover (|Δposition|).
  * TRAIN period picks nothing here (params are fixed a priori / classic);
    we simply report TRAIN vs TEST so we can see if edge survives OOS.
  * Long/flat only (matches platform paper-trading; no leverage).

Sources that work in this env: yfinance (US), ccxt/binance (crypto).
"""
from __future__ import annotations
import os, sys, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
os.environ.setdefault("VIBE_TRADING_DATA_CACHE", "1")
os.environ.setdefault("TUSHARE_TOKEN", "noop")

sys.path.insert(0, os.path.expanduser("~/../.."))  # no-op safety
from backtest.loaders.registry import LOADER_REGISTRY, _ensure_registered  # noqa: E402
_ensure_registered()

START, SPLIT, END = "2018-01-01", "2022-06-30", "2025-12-31"
COST = 0.0005          # 5 bps per unit turnover (round-trip ~10 bps)
ANN = 252

US = ["SPY", "QQQ", "IWM", "EFA", "TLT", "GLD", "AAPL", "MSFT", "NVDA", "AMZN"]
CRYPTO = [("BTC/USDT", "ccxt"), ("ETH/USDT", "ccxt")]


def load(code: str, src: str) -> pd.Series | None:
    try:
        L = LOADER_REGISTRY[src]()
        dm = L.fetch([code], START, END, interval="1D")
        df = dm.get(code)
        if df is None or len(df) < 300:
            return None
        s = df["close"].astype(float)
        s.index = pd.to_datetime(s.index)
        return s[~s.index.duplicated(keep="last")].sort_index()
    except Exception as e:
        print(f"  ! {code}/{src} load failed: {str(e)[:70]}")
        return None


def rsi(series: pd.Series, n: int) -> pd.Series:
    d = series.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def signals(close: pd.Series) -> dict[str, pd.Series]:
    """Each returns a target position in {0,1} indexed like close (pre-shift)."""
    out = {}
    out["buyhold"] = pd.Series(1.0, index=close.index)
    out["sma200"] = (close > close.rolling(200).mean()).astype(float)
    out["sma50_200"] = (close.rolling(50).mean() > close.rolling(200).mean()).astype(float)
    mom = close.pct_change(126)  # 6-month time-series momentum
    out["tsmom126"] = (mom > 0).astype(float)
    hi = close.rolling(50).max(); lo = close.rolling(50).min()
    br = pd.Series(np.nan, index=close.index)
    br[close >= hi] = 1.0; br[close <= lo] = 0.0
    out["donchian50"] = br.ffill().fillna(0.0)
    r = rsi(close, 2)
    mr = pd.Series(np.nan, index=close.index)
    mr[r < 10] = 1.0; mr[r > 70] = 0.0
    out["rsi2_meanrev"] = (mr.ffill().fillna(0.0) * (close > close.rolling(200).mean())).astype(float)
    return out


def evaluate(close: pd.Series, pos: pd.Series) -> pd.Series:
    ret = close.pct_change().fillna(0.0)
    p = pos.shift(1).fillna(0.0)                 # <-- look-ahead guard
    turn = p.diff().abs().fillna(0.0)
    strat = p * ret - turn * COST
    return strat


def stats(strat: pd.Series) -> dict:
    if strat.std() == 0 or len(strat) < 20:
        return dict(cagr=0, sharpe=0, maxdd=0, vol=0)
    eq = (1 + strat).cumprod()
    yrs = len(strat) / ANN
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    sharpe = strat.mean() / strat.std() * np.sqrt(ANN)
    dd = (eq / eq.cummax() - 1).min()
    return dict(cagr=cagr, sharpe=sharpe, maxdd=dd, vol=strat.std() * np.sqrt(ANN))


def main():
    universe = [(c, "yfinance") for c in US] + CRYPTO
    prices = {}
    print("Loading universe...")
    for code, src in universe:
        s = load(code, src)
        if s is not None:
            prices[code] = s
            print(f"  {code:10} {src:8} {len(s)} bars  {s.index[0].date()}..{s.index[-1].date()}")
    print(f"Loaded {len(prices)}/{len(universe)} symbols\n")

    strat_names = ["buyhold", "sma200", "sma50_200", "tsmom126", "donchian50", "rsi2_meanrev"]
    # portfolio = equal-weight average of per-asset strategy returns
    rows = []
    for name in strat_names:
        for phase, lo, hi in [("TRAIN", START, SPLIT), ("TEST", SPLIT, END)]:
            per_asset = []
            for code, s in prices.items():
                sig = signals(s)[name]
                strat = evaluate(s, sig)
                strat = strat[(strat.index >= lo) & (strat.index < hi)]
                per_asset.append(strat)
            port = pd.concat(per_asset, axis=1).mean(axis=1).dropna()
            st = stats(port)
            rows.append((name, phase, st["cagr"], st["sharpe"], st["maxdd"], st["vol"]))

    print(f"{'strategy':14}{'phase':7}{'CAGR':>9}{'Sharpe':>9}{'MaxDD':>9}{'Vol':>8}")
    print("-" * 56)
    for name, phase, cagr, sh, dd, vol in rows:
        star = "  <<" if (phase == "TEST" and sh > 0.8) else ""
        print(f"{name:14}{phase:7}{cagr:>8.1%}{sh:>9.2f}{dd:>8.1%}{vol:>8.1%}{star}")
    print("\n(equal-weight portfolio across all loaded symbols; long/flat; 5bps turnover cost)")


if __name__ == "__main__":
    main()
