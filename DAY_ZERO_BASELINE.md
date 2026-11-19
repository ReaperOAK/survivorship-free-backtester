# Day-Zero Forward Test Baseline

**Registration Date:** 2026-11-19  
**Evaluation Period:** 2026-11-19 → 2027-11-19 (Month 12)  
**Strategy Protocol:** Canonical Indian Quantitative Ensemble (Protocol v1.1)  
**Target Scope:** `~/.vibe-trading/india_account.json` (Main Book) & `india_vol_account.json` (Vol Book)

---

## 1. Capital & Equity Reconciliation (Dated Errata 2026-11-19)

To ensure zero ambiguity when evaluating Month 12 returns, the Day-Zero portfolio accounting is formally defined below:

| Accounting Metric | Amount (₹) | Formula / Derivation |
|---|:---:|---|
| **Starting Account Cash** | **₹10,00,000.00** | Initial pre-funded cash deposit on Day Zero |
| **Gross Stock Market Value (44 positions)** | **₹9,35,822.98** | $\sum (\text{Quantity} \times \text{Entry Price})$ |
| **Day-Zero Entry Friction Paid (0.20%)** | **₹1,871.65** | $0.002 \times \text{Gross Stock Value}$ (Brokerage, STT, Stamp, GST) |
| **Total Cash Deployed on Stock Purchase** | **₹9,37,694.63** | Gross Stock Value + Entry Friction |
| **Unallocated Cash Balance Remaining** | **₹62,305.37** | Starting Cash − Total Deployed (6.23% integer rounding drag) |
| **Total Portfolio Equity (Day-Zero Base)** | **₹9,98,128.35** | **Gross Stock Market Value (₹9,35,823) + Cash Balance (₹62,305)** |
| **Day-Zero Realized Drag** | **₹1,871.65** | Starting Cash − Total Equity (0.187% realized entry cost) |

> [!IMPORTANT]
> **Total Portfolio Equity at Day Zero is ₹9,98,128.35 (inclusive of the ₹62,305.37 cash).**  
> Cash is NOT additive to ₹9,98,128.35. At Day Zero, only the 0.20% entry friction has been realized (₹1,871.65). The 0.20% exit friction will only be realized upon liquidation/rebalance.

---

## 2. Fill Price & Execution Timing Convention

* **Execution Price Convention:** Day-Zero initial fills and all ongoing paper rebalances execute at **EOD NSE Bhavcopy closing prices**, NOT next-day open.
* **Operational Rationale:** The daily automated cron pipeline runs post-market at 17:30 UTC (23:00 IST), downloads the published NSE Bhavcopy, loads closing prices into DuckDB, and calculates rebalances against verified closing data. While the theoretical backtest engine assumes next-day open fills, the live forward paper ledger executes deterministically against EOD closes with 0.20% round-trip friction.

---

## 3. Pre-Registered Benchmark Targets

### Primary Benchmark: Investable Nifty 500 TRI Fund
* **Instrument:** ICICI Prudential Nifty 500 Index Fund (Direct - Growth), AMFI Scheme Code: `153161`  
  *(SEBI-mandated open-ended index fund tracking the Nifty 500 Total Return Index with dividends reinvested).*
* **Benchmark Nature:** Net of actual Total Expense Ratio (~0.20% p.a.), transaction costs, and tracking error. This represents the true investable alternative for an Indian retail investor.
* **Day-Zero Reference NAV (2026-11-18 EOD):** **10.6787**
* **Day-Zero Investable Units (₹10,00,000 base):** **93,644.3575 units**
* **Mechanical Month-12 Net Evaluation:**
  $$\text{Benchmark NAV Value at Month 12} = 93,644.3575 \times \text{NAV}_{2027-11-19}$$
  $$\text{TRI Benchmark 12-Month Net Return} = \frac{\text{Value} - 1,000,000.00}{1,000,000.00}$$

### Secondary Reference: Nifty 500 Price Index (`^CRSLDX`)
* **Closing Level (2026-11-18):** 23,630.25
* **Opening Level (2026-11-19):** 23,777.85

---

## 4. Canonical Initial Holdings (Main Book: `india_account.json`)

All 44 positions were allocated under the canonical equal 1/3 Momentum + 1/3 Low-Vol + 1/3 Mom/Vol ensemble, floored to whole shares with 0.20% entry friction:

| Symbol | Quantity | Buy Price (₹) | Gross Value (₹) | Entry Fee (0.2%) | Total Cash Spent (₹) | Sleeve |
|---|:---:|:---:|:---:|:---:|:---:|---|
| **AETHER** | 20 | 1,662.70 | 33,254.00 | 66.51 | 33,320.51 | Mom / Vol |
| **ANANDRATHI** | 14 | 2,375.30 | 33,254.20 | 66.51 | 33,320.71 | Mom / Vol |
| **APARINDS** | 2 | 14,171.00 | 28,342.00 | 56.68 | 28,398.68 | Mom / Vol |
| **ATHERENERG** | 17 | 1,908.60 | 32,446.20 | 64.89 | 32,511.09 | Mom / Vol |
| **CPPLUS** | 8 | 3,989.20 | 31,913.60 | 63.83 | 31,977.43 | Mom / Vol |
| **HFCL** | 147 | 226.27 | 33,261.69 | 66.52 | 33,328.21 | Mom / Vol |
| **LAURUSLABS** | 14 | 2,338.00 | 32,732.00 | 65.46 | 32,797.46 | Mom / Vol |
| **MCX** | 8 | 3,705.40 | 29,643.20 | 59.29 | 29,702.49 | Mom / Vol |
| **MTARTECH** | 5 | 5,709.50 | 28,547.50 | 57.10 | 28,604.60 | Mom / Vol |
| **RUBICON** | 19 | 1,683.90 | 31,994.10 | 63.99 | 32,058.09 | Mom / Vol |
| **SANSERA** | 7 | 4,614.60 | 32,302.20 | 64.60 | 32,366.80 | Mom / Vol |
| **SHRIPISTON** | 7 | 4,322.10 | 30,254.70 | 60.51 | 30,315.21 | Mom / Vol |
| **STLTECH** | 82 | 405.15 | 33,222.30 | 66.44 | 33,288.74 | Mom / Vol |
| **SYRMA** | 23 | 1,433.90 | 32,979.70 | 65.96 | 33,045.66 | Mom / Vol |
| **WELCORP** | 14 | 2,260.20 | 31,642.80 | 63.29 | 31,706.09 | Mom / Vol |
| **ACUTAAS** | 4 | 3,942.90 | 15,771.60 | 31.54 | 15,803.14 | Low Vol |
| **AEGISLOG** | 13 | 1,211.60 | 15,750.80 | 31.50 | 15,782.30 | Mom / Trend |
| **ALKEM** | 3 | 5,175.00 | 15,525.00 | 31.05 | 15,556.05 | Low Vol |
| **AUROPHARMA** | 9 | 1,794.10 | 16,146.90 | 32.29 | 16,179.19 | Mom / Trend |
| **AZAD** | 7 | 2,364.80 | 16,553.60 | 33.11 | 16,586.71 | Mom / Trend |
| **CASTROLIND** | 87 | 191.09 | 16,624.83 | 33.25 | 16,658.08 | Low Vol |
| **CIPLA** | 12 | 1,388.00 | 16,656.00 | 33.31 | 16,689.31 | Low Vol |
| **CRAFTSMAN** | 1 | 11,195.00 | 11,195.00 | 22.39 | 11,217.39 | Mom / Trend |
| **FINCABLES** | 13 | 1,230.40 | 15,995.20 | 31.99 | 16,027.19 | Mom / Trend |
| **GILLETTE** | 2 | 7,098.50 | 14,197.00 | 28.39 | 14,225.39 | Low Vol |
| **GLAND** | 5 | 3,248.40 | 16,242.00 | 32.48 | 16,274.48 | Mom / Trend |
| **GODREJCP** | 18 | 894.50 | 16,101.00 | 32.20 | 16,133.20 | Low Vol |
| **HINDUNILVR** | 8 | 2,009.90 | 16,079.20 | 32.16 | 16,111.36 | Low Vol |
| **IPCALAB** | 9 | 1,834.40 | 16,509.60 | 33.02 | 16,542.62 | Low Vol |
| **IRCTC** | 37 | 449.35 | 16,625.95 | 33.25 | 16,659.20 | Low Vol |
| **JINDALSAW** | 64 | 258.79 | 16,562.56 | 33.13 | 16,595.69 | Mom / Trend |
| **JSWCEMENT** | 132 | 125.94 | 16,624.08 | 33.25 | 16,657.33 | Low Vol |
| **LT** | 4 | 4,155.50 | 16,622.00 | 33.24 | 16,655.24 | Mom / Trend |
| **LUPIN** | 8 | 1,950.00 | 15,600.00 | 31.20 | 15,631.20 | Low Vol |
| **NATCOPHARM** | 20 | 822.90 | 16,458.00 | 32.92 | 16,490.92 | Low Vol |
| **NTPC** | 51 | 321.80 | 16,411.80 | 32.82 | 16,444.62 | Low Vol |
| **ONGC** | 74 | 223.52 | 16,540.48 | 33.08 | 16,573.56 | Low Vol |
| **SBIN** | 15 | 1,108.60 | 16,629.00 | 33.26 | 16,662.26 | Low Vol |
| **SONACOMS** | 18 | 899.70 | 16,194.60 | 32.39 | 16,226.99 | Mom / Trend |
| **SRF** | 6 | 2,479.40 | 14,876.40 | 29.75 | 14,906.15 | Low Vol |
| **SUNPHARMA** | 8 | 1,870.00 | 14,960.00 | 29.92 | 14,989.92 | Low Vol |
| **TORNTPHARM** | 3 | 4,668.80 | 14,006.40 | 28.01 | 14,034.41 | Low Vol |
| **UTIAMC** | 19 | 847.65 | 16,105.35 | 32.21 | 16,137.56 | Low Vol |
| **WELSPUNLIV** | 62 | 265.62 | 16,468.44 | 32.94 | 16,501.38 | Mom / Trend |
| **TOTAL STOCKS** | — | — | **₹9,35,822.98** | **₹1,871.65** | **₹9,37,694.63** | — |
| **CASH REMAINDER**| — | — | — | — | **₹62,305.37** | Idle Cash |
| **TOTAL ACCOUNT** | — | — | — | — | **₹10,00,000.00** | Net Eq: ₹9,98,128.35 |

---

## 5. Volatility-Targeted Ledger (`india_vol_account.json`) Reconciliation

The volatility-targeted companion account operates under dynamic risk-targeting (target annualized volatility = 12%):
* **Target Leverage / Allocation:** 0.69 (69.0% Target Equity, 31.0% Target Cash).
* **Target Equity Spend:** ₹6,90,000.00.
* **Whole-Share Allocation Result:**
  * Gross Stock Value Purchased: ₹6,22,307.65 (62.3% of portfolio).
  * Entry Friction Paid (0.20%): ₹1,244.62.
  * Total Cash Deployed on Stocks: ₹6,23,552.27.
  * Remaining Cash Balance: **₹3,76,447.73** (37.69% of equity).
  * Total Opening Equity: **₹9,98,755.38** (Gross Stocks ₹6,22,308 + Cash ₹3,76,448).
* **The 31.0% vs 37.7% Cash Reconciliation:**
  * The algorithm targeted 31.0% cash.
  * Discretizing 44 stock orders into whole shares resulted in ₹66,447.73 (6.65% of portfolio) of whole-share truncation remainder.
  * Total actual opening cash = $31.04\% (\text{vol-target}) + 6.65\% (\text{integer rounding}) = \mathbf{37.69\%}$.
