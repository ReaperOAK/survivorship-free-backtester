# AI-Trader Lab — Protocol Version Changelog

### Protocol v1.1 (2026-11-19) — *The Quant Audit & Clean Restart*
* **Ledger Bug Fixes**:
  * Fixed fallback bug in `india_ledger.py`: replaced `prices.get(s, p['avg_price'])` with an explicit DuckDB closing price lookup (`get_latest_price()`).
  * Enforced **Fail-Loudly Rule**: if any held position lacks market closing data, raises a `RuntimeError` rather than silently masking paper losses at cost basis.
  * Added unit test `tests/test_ledger_pricing.py` asserting fail-loudly behavior.
  * Fixed `cron()` state bug: `last_rebalance_month` is now updated **only** if `rebalance()` successfully evaluates and executes trades.
* **Architecture Harmonization**:
  * Reconciled the ₹8,714 gap between `status()` and `ledger_audit.py`: proved that 22 dropped names had unrecorded paper losses hidden by the fallback bug.
  * Identified the cadence divergence: demonstrated that a true monthly 200-SMA check lags and sells at crash bottoms (COVID CAGR 7.9%, MaxDD −43.8%), whereas a daily regime stop halves drawdown (MaxDD −18.5%, turnover 966%).
* **Significance & Error Bars**:
  * Ran a 1,000-resample stationary block bootstrap (21-day blocks, 0.40% round-trip friction):
    * CAGR difference vs Buy & Hold: Mean +0.10%, 95% CI [−12.53%, +13.71%] (Prob > 0: 49.5%).
    * Sharpe difference vs Buy & Hold: Mean +0.28, 95% CI [−0.43, +0.99] (Prob > 0: 77.1%).
    * **Conclusion**: Long-term return edge is statistically indistinguishable from zero; the only surviving edge is drawdown suppression.
* **Pre-Registered Protocol & Clean Ledger Restart**:
  * Archived legacy ledgers (`india_account_legacy_20261119.json`, `india_vol_account_legacy_20261119.json`).
  * Restarted `india_account.json` with clean ₹10,00,000 capital, immediately deployed into the 44 current canonical targets with 0.20% friction.
  * Reset the 12-month evaluation clock to start **2026-11-19** (target: **2027-11-19**).
  * Added explicit pass condition (earns a second 12-month extension; does not authorize real capital) and automated watchdog script `kill_rule_watchdog.py`.

---

### Protocol v1.0 (2026-07-17) — *Initial Release*
* Initial open-source research lab.
* Bulk NSE Bhavcopy ingest into DuckDB (`data_store.py`).
* Point-in-time constituent reconstruction via Internet Archive Wayback Machine (`wayback_membership.py`).
* Multi-factor tournament: 1/3 Carhart Momentum + 1/3 Low Volatility + 1/3 Risk-Adjusted Momentum.
* Experimental paper ledgers for Indian equities and mutual fund SIPs.
