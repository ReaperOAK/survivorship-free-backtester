# PRD — "Backtest Playground" (working title)
*An honest, educational strategy-backtesting tool for retail investors.*
Draft v0.1 · 2026-07-17 · Owner: ReaperOAK

---

## 0. The one-line pitch
A web app where a beginner picks a market and a strategy, sees **honest historical
backtests** (gains *and* worst drawdowns), learns *why* it works and why it's no
guarantee, and decides for themselves — a **tool + education product, not advice.**

## 1. Why this framing (READ FIRST — it constrains everything)
This is deliberately **NOT** an advisory/tips service. That line is load-bearing:

| We DO (legal — a "tool/edtech") | We DON'T (regulated — needs SEBI RIA license) |
|---|---|
| Show rule-based backtests + screens | Say "**you** should buy X" (personalized advice) |
| Present honest *historical* performance | Project future gains ("you'll make ₹Y in 20 yrs") |
| Educate on how/why strategies behave | Manage money / place trades for users |
| User interprets & acts themselves | Charge a fee *for the recommendation itself* |

**Three hard rules, non-negotiable:**
1. **No forward projections presented as expected returns.** Backtests overfit;
   past ≠ future. We show historical *ranges* and worst drawdowns, never "you might
   gain X in 1/5/10/20 years." (This is also the law: "past performance is not
   indicative of future results.")
2. **No personalized buy/sell recommendations.** We surface *"stocks currently
   passing the momentum rule you selected"* as **information**, with disclaimers.
3. **Only survivorship-corrected numbers are shown as performance.** The biased
   (today's-list) number may appear *only* when explicitly labeled "before
   survivorship correction," as a teaching contrast. This is our credibility edge —
   see §5a. Showing the fantasy number as if it were real would make us the thing
   we're trying to replace.

> ⚖️ **Blocking dependency:** before charging anyone, a 30-min review with a
> SEBI-RIA-savvy lawyer/CA to confirm the tool/advice boundary for our exact wording.
> This PRD assumes the tool side; legal sign-off gates launch.

## 2. Problem
Retail beginners (esp. in India) either (a) get scammed by unregulated "tip"
Telegram channels, or (b) have no honest, hands-on way to *understand* a strategy
before risking money. Backtesting tools exist but are pro-grade/intimidating and
often oversell returns. There's a gap for an **honest, beginner-friendly, "learn by
backtesting" sandbox.**

## 3. Target user
- **Primary:** Indian retail beginner, small capital (₹5k–₹1L), wants to invest
  systematically (often via SIP), doesn't know how to evaluate a strategy.
- Secondary: US/crypto retail with the same need.

## 4. Core user flow (honest version)
1. **Pick a market:** Indian stocks / US stocks / crypto. *(Start: Indian stocks.)*
2. **Enter capital + SIP:** "₹10,000 now, ₹10,000/month?" — used to compute
   **feasibility**, not projections.
3. **Minimum-balance gate (KEY, from the whole-share finding):**
   - **Every strategy carries a computed "minimum balance to run it"** — a
     first-class field, shown up front. Two thresholds: *bare* (can hold ≥1 whole
     share of each held name) and *comfortable* (whole-share rounding wastes <~10%).
   - Computed from the strategy's holding-count × the actual share prices it trades
     (see `trading-lab/min_balance.py`). Example (Indian momentum, live prices):
     **hold-6 ≈ ₹85k comfortable, hold-12 ≈ ₹1.7L comfortable.**
   - If the user's capital is **below the minimum**, the tool **says so plainly** and
     routes them to the **index fund/ETF path** (fractional units) until their SIP
     grows past it. Honesty as a feature, not a dead end.
4. **Show validated strategies** for that market with **honest history:**
   - Metrics shown *together*, drawdown as loud as return: CAGR, Sharpe, **worst
     drawdown**, **minimum balance to run it**, "what a SIP would have done"
     (factual, historical only).
   - Plain-English "how it works / why it's not a guarantee."
5. **Explore / screen:** user can see *which instruments currently pass the chosen
   rule* (information), toggle parameters, view the equity curve.
6. **User decides & acts on their own broker** (we never place trades in v1).
7. **Come back monthly:** re-open to see the current rule-based screen + track a
   (paper) portfolio. Framed as information + education.

## 5. MVP scope (v1)
- Market: **Indian stocks + Nifty index-fund/ETF path** (covers the small-account reality).
- **Universe selection (user-chosen, with pros/cons shown):** powered by stored
  NSE index membership (`data_store.index_symbols`). **Default = Nifty 500** — it is
  the honest best once survivorship is corrected (see §5a). The ⭐ moved from Nifty
  200 → Nifty 500 *because* of the correction: on the raw (biased) backtest Nifty 200
  looked best, but that was hindsight. **Corrected Sharpe** column below is the number
  we actually show users (momentum+trend, top-20, survivorship-corrected):

  | Universe | # | Corrected Sharpe | Pros | Cons | Best for |
  |---|---|---|---|---|---|
  | **Nifty 50** | 50 | ~0.76 | Safest, most liquid, blue-chips, low crash risk | Few names → weak selection; mega-cap heavy | Beginners / safety |
  | **Nifty 100** | 100 | ~0.53 | Very liquid large-caps | Too narrow — momentum needs breadth (weakest corrected) | Conservative buy-and-hold |
  | **Nifty 200** | 200 | ~0.86 | Real selection, still liquid | Raw looked best (1.48-1.74) but was survivorship fantasy | Balanced |
  | **Nifty 500** ⭐ | 500 | **~1.04** | Breadth survives the honesty test best — strongest *corrected* edge | Less-liquid small-caps, higher vol, needs more capital | **Best honest edge (default)** |
  | **Full market** | ~2,800 | untested | Maximum breadth | Illiquid micro-caps, extreme vol, picks speculative junk (proven) | Advanced only — high risk |
### 5a. Survivorship correction — the real moat (built, free)
Most retail backtesting tools quietly cheat: they run the strategy over *today's*
index members, so the backtest is implicitly holding stocks that we already know
survived and thrived. That inflates every number. We **corrected it for free** and
it's our honest-data edge:
- **`trading-lab/wayback_membership.py`** reconstructs *point-in-time* index
  membership ("who was actually in Nifty 100/200/500 back then") from the Internet
  Archive's snapshots of NSE's public constituent CSVs → `index_members_hist`.
- **`trading-lab/fetch_delisted.py`** recovers the *own* frozen price history of
  dropped/delisted names (the losers survivorship hides) from free Yahoo data —
  never substituting a successor ticker (that would fake the correction).
- **`trading-lab/survivorship_pit.py`** runs biased-vs-corrected side by side.

**What it revealed (momentum+trend, top-20):** the raw "best" (Nifty 200, Sharpe
~1.48–1.74) was fantasy; corrected, Nifty 200 is only ~0.86 and **Nifty 500 is the
honest winner at ~1.04** (≈24%/yr, −38% worst drop). Note the number *firmed down*
from ~1.20 → ~1.04 the moment we folded in recovered delisted losers (IL&FSTRANS,
JETAIRWAYS, Future Group…) via `fetch_delisted.py` — the more complete the loser
data, the more honest (lower) the edge. We show the **corrected** number everywhere
(`signal_engine.CORRECTED_STATS`); the raw one only ever appears labeled "before
survivorship correction" to teach the concept. *Caveat we still disclose:* ~15% of
ever-members are truly defunct with no free price (DHFL, merged PSU banks), so the
true edge is a hair lower still.

- Strategies: **momentum (hold-N)** + **buy-and-hold index** baseline. (Reuse
  `trading-lab/india_research.py`, `india_signal.py`.) Each strategy ships with its
  **survivorship-corrected** Sharpe / CAGR / MaxDD, never the biased number.
- Honest backtest view: equity curve, CAGR/Sharpe/**MaxDD**, **minimum balance to
  run it** (`min_balance.py`), SIP-vs-lumpsum, worst-year, "past performance ≠
  future" banner everywhere.
- **Fund/ETF finder** (for small accounts *and* people who prefer funds — "safer"):
  - **Index funds/ETFs — an objective "best" is defensible:** rank by *expense
    ratio ↓, tracking error ↓, liquidity/AUM ↑*. An index fund's whole job is to
    track cheaply, so cheapest+tightest ≈ genuinely best. (Data: AMFI/mfapi NAVs +
    yfinance ETF prices — confirmed available, free.)
  - **Active funds — NO "best" prediction:** show factual expense ratio, historical
    risk/drawdown, past return *with the "past ≠ future" caveat* — user compares.
    (Ranking active funds by past return = the misleading trap; we don't do it.)
- Whole-share + fractional-fund awareness baked into feasibility.
- Paper portfolio tracker (reuse `india_ledger.py` logic, whole-share).
- Accounts, disclaimers/ToS, no real-money execution.

## 6. What we reuse (already built in `trading-lab/`)
- `india_research.py` / `india_k_sweep.py` — the honest multi-strategy backtests.
- `india_signal.py` — the current-signal ("which stocks pass the rule") engine.
- `india_ledger.py` (whole-share) — paper portfolio + SIP simulation.
- `vectorbt` — the fast backtest engine behind it all.
- Data: yfinance (`.NS`), cached. (Verify data-vendor ToS for commercial use — see risks.)

## 7. Non-goals (v1 — explicitly out)
- ❌ Forward return projections of any kind.
- ❌ Personalized buy/sell recommendations / "tips."
- ❌ Placing real trades / broker integration (revisit post-legal, likely v2+ as
  optional user-initiated execution via *their own* Upstox keys).
- ❌ Crypto/US at launch (add after Indian MVP + legal clarity).

## 8. Monetization
- **Not $1/mo** — payment fees (~₹25–40 / $0.30–0.50 per charge) would eat ~half.
- **Freemium:** free tier (1 market, core backtests, paper tracker) →
  **Pro ~₹300–500/mo (~$5–8)** or discounted **annual** (all markets, custom
  strategies, full history, alerts, exports). Annual = better cash flow + less churn.
- 3-month free trial is fine as an *acquisition* lever; price the paid tier for
  real value, not a race to $1.

## 9. Risks & open questions
| Risk | Severity | Note |
|---|---|---|
| **SEBI RIA / advice boundary** | 🔴 Critical | Gates launch. Lawyer review first. Keep strictly "tool/info." |
| Misleading-performance liability | 🔴 High | No projections; drawdowns prominent; disclaimers everywhere. |
| Data vendor commercial ToS | 🟠 Med | **Pipeline BUILT & proven** (`data_store.py`): NSE **bhavcopy** (public, bulk, 1 req/day = whole market) → **DuckDB** store (2,808 stocks × **26 yrs**, ~132MB, zero repeat calls) + gentle yfinance seed + mfapi fund NAVs + **free Wayback point-in-time membership** (survivorship fixed for ₹0). Bhavcopy = NSE's own public data (more defensible than scraping Yahoo). Still: confirm commercial-use terms; yfinance/Yahoo is *personal-use* only, so keep it as a seed we don't redistribute. |
| **Reselling the raw data** ⚠️ | 🔴 High | Tempting (we assembled data others find hard to get) but **the raw feed is mostly NOT ours to sell**: NSE asserts IPR over bhavcopy/prices (redistribution needs an NSE/DotEx data licence), NIFTY constituents are NSE Indices' IP, and Yahoo/yfinance is personal-use-only per ToS. Selling it invites a cease-&-desist from a very large exchange. **Safer monetisation = sell the *tool and the corrected results/reports* (transformative outputs on the user's own screen), not the dataset.** The moat is the *survivorship-correction engine*, not a data dump. Decide with the same lawyer as the SEBI review. |
| **Unconstrained-universe risk** | 🟠 Med | Full-market momentum picks speculative small-caps (40-84% vol). Product defaults to **Nifty 500** (best *corrected* edge, still index-membered) with full-market as an explicit *aggressive* opt-in; small accounts routed to the ETF path. |
| Backtest overfitting sold as "best" | 🟠 Med | Show out-of-sample + drawdowns; educate, don't hype. |
| Small-account futility | 🟢 Handled | Feasibility check + ETF path is a feature, not a flaw. |

**Open questions:** legal entity/structure? which licensed data vendor? do we ever
add user-initiated execution? free-trial length vs. abuse?

## 10. Rough roadmap
- **Phase 0:** legal review (advice boundary) + data-vendor decision. *(gate)*
- **Phase 1 (MVP):** Indian stocks + index path, honest backtest UI, paper tracker,
  freemium plumbing. Reuse `trading-lab/`.
- **Phase 2:** more markets, custom strategies, alerts, annual plans.
- **Phase 3 (maybe):** optional user-initiated Upstox execution (their keys), still
  never "advice."

---
*This PRD deliberately trades "exciting projections + tips" for "honest tool +
education." That's the version that's legal, defensible, and actually helps users —
and it reuses ~everything we've already built.*
