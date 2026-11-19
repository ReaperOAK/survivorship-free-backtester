# Pre-Registered Strategy Protocol & Kill Rule

**Document Version:** 1.0  
**Effective Date:** 2026-11-19  
**System:** AI-Trader Lab (Canonical Indian Equities Quantitative Ensemble)  
**Target Ledger:** `~/.vibe-trading/india_account.json`  
**Git Commit / Hash Reference:** Locked on `main`

---

## 1. Purpose & Pre-Commitment
This document establishes an unalterable, pre-registered testing protocol and kill rule for the Indian Equities Quantitative Ensemble strategy. In accordance with quantitative research best practices, these rules are committed prior to observing forward out-of-sample data and cannot be adjusted retroactively.

---

## 2. Canonical Specification (Unified Standard)
All backtests, simulations, tax models, and live paper ledgers must adhere to this single canonical implementation:

| Parameter | Canonical Rule |
|---|---|
| **Universe** | Nifty 500 Point-in-Time (reconstructed via Wayback Machine, survivorship-corrected) |
| **Rebalance Cadence** | Monthly (1st trading day of each calendar month) |
| **Signal Model** | Equal 1/3 weight blend: (1) Carhart 12-1 Momentum, (2) 1-Year Low Volatility, (3) Risk-Adjusted Momentum (Return / Vol) |
| **Individual Gate** | Price > 200-day SMA AND 6-month momentum > 0 |
| **Macro Regime Filter** | Monthly broad equal-weight proxy > 200-day SMA at rebalance date. If FALSE → 100% Cash for the month |
| **Execution Price** | Next-day Market Open (eliminating same-day close look-ahead bias) |
| **Whole-Share Sizing** | Floor to integer quantities; unallocated rupees remain in cash |

---

## 3. Pre-Registered Benchmark
* **Primary Benchmark:** **Nifty 500 Total Return Index (TRI)**.  
  *(Must include dividend reinvestment, not the price index).*
* **Secondary Benchmark:** Equal-Weight Nifty 500 Point-in-Time Universe.

---

## 4. Pre-Registered Kill Rules (Hard Triggers)
The strategy will be run untouched. If any of the following conditions are met, the strategy is **immediately and permanently decommissioned**, documented as a failed hypothesis, and barred from being presented as viable:

### Trigger 1: 12-Month Net Underperformance
* **Condition:** After 12 months of live paper execution (minimum evaluation date: **2027-07-16**), the net portfolio return (net of 0.20% friction and FIFO STCG/LTCG tax) trails the Nifty 500 TRI by more than **6.0 percentage points**.

### Trigger 2: Drawdown Tolerance Breach
* **Condition:** The peak-to-trough drawdown of the portfolio exceeds **−22.0%** at any point.  
  *(The backtested maximum drawdown of the monthly regime ensemble is −18.0%. A breach beyond −22.0% statistically rejects the drawdown-reduction hypothesis).*

### Trigger 3: Execution & Cash Drag Failure
* **Condition:** Whole-share integer allocation causes idle unallocated cash to exceed **15.0%** of total portfolio equity for **three consecutive monthly rebalances** on a ₹10,00,000 book.

### Trigger 4: Drawdown Regime Failure
* **Condition:** During a verified broad market (Nifty 500) drawdown of **10.0% or greater**, the strategy fails to transition to cash or experiences a deeper drawdown than the index itself.

---

## 5. Decommission Protocol
Upon tripping any kill trigger:
1. All positions are immediately marked liquidated to cash at the next trading open.
2. An automated post-mortem is generated detailing the exact date, price action, and failure mode.
3. The repository README is updated with a permanent badge: `Status: Decommissioned (Tripped Kill Rule X)`.
