# Pre-Registered Strategy Protocol & Kill Rule (Protocol v1.1)

**Effective Registration Date:** 2026-11-19  
**Evaluation Clock Start:** 2026-11-19 (Month 12 Target: 2027-11-19)  
**Target Scope:** `~/.vibe-trading/india_account.json` ONLY.  
*(Exemption: `india_vol_account.json` is explicitly exempt from Cash Drag Trigger 3, as it targets volatility dynamically and holds 30%+ cash by design).*  

---

## 1. Benchmark & Tax Specification (Dated Errata 2026-11-19)

### 1.1 Investable Benchmark Instrument
* **Primary Benchmark:** **ICICI Prudential Nifty 500 Index Fund (Direct - Growth)**  
  * **AMFI Scheme Code:** `153161`
  * **Day-Zero Reference NAV (2026-11-18 EOD):** **10.6787**
  * **Day-Zero Investable Units (₹10,00,000 base):** **93,644.3575 units**
* **Benchmark Nature:** This is explicitly an investable mutual fund NAV tracking the Nifty 500 Total Return Index (all corporate dividends reinvested), net of Total Expense Ratio (~0.20% p.a.) and tracking error.

### 1.2 Explicit After-Tax Evaluation Standard
All evaluation metrics against the benchmark are strictly **AFTER-TAX**:
* **Applicable Tax Rate:** **20.0% flat Short-Term Capital Gains (STCG)** on all net realized gains, in compliance with the Indian Finance Act 2024 (for listed equity held < 12 months).
* **Tax Accounting Method:** First-In, First-Out (FIFO) on realized transactions.
* **Month-12 Imputed Tax Treatment:** At the Month-12 evaluation date (2027-11-19), any net unrealized profit on currently held positions will have a provisional 20% tax haircut deducted to reflect true liquidating post-tax value in pocket.
* **Benchmark Tax Treatment:** The benchmark fund NAV is held continuously without realization; at Month 12, its gain is subjected to the same applicable statutory tax rate (or evaluated on after-tax redemption value) to guarantee an apples-to-apples net-of-tax comparison.

### 1.3 Execution Fill Price Convention
* **Fill Price Basis:** All initial paper fills and monthly rebalances execute at **same-day EOD Bhavcopy closing prices**, NOT next-day open.
* **Operational Rationale:** Ingest scripts run post-market at 17:30 UTC / 23:00 IST and calculate orders based on official NSE closing prices with 0.20% round-trip execution friction.

---

## 2. Specification Reality (The Cadence Dilemma)
Research on Nifty 500 (2017–2026) revealed a structural divergence between monthly and daily regime enforcement:
* **Monthly-Only Regime Filter**: Checking the 200-SMA only on the last day of the month takes the full brunt of sudden mid-month crashes (e.g. COVID March 2020) and liquidates at the bottom on March 31, collapsing CAGR to **7.9%** and Sharpe to **0.56** (MaxDD −43.8%).
* **Daily Regime Stop**: Liquidating to cash as soon as the index breaks its 200 SMA preserves capital (Sharpe 1.20, MaxDD −18.8%), but incurs **~966% annual turnover** and heavy whipsaw friction.
* **Unhedged Ensemble**: Holding the 1/3 Mom + 1/3 Low-Vol + 1/3 Mom-Vol blend without any regime cash switch yields **18.2% CAGR, Sharpe 1.05, and MaxDD −36.9%**.

**Canonical Standard for Forward Testing:**
The paper ledger (`india_account.json`) runs the **Daily Regime Stop** mechanism: positions are rebalanced monthly, but the portfolio monitors the 200-day trend daily; if broken, it transitions to cash.

---

## 3. Hard Kill Triggers (Failure Conditions)
If any of the following triggers trip, the strategy is **immediately and permanently decommissioned**:

1. **Trigger 1 (12-Month Net After-Tax Underperformance):**  
   At Month 12 (**2027-11-19**), if the strategy's net return (after 0.40% round-trip friction and 20% FIFO STCG tax) trails the ICICI Pru Nifty 500 Index Fund (Direct - Growth) after-tax return by more than **6.0 percentage points**.
2. **Trigger 2 (Drawdown Tolerance Breach):**  
   If peak-to-trough drawdown exceeds **−22.0%** at any point.
3. **Trigger 3 (Cash Drag Failure — Unconstrained Book Only):**  
   If whole-share integer rounding causes unallocated idle cash in `india_account.json` to exceed **15.0%** of total equity for **three consecutive monthly rebalances**.
4. **Trigger 4 (Drawdown Regime Failure):**  
   During any verified broad market (Nifty 500) drawdown of **10.0% or greater**, the strategy fails to transition to cash or suffers a deeper drawdown than the index fund itself.

---

## 4. Explicit Pass Condition (What Survival Earns)
* **Survival is NOT a green light for real capital.**
* **What a Pass Earns:** If all kill triggers are avoided through 2027-11-19, the strategy earns **a second 12-month extension of forward paper testing** to observe how it handles an out-of-sample bear market.
* Under no circumstances does passing Year 1 authorize deploying real money without a pre-registered execution slippage audit on a live broker.

---

## 5. Automated Enforcement Mechanism
An automated cron watchdog (`trading-lab/kill_rule_watchdog.py`) executes on the 1st of every month:
1. Calculates trailing 12-month return against ICICI Pru Nifty 500 Index Fund NAV after 20% STCG.
2. Checks current drawdown from peak.
3. Evaluates cash drag percentage.
4. Writes an immutable audit verdict to `~/.vibe-trading/kill_rule_audit.log`.
5. If any trigger is tripped, it sets `"status": "KILLED"` in the ledger and marks the repository as decommissioned.
