"""
signal.py — the DEPLOYABLE momentum signal (what to hold right now).

Built from what the research actually validated (two independent methods both
pointed to momentum):
  * Cross-sectional Carhart momentum (12m-1m) = the only 'alive' S&P factor.
  * Time-series trend gate (>SMA200) = bear protection from the daily study.
  * Inverse-vol weighting = better risk-adjusted construction.

Rules (monthly cadence; long/flat; no leverage):
  1. Eligible = price > SMA200 AND 6-month return > 0   (trend + absolute mom)
  2. Rank eligible by Carhart momentum (12m return minus last-1m return)
  3. Hold TOP-K; if fewer than K qualify, hold cash for the rest (bear defense)
  4. Weight held names by inverse 60d volatility, scaled so gross <= 1

Outputs target weights per PLATFORM symbol (US tickers + BTC/ETH).
Read-only: computes targets, places NO orders.
"""
from __future__ import annotations
import os, sys, json, time, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
os.environ.setdefault("VIBE_TRADING_DATA_CACHE", "1")
os.environ.setdefault("TUSHARE_TOKEN", "noop")
from backtest.loaders.registry import LOADER_REGISTRY, _ensure_registered
_ensure_registered()

TOPK = 6
LOOKBACK_DAYS = 400  # enough for SMA200 + 12m momentum
PXCACHE = os.path.expanduser("~/.vibe-trading/pxcache")  # local parquet cache
CACHE_FRESH_DAYS = 3   # reuse cached series if updated within N days
os.makedirs(PXCACHE, exist_ok=True)

# platform-tradeable universe: sector ETFs + liquid megacaps + crypto majors
US = ["XLK","XLF","XLE","XLV","XLI","XLY","XLP","XLU","XLB",
      "AAPL","MSFT","NVDA","AMZN","GOOGL","META","AVGO","JPM","XOM","LLY"]
CRYPTO = {"BTC/USDT": "BTC", "ETH/USDT": "ETH"}   # loader symbol -> platform symbol


def _cache_path(code):
    # CSV (not pickle): safe to load, no engine dependency, human-readable.
    return os.path.join(PXCACHE, code.replace("/", "_") + ".csv")


def load(code, src, days=LOOKBACK_DAYS, retries=4):
    # 1) serve from local parquet cache if fresh (fetch-once, reuse) -> avoids
    #    hammering yfinance into a rate-limit on every run.
    cp = _cache_path(code)
    if os.path.exists(cp):
        age_days = (time.time() - os.path.getmtime(cp)) / 86400
        if age_days <= CACHE_FRESH_DAYS:
            try:
                s = pd.read_csv(cp, index_col=0, parse_dates=True)["close"]
                if len(s) >= 260:
                    return s
            except Exception:
                pass
    # 2) fetch from network (end=yesterday; today's bar isn't settled), with
    #    patient backoff on throttling, then persist to the parquet cache.
    end = pd.Timestamp.utcnow().normalize() - pd.Timedelta(days=1)
    start = end - pd.Timedelta(days=int(days * 1.6) + 40)
    for attempt in range(retries):
        try:
            dm = LOADER_REGISTRY[src]().fetch([code], start.strftime("%Y-%m-%d"),
                                              end.strftime("%Y-%m-%d"), interval="1D")
            df = dm.get(code)
            if df is not None and len(df) >= 260:
                s = df["close"].astype(float); s.index = pd.to_datetime(s.index)
                s = s[~s.index.duplicated(keep="last")].sort_index()
                s.to_frame("close").to_csv(cp)   # persist for reuse
                return s
        except Exception:
            pass
        time.sleep(2.0 + 2 * attempt)   # patient backoff on rate-limit
    return None


def compute_targets():
    series = {}
    for c in US:
        s = load(c, "yfinance")
        if s is not None: series[c] = s
        else: print(f"  (skip {c}: no data)", file=sys.stderr)
        time.sleep(0.5)   # pace yfinance to avoid rate-limit
    for loader_sym, plat_sym in CRYPTO.items():
        s = load(loader_sym, "ccxt")
        if s is not None: series[plat_sym] = s

    rows = {}
    for sym, s in series.items():
        px = s.iloc[-1]
        sma200 = s.rolling(200).mean().iloc[-1]
        ret6m = s.iloc[-1] / s.iloc[-126] - 1 if len(s) >= 126 else np.nan
        # Carhart 12m-1m: return from t-252 to t-21
        car = s.iloc[-21] / s.iloc[-252] - 1 if len(s) >= 252 else np.nan
        vol = s.pct_change().iloc[-60:].std() * np.sqrt(252)
        rows[sym] = dict(price=px, above_sma200=px > sma200, ret6m=ret6m,
                         carhart=car, vol=vol)
    df = pd.DataFrame(rows).T
    if df.empty:
        # every fetch failed (e.g. provider throttling) — degrade gracefully,
        # do NOT crash and do NOT emit bogus targets.
        return df, df, {}, 1.0

    eligible = df[(df["above_sma200"]) & (df["ret6m"] > 0)].copy()
    eligible = eligible.sort_values("carhart", ascending=False)
    held = eligible.head(TOPK).copy()

    weights = {s: 0.0 for s in df.index}
    if len(held):
        inv = 1.0 / held["vol"].replace(0, np.nan)
        inv = inv / inv.sum()
        scale = len(held) / TOPK          # partial cash if < TOPK qualify
        for s in held.index:
            weights[s] = float(inv[s] * scale)
    cash = 1.0 - sum(weights.values())
    return df, held, weights, cash


def main():
    df, held, weights, cash = compute_targets()
    asof = pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print(f"=== Momentum target portfolio  ({asof}) ===\n")
    print(f"{'symbol':8}{'price':>11}{'>SMA200':>9}{'6m ret':>9}{'12-1 mom':>10}{'ann.vol':>9}{'TARGET w':>10}")
    print("-"*66)
    view = df.copy()
    view["w"] = pd.Series(weights)
    view = view.sort_values("w", ascending=False)
    for s, r in view.iterrows():
        mark = "  <<HOLD" if weights[s] > 0 else ""
        c = r["carhart"]; sixm = r["ret6m"]
        print(f"{s:8}{r['price']:>11.2f}{('yes' if r['above_sma200'] else 'no'):>9}"
              f"{(f'{sixm:+.1%}' if pd.notna(sixm) else 'n/a'):>9}"
              f"{(f'{c:+.1%}' if pd.notna(c) else 'n/a'):>10}"
              f"{(f'{r['vol']:.0%}' if pd.notna(r['vol']) else 'n/a'):>9}"
              f"{weights[s]:>9.1%}{mark}")
    print("-"*66)
    print(f"{'CASH':8}{'':>47}{cash:>9.1%}")
    print(f"\nHolding {len(held)}/{TOPK} slots; {cash:.0%} cash. "
          f"Long/flat, inverse-vol, gross={1-cash:.0%}.")
    # machine-readable for the trader
    out = {"as_of": asof, "weights": {k: v for k, v in weights.items() if v > 0}, "cash": cash}
    path = os.path.expanduser("~/.vibe-trading/targets.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"targets -> {path}")


if __name__ == "__main__":
    main()
