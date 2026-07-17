"""
india_signal.py — momentum signal for INDIAN stocks (NSE / Nifty large-caps).

Same validated strategy as before, pointed at stocks an India resident can
actually buy (rupees, no forex):
  1. Eligible = price > 200-day average AND 6-month return > 0  (trend + momentum)
  2. Rank eligible by Carhart momentum (12m return minus last 1m)
  3. Hold TOP-6; fewer qualify -> hold cash (bear protection)
  4. Weight by inverse volatility (more into calmer names), gross <= 1
Monthly cadence. Read-only: computes targets, places NO orders. Prices in INR.
"""
from __future__ import annotations
import os, sys, json, time, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
os.environ.setdefault("VIBE_TRADING_DATA_CACHE", "1")
os.environ.setdefault("TUSHARE_TOKEN", "noop")
try:   # legacy yfinance loader path — unused now that compute_targets wraps signal_engine
    from backtest.loaders.registry import LOADER_REGISTRY, _ensure_registered
    _ensure_registered()
except Exception:
    LOADER_REGISTRY = {}   # not needed for the store-backed signal (OCI has no vibe-trading pkg)

TOPK = 12   # hold 12 (balanced): ~28%/yr, worst drop ~-54% at same risk-score as top-6
LOOKBACK_DAYS = 400
PXCACHE = os.path.expanduser("~/.vibe-trading/pxcache")   # shared; .NS names don't collide
CACHE_FRESH_DAYS = 3
os.makedirs(PXCACHE, exist_ok=True)

# ~24 liquid Nifty large-caps across sectors (banks, IT, energy, FMCG, auto, pharma, infra)
INDIA = ["RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS","HINDUNILVR.NS",
         "ITC.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS","LT.NS","AXISBANK.NS",
         "ASIANPAINT.NS","MARUTI.NS","SUNPHARMA.NS","BAJFINANCE.NS","HCLTECH.NS",
         "WIPRO.NS","TITAN.NS","NESTLEIND.NS","POWERGRID.NS","NTPC.NS","TATAMOTORS.NS","ONGC.NS"]


def disp(sym):  # RELIANCE.NS -> RELIANCE
    return sym.replace(".NS", "")


def _cache_path(code):
    return os.path.join(PXCACHE, code.replace("/", "_") + ".csv")


def load(code, retries=4):
    cp = _cache_path(code)
    if os.path.exists(cp):
        if (time.time() - os.path.getmtime(cp)) / 86400 <= CACHE_FRESH_DAYS:
            try:
                s = pd.read_csv(cp, index_col=0, parse_dates=True)["close"]
                if len(s) >= 260:
                    return s
            except Exception:
                pass
    end = pd.Timestamp.utcnow().normalize() - pd.Timedelta(days=1)
    start = end - pd.Timedelta(days=int(LOOKBACK_DAYS * 1.6) + 40)
    for attempt in range(retries):
        try:
            df = LOADER_REGISTRY["yfinance"]().fetch([code], start.strftime("%Y-%m-%d"),
                                                     end.strftime("%Y-%m-%d"), interval="1D").get(code)
            if df is not None and len(df) >= 260:
                s = df["close"].astype(float); s.index = pd.to_datetime(s.index)
                s = s[~s.index.duplicated(keep="last")].sort_index()
                s.to_frame("close").to_csv(cp)
                return s
        except Exception:
            pass
        time.sleep(2.0 + 2 * attempt)
    return None


def compute_targets(universe=None, strategy=None, topk=20):
    """Validated strategy from the CLEANED local store — zero API calls, no
    throttling. Defaults = Nifty 500 + 'ensemble_regime' (the tournament AND
    after-tax champion: blend momentum+lowvol+risk-adjusted-momentum, and go to
    CASH when the market is below its 200-day trend). Best risk-adjusted after-tax
    (~1.10 Sharpe, shallow -18% drawdowns). See strategy_tournament.py / aftertax_sim.py.
    Returns (df, held, weights, cash); df.attrs['min_balance'] = whole-share min."""
    import signal_engine as se
    if universe is None:
        universe = se.DEFAULT_UNIVERSE
    if strategy is None:
        strategy = se.DEFAULT_STRATEGY
    sig = se.current_signal(universe, strategy, topk)
    picks = sig["picks"]
    if picks.empty:
        # empty can mean risk-OFF (hold cash) — pass that through so the ledger explains it
        picks.attrs["risk_on"] = sig.get("risk_on", True)
        picks.attrs["strategy"], picks.attrs["universe"] = strategy, universe
        return picks, picks, {}, 1.0
    weights = {s: float(picks.loc[s, "weight"]) for s in picks.index}
    picks.attrs["min_balance"] = sig.get("min_balance")
    picks.attrs["universe"], picks.attrs["strategy"] = universe, strategy
    picks.attrs["risk_on"] = sig.get("risk_on", True)
    return picks, picks, weights, sig.get("cash_frac", 0.0)


def main():
    df, held, weights, cash = compute_targets()
    asof = pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print(f"=== Indian momentum targets  ({asof}) ===\n")
    if df.empty:
        print("No data (provider busy). Try again shortly."); return
    print(f"{'stock':11}{'price(Rs)':>11}{'>200d':>7}{'6m ret':>9}{'12-1 mom':>10}{'vol':>7}{'TARGET':>9}")
    print("-" * 64)
    view = df.copy(); view["w"] = pd.Series(weights)
    for s, r in view.sort_values("w", ascending=False).iterrows():
        mark = "  <<HOLD" if weights[s] > 0 else ""
        print(f"{s:11}{r['price']:>11,.0f}{('yes' if r['above_sma200'] else 'no'):>7}"
              f"{(f'{r['ret6m']:+.0%}' if pd.notna(r['ret6m']) else 'n/a'):>9}"
              f"{(f'{r['carhart']:+.0%}' if pd.notna(r['carhart']) else 'n/a'):>10}"
              f"{(f'{r['vol']:.0%}' if pd.notna(r['vol']) else 'n/a'):>7}{weights[s]:>8.0%}{mark}")
    print("-" * 64)
    print(f"{'CASH':11}{'':>43}{cash:>8.0%}")
    print(f"\nHolding {len(held)}/{TOPK} slots; {cash:.0%} cash.")
    out = {"as_of": asof, "weights": {k: v for k, v in weights.items() if v > 0}, "cash": cash}
    json.dump(out, open(os.path.expanduser("~/.vibe-trading/india_targets.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
