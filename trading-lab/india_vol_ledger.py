"""
india_vol_ledger.py — a VOL-CAPPED twin of the ₹10L india research account.

Same momentum champion, same picks — but position size is scaled by a volatility
cap (Carver-style, scale DOWN only, no leverage). When the held book's recent
realised vol runs above the target, we hold more cash; when it's calm, we invest
fully. This is the LIVE, forward version of the voltarget_sweep finding, run side
by side with the un-capped india account so we can watch the drawdown-vs-return
trade play out on real prices instead of a backtest.

Design: a thin monkeypatch over india_ledger — its whole rebalance/report/cron
engine is reused unchanged; we only (a) point it at a separate account file and
(b) multiply the target weights by the vol scalar before it sizes positions.

  INDIA_VOL_TARGET=0.12 (default) — annualised vol cap. Env-overridable.

  python india_vol_ledger.py start [--cash 1000000]
  python india_vol_ledger.py rebalance
  python india_vol_ledger.py status
  python india_vol_ledger.py cron
"""
from __future__ import annotations
import os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import india_ledger as base
import signal_engine as se

# separate account file so it never collides with the un-capped india account
base.ACCOUNT = os.path.expanduser("~/.vibe-trading/india_vol_account.json")
TARGET_VOL = float(os.getenv("INDIA_VOL_TARGET", "0.12"))


def _portfolio_realized_vol(weights: dict) -> float | None:
    """Trailing 20-day annualised vol of the CURRENTLY-TARGETED book (weighted),
    from the same store the signal uses. Mirrors the research vol_manage gauge."""
    if not weights:
        return None
    try:
        px, _ = se._load(se.DEFAULT_UNIVERSE)
    except Exception:
        return None
    held = [s for s in weights if s in px.columns]
    if not held:
        return None
    w = pd.Series({s: float(weights[s]) for s in held})
    if w.sum() <= 0:
        return None
    w = w / w.sum()                                   # normalise across the invested names
    rets = px[held].pct_change().clip(-0.35, 0.35)
    port = (rets * w).sum(axis=1).dropna()
    if len(port) < 20:
        return None
    return float(port.iloc[-20:].std() * np.sqrt(252))


_orig_targets = base._prices_and_targets


def _capped_targets():
    prices, targets, df, held, cash = _orig_targets()
    rv = _portfolio_realized_vol(targets)
    m = 1.0 if (not rv or rv <= 0) else min(1.0, TARGET_VOL / rv)
    capped = {k: v * m for k, v in targets.items()}
    try:                                              # surface the scaling for the report
        df.attrs["vol_scalar"] = round(m, 3)
        df.attrs["realized_vol"] = round(rv, 3) if rv else None
        df.attrs["target_vol"] = TARGET_VOL
    except Exception:
        pass
    if rv:
        print(f"[vol-cap] realised {rv:.0%} vs target {TARGET_VOL:.0%} -> invest "
              f"{m:.0%}, hold {1-m:.0%} extra cash")
    return prices, capped, df, held, cash


base._prices_and_targets = _capped_targets   # engine now sees vol-scaled targets


if __name__ == "__main__":
    base.main()
