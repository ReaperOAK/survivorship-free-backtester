# Pre-Registered Strategy Protocol & Kill Rule (Protocol v1.1)

**Effective Registration Date:** 2026-11-19  
**Evaluation Clock Start:** 2026-11-19 (Month 12 Target: 2027-11-19)  
**Target Scope:** `~/.vibe-trading/india_account.json` ONLY.  
*(Exemption: `india_vol_account.json` is explicitly exempt from Cash Drag Trigger 3, as it targets volatility dynamically and holds 30%+ cash by design).*  
**Benchmark:** Nifty 500 TRI (Total Return Index, dividends reinvested).

---

## 1. Specification Reality (The Cadence Dilemma)
Research on Nifty 500 (2017–2026) revealed a critical structural divergence between monthly and daily regime enforcement:
* **Monthly-Only Regime Filter**: Checking the 200-SMA only on the last day of the month takes the full brunt of sudden mid-month crashes (e.g. COVID March 2020) and liquidates at the bottom on March 31, collapsing CAGR to **7.9%** and Sharpe to **0.56** (MaxDD −43.8%).
* **Daily Regime Stop**: Liquidating to cash as soon as the index breaks its 200 SMA preserves capital (Sharpe 1.20, MaxDD −18.8%), but incurs **~966% annual turnover** and heavy whipsaw friction.
* **Unhedged Ensemble**: Holding the 1/3 Mom + 1/3 Low-Vol + 1/3 Mom-Vol blend without any regime cash switch yields **18.2% CAGR, Sharpe 1.05, and MaxDD −36.9%**.

**Canonical Standard for Forward Testing:**
The paper ledger (`india_account.json`) runs the **Daily Regime Stop** mechanism: positions are rebalanced monthly, but the portfolio monitors the 200-day trend daily; if broken, it transitions to cash.

---

## 2. Hard Kill Triggers (Failure Conditions)
If any of the following triggers trip, the strategy is **immediately and permanently decommissioned**:

1. **Trigger 1 (12-Month Net Underperformance):**  
   At Month 12 (**2027-11-19**), if the strategy's net return (after 0.40% round-trip friction and FIFO STCG/LTCG tax) trails the Nifty 500 TRI by more than **6.0 percentage points**.
2. **Trigger 2 (Drawdown Tolerance Breach):**  
   If peak-to-trough drawdown exceeds **−22.0%** at any point.
3. **Trigger 3 (Cash Drag Failure — Unconstrained Book Only):**  
   If whole-share integer rounding causes unallocated idle cash in `india_account.json` to exceed **15.0%** of total equity for **three consecutive monthly rebalances**.
4. **Trigger 4 (Drawdown Regime Failure):**  
   During any verified broad market (Nifty 500) drawdown of **10.0% or greater**, the strategy fails to transition to cash or suffers a deeper drawdown than the index itself.

---

## 3. Explicit Pass Condition (What Survival Earns)
* **Survival is NOT a green light for real capital.**
* **What a Pass Earns:** If all kill triggers are avoided through 2027-11-19, the strategy earns **a second 12-month extension of forward paper testing** to observe how it handles an out-of-sample bear market.
* Under no circumstances does passing Year 1 authorize deploying real money without a pre-registered execution slippage audit on a live broker.

---

## 4. Automated Enforcement Mechanism
An automated cron watchdog (`trading-lab/kill_rule_watchdog.py`) executes on the 1st of every month:
1. Calculates trailing 12-month return against Nifty 500 TRI.
2. Checks current drawdown from peak.
3. Evaluates cash drag percentage.
4. Writes an immutable audit verdict to `~/.vibe-trading/kill_rule_audit.log`.
5. If any trigger is tripped, it sets `"status": "KILLED"` in the ledger and marks the repository as decommissioned.
