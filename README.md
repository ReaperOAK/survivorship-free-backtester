# AI-Trader Lab

**Honest, survivorship-corrected backtesting + paper trading for Indian equities — built entirely on free data.**

This is a personal research lab, not investment advice. Everything here is educational,
runs on pretend money, and shows drawdowns as loudly as returns. *Past performance is not
indicative of future results.*

---

## Why this exists

Most retail backtests quietly lie — they test the *past* using *today's* winning stocks
(survivorship bias), assume fractional shares that don't exist, and ignore tax. This lab
was built to do the honest version, using only free data sources, and to run a live paper
account against the result.

## What's genuinely built here

| Piece | File | What it does |
|---|---|---|
| **Data store** | `trading-lab/data_store.py` | DuckDB store of ~2,800 NSE stocks × 26 years. Bulk **NSE bhavcopy** ingest (1 request/day = whole market) + gentle yfinance deep-history seed. Zero repeat API calls. |
| **Survivorship correction** | `trading-lab/wayback_membership.py`, `fetch_delisted.py`, `survivorship_pit.py` | Reconstructs *point-in-time* Nifty 100/200/500 membership from the Internet Archive, recovers delisted-loser prices, and re-runs backtests honestly. The correction is real: raw momentum "Sharpe ~1.5" → **~1.0 corrected**. |
| **Strategy tournament** | `trading-lab/strategy_tournament.py` | ~15 strategies + ensembles/overlays, all survivorship-corrected. Winner: **ensemble + regime-cash** (blend momentum/low-vol/risk-adjusted-momentum, go to cash below the 200-day trend). |
| **After-tax simulator** | `trading-lab/aftertax_sim.py` | Lot-level FIFO with real Indian tax (20% STCG / 12.5% LTCG). Shows tax is the great equalizer between active strategies and buy-and-hold. |
| **Signal engine** | `trading-lab/signal_engine.py` | App-ready "what to hold now" from the store, with the corrected + after-tax stats attached so a fantasy number can't be shown. |
| **Live paper accounts** | `trading-lab/fund_sip.py`, `india_ledger.py` | (1) Two-fund monthly SIP into real Nifty 500 index + Momentum 50 funds (fractional units, real NAVs from mfapi.in). (2) Direct-stock ensemble-regime ledger. Both idempotent, cron-driven. |
| **SIP strategy research** | `trading-lab/sip_strategies.py`, `sip_robustness.py` | Tests dip-buying / rebalancing / regime overlays on a monthly SIP, after tax — and stress-tests whether the "edge" is real or just factor exposure. |
| **Product spec** | `PRD.md` | An honest, tool-not-advice backtesting product concept (avoids SEBI RIA regulation; no forward projections). |

## Honest headline findings

- Survivorship inflates momentum by roughly **+0.4 to +0.9 Sharpe** depending on universe.
- Corrected, the best universe is **Nifty 500** (breadth survives the correction), ~1.0–1.2 Sharpe.
- **Ensemble + regime-cash** roughly halves drawdown (−38% → ~−18%) — insurance, not free alpha.
- After Indian tax, high-turnover strategies barely out-earn buy-and-hold; the win is a *smoother ride*.
- Intraday and daily "buy-the-dip" tricks die under honest testing (costs / factor-exposure in disguise).

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# build the data store (first run pulls history; then it's local + free forever)
.venv/bin/python trading-lab/data_store.py backfill
.venv/bin/python trading-lab/data_store.py indexes
# see the current honest signal
.venv/bin/python trading-lab/signal_engine.py nifty500 ensemble_regime
```

Live paper accounts run via cron (see the `*.sh` wrappers — adjust the hard-coded paths
for your machine). Account state and the data store live under `~/.vibe-trading/` and are
**git-ignored** — never commit them.

## Data sources (all free)

NSE bhavcopy · Yahoo Finance (`yfinance`) · [mfapi.in](https://www.mfapi.in) fund NAVs ·
Internet Archive (point-in-time index membership) · Kaggle historical Nifty-50 weights.

## Standing on other people's shoulders (credits)

This lab was prototyped while studying these excellent open-source projects. The genuine
work here is the honest data pipeline, survivorship correction, and the tests above — but
the ideas were sharpened against:

- [HKUDS/Vibe-Trading](https://github.com/HKUDS/Vibe-Trading)
- [paperswithbacktest/awesome-systematic-trading](https://github.com/paperswithbacktest/awesome-systematic-trading)
- [stefan-jansen/machine-learning-for-trading](https://github.com/stefan-jansen/machine-learning-for-trading)
- [polakowo/vectorbt](https://github.com/polakowo/vectorbt)

## Disclaimer

Educational research only. Not investment advice, not a recommendation to buy or sell any
security. No forward return projections. Paper money throughout. Do your own research and
consult a SEBI-registered adviser before investing real money.
