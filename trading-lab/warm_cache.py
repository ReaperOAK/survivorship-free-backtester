"""
warm_cache.py — GENTLY populate the local price cache without tripping
yfinance's rate limit. Fetch-once, persist to CSV, reuse forever.

Strategy: wait out any active throttle, then fetch one symbol at a time with
big gaps. Symbols that still fail get retried in later passes after a cooldown.
Fail-FAST per attempt (no long per-symbol backoff) so a throttled symbol
doesn't waste time — we just try it again next pass.
"""
from __future__ import annotations
import os, sys, time
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import momentum_signal as strat   # reuse universe + cache path convention

GAP = 6           # seconds between symbols within a pass
PASS_COOLDOWN = 75  # seconds between passes
MAX_PASSES = 5
INITIAL_COOLDOWN = 45  # let any active throttle clear first


def have_fresh(code):
    cp = strat._cache_path(code)
    if os.path.exists(cp):
        try:
            s = pd.read_csv(cp, index_col=0, parse_dates=True)["close"]
            return len(s) >= 260
        except Exception:
            return False
    return False


def fetch_one(code, src):
    end = pd.Timestamp.utcnow().normalize() - pd.Timedelta(days=1)
    start = end - pd.Timedelta(days=int(strat.LOOKBACK_DAYS * 1.6) + 40)
    try:
        df = strat.LOADER_REGISTRY[src]().fetch([code], start.strftime("%Y-%m-%d"),
                                                end.strftime("%Y-%m-%d"), interval="1D").get(code)
        if df is not None and len(df) >= 260:
            s = df["close"].astype(float); s.index = pd.to_datetime(s.index)
            s = s[~s.index.duplicated(keep="last")].sort_index()
            s.to_frame("close").to_csv(strat._cache_path(code))
            return True
    except Exception:
        pass
    return False


def main():
    targets = [(c, "yfinance") for c in strat.US] + [(ls, "ccxt") for ls in strat.CRYPTO]
    print(f"Warming cache for {len(targets)} symbols. Initial cooldown {INITIAL_COOLDOWN}s...", flush=True)
    time.sleep(INITIAL_COOLDOWN)
    for p in range(1, MAX_PASSES + 1):
        missing = [(c, s) for c, s in targets if not have_fresh(strat.CRYPTO.get(c, c) if s == "ccxt" else c)]
        # note: crypto cache keyed by loader symbol (BTC/USDT), fetched as such
        missing = [(c, s) for c, s in targets if not have_fresh(c)]
        if not missing:
            print(f"Pass {p}: all cached. Done.", flush=True)
            break
        print(f"Pass {p}: {len(missing)} still missing -> {[c for c,_ in missing]}", flush=True)
        got = 0
        for code, src in missing:
            if fetch_one(code, src):
                got += 1
                print(f"  ok {code}", flush=True)
            time.sleep(GAP)
        print(f"Pass {p}: fetched {got}/{len(missing)} this pass.", flush=True)
        if got < len(missing) and p < MAX_PASSES:
            print(f"  cooldown {PASS_COOLDOWN}s before next pass...", flush=True)
            time.sleep(PASS_COOLDOWN)
    cached = sum(1 for c, _ in targets if have_fresh(c))
    print(f"\nDONE: {cached}/{len(targets)} symbols cached at {strat.PXCACHE}", flush=True)


if __name__ == "__main__":
    main()
