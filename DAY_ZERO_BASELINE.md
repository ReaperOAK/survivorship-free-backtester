# Day-Zero Forward Test Baseline

**Registration Date:** 2026-11-19  
**Strategy:** Canonical Indian Quantitative Ensemble (Protocol v1.1)  
**Evaluation Window:** 2026-11-19 → 2027-11-19 (Month 12)  
**Starting Capital:** ₹10,00,000.00  
**Day-Zero Net Equity (after 0.40% round-trip friction):** ₹9,98,128.35  
**Unallocated Cash:** ₹62,305.37 (6.2% cash drag from integer share allocation)  
**Active Holdings Count:** 44 stocks

---

## 1. Pre-Registered Benchmark Targets

### Primary Benchmark: Nifty 500 Total Return Index (TRI)
* **Instrument:** ICICI Prudential Nifty 500 Index Fund (Direct - Growth), AMFI Scheme Code: `153161`  
  *(Mandated by SEBI to track Nifty 500 TRI with all dividends reinvested).*
* **Day-Zero NAV (2026-11-18 EOD):** **10.6787**
* **Day-Zero Units Purchased (₹10,00,000 equivalent):** **93,644.3575 units**
* **Mechanical Month-12 Evaluation Formula:**
  $$\text{Benchmark Portfolio Value at Month 12} = 93,644.3575 \times \text{NAV}_{2027-11-19}$$
  $$\text{TRI Benchmark Net Return} = \frac{\text{Value} - 1,000,000}{1,000,000}$$

### Secondary Reference: Nifty 500 Price Index (`^CRSLDX`)
* **Closing Level (2026-11-18):** 23,630.25
* **Opening Level (2026-11-19):** 23,777.85

---

## 2. Canonical Initial Holdings (Clean Day-Zero Allocation)

All positions were allocated under the canonical equal 1/3 Momentum + 1/3 Low-Vol + 1/3 Mom/Vol ensemble, floored to whole shares with 0.20% entry friction:

| Symbol | Quantity | Buy Price (₹) | Total Deployed (₹) | Target Strategy Sleeve |
|---|:---:|:---:|:---:|---|
| **AETHER** | 20 | 1,662.70 | 33,320.51 | Momentum / Volatility |
| **ANANDRATHI** | 14 | 2,375.30 | 33,320.71 | Momentum / Volatility |
| **APARINDS** | 2 | 14,171.00 | 28,398.68 | Momentum / Volatility |
| **ATHERENERG** | 17 | 1,908.60 | 32,511.09 | Momentum / Volatility |
| **CPPLUS** | 8 | 3,989.20 | 31,977.43 | Momentum / Volatility |
| **HFCL** | 147 | 226.27 | 33,328.21 | Momentum / Volatility |
| **LAURUSLABS** | 14 | 2,338.00 | 32,797.46 | Momentum / Volatility |
| **MCX** | 8 | 3,705.40 | 29,702.49 | Momentum / Volatility |
| **MTARTECH** | 5 | 5,709.50 | 28,604.60 | Momentum / Volatility |
| **RUBICON** | 19 | 1,683.90 | 32,058.09 | Momentum / Volatility |
| **SANSERA** | 7 | 4,614.60 | 32,366.80 | Momentum / Volatility |
| **SHRIPISTON** | 7 | 4,322.10 | 30,315.21 | Momentum / Volatility |
| **STLTECH** | 82 | 405.15 | 33,288.74 | Momentum / Volatility |
| **SYRMA** | 23 | 1,433.90 | 33,045.66 | Momentum / Volatility |
| **WELCORP** | 14 | 2,260.20 | 31,706.09 | Momentum / Volatility |
| **ACUTAAS** | 4 | 3,942.90 | 15,803.14 | Low Volatility Sleeve |
| **AEGISLOG** | 13 | 1,211.60 | 15,782.30 | Momentum / Trend |
| **ALKEM** | 3 | 5,175.00 | 15,556.05 | Low Volatility Sleeve |
| **AUROPHARMA** | 9 | 1,794.10 | 16,179.19 | Momentum / Trend |
| **AZAD** | 7 | 2,364.80 | 16,586.71 | Momentum / Trend |
| **CASTROLIND** | 87 | 191.09 | 16,658.08 | Low Volatility Sleeve |
| **CIPLA** | 12 | 1,388.00 | 16,689.31 | Low Volatility Sleeve |
| **CRAFTSMAN** | 1 | 11,195.00 | 11,217.39 | Momentum / Trend |
| **FINCABLES** | 13 | 1,230.40 | 16,027.19 | Momentum / Trend |
| **GILLETTE** | 2 | 7,098.50 | 14,225.39 | Low Volatility Sleeve |
| **GLAND** | 5 | 3,248.40 | 16,274.48 | Momentum / Trend |
| **GODREJCP** | 18 | 894.50 | 16,133.20 | Low Volatility Sleeve |
| **HINDUNILVR** | 8 | 2,009.90 | 16,111.36 | Low Volatility Sleeve |
| **IPCALAB** | 9 | 1,834.40 | 16,542.62 | Low Volatility Sleeve |
| **IRCTC** | 37 | 449.35 | 16,659.20 | Low Volatility Sleeve |
| **JINDALSAW** | 64 | 258.79 | 16,595.69 | Momentum / Trend |
| **JSWCEMENT** | 132 | 125.94 | 16,657.33 | Low Volatility Sleeve |
| **LT** | 4 | 4,155.50 | 16,655.24 | Momentum / Trend |
| **LUPIN** | 8 | 1,950.00 | 15,631.20 | Low Volatility Sleeve |
| **NATCOPHARM** | 20 | 822.90 | 16,490.92 | Low Volatility Sleeve |
| **NTPC** | 51 | 321.80 | 16,444.62 | Low Volatility Sleeve |
| **ONGC** | 74 | 223.52 | 16,573.56 | Low Volatility Sleeve |
| **SBIN** | 15 | 1,108.60 | 16,662.26 | Low Volatility Sleeve |
| **SONACOMS** | 18 | 899.70 | 16,226.99 | Momentum / Trend |
| **SRF** | 6 | 2,479.40 | 14,906.15 | Low Volatility Sleeve |
| **SUNPHARMA** | 8 | 1,870.00 | 14,989.92 | Low Volatility Sleeve |
| **TORNTPHARM** | 3 | 4,668.80 | 14,034.41 | Low Volatility Sleeve |
| **UTIAMC** | 19 | 847.65 | 16,137.56 | Low Volatility Sleeve |
| **WELSPUNLIV** | 62 | 265.62 | 16,501.38 | Momentum / Trend |
| **CASH (Unallocated)**| — | — | **62,305.37** | Idle Cash Remainder |

**Total Day-Zero Portfolio Equity:** ₹9,98,128.35
