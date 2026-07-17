"""
explore_all.py — every strategy x every universe, across 26 years, from the store.

Reads the local DuckDB (zero API calls). For each (universe x strategy):
  * monthly rebalance, look-ahead safe (weights decided at month-end t, applied t+1)
  * 5bps turnover cost, long/flat, no leverage
  * outputs CAGR / Sharpe / MaxDD + a full TRADE LOG (what it held each month)

Universes: nifty50/100/200/500 (official membership) + 'full' (top-400 liquid).
Saves per-run trade logs + a summary matrix under ~/.vibe-trading/explore/.
"""
from __future__ import annotations
import os, itertools, warnings
import numpy as np
import pandas as pd
import duckdb

warnings.filterwarnings("ignore")
DB = os.path.expanduser("~/.vibe-trading/market.duckdb")
OUT = os.path.expanduser("~/.vibe-trading/explore")
os.makedirs(OUT, exist_ok=True)
COST, ANN = 0.0005, 252
START = "2005-01-01"   # deep-history window most Nifty500 names cover


# ---------- data (from store) ----------
def _con():
    return duckdb.connect(DB, read_only=True)


def universe_symbols(u):
    con = _con()
    if u == "full":
        cut = con.execute("SELECT MAX(date) FROM prices").fetchone()[0] - pd.Timedelta(days=90)
        rows = con.execute("""SELECT symbol FROM prices WHERE date>=? GROUP BY symbol
            HAVING AVG(close)>20 AND COUNT(*)>40 ORDER BY AVG(close*volume) DESC LIMIT 400""",
            [cut]).fetchall()
    else:
        rows = con.execute("SELECT symbol FROM index_members WHERE idx=?", [u]).fetchall()
    con.close()
    return [r[0] for r in rows]


def load_prices(symbols):
    con = _con()
    ph = ",".join(["?"] * len(symbols))
    df = con.execute(f"SELECT date,symbol,close FROM prices WHERE symbol IN ({ph}) "
                     f"AND date>=? ORDER BY date", [*symbols, START]).df()
    con.close()
    px = df.pivot(index="date", columns="symbol", values="close")
    px.index = pd.to_datetime(px.index)
    return px.ffill(limit=5).dropna(how="all")


# ---------- strategies (weight fn: ctx,t -> Series of weights) ----------
def _ctx(px):
    rets = px.pct_change()
    return dict(px=px, rets=rets, sma200=px.rolling(200).mean(),
                mom126=px / px.shift(126) - 1, car=px.shift(21) / px.shift(252) - 1,
                vol=rets.rolling(60).std())


def w_buyhold(c, t):
    cols = c["px"].columns
    v = c["px"].loc[t].notna()
    n = int(v.sum()); return pd.Series(np.where(v, 1.0 / max(n, 1), 0.0), index=cols)


def _trend_ok(c, t):
    return (c["px"].loc[t] > c["sma200"].loc[t]) & c["px"].loc[t].notna()


def w_trend(c, t):
    sel = _trend_ok(c, t); n = int(sel.sum())
    return pd.Series(np.where(sel, 1.0 / max(n, 1), 0.0), index=sel.index)


def w_tsmom(c, t):
    sel = (c["mom126"].loc[t] > 0) & c["px"].loc[t].notna(); n = int(sel.sum())
    return pd.Series(np.where(sel, 1.0 / max(n, 1), 0.0), index=sel.index)


def w_tsmom_iv(c, t):
    sel = (c["mom126"].loc[t] > 0) & c["px"].loc[t].notna()
    inv = (1 / c["vol"].loc[t]).where(sel, 0).replace([np.inf, -np.inf], 0).fillna(0)
    return inv / inv.sum() if inv.sum() > 0 else inv


def _xs(c, t, k, trend=False):
    car = c["car"].loc[t].dropna()
    if trend:
        car = car[_trend_ok(c, t).reindex(car.index).fillna(False) & (c["mom126"].loc[t].reindex(car.index) > 0)]
    top = car.sort_values(ascending=False).head(k).index
    w = pd.Series(0.0, index=c["px"].columns)
    if len(top):
        w[top] = 1.0 / k              # fixed 1/k -> partial cash if <k qualify
    return w


def w_xs10(c, t): return _xs(c, t, 10)
def w_xs20(c, t): return _xs(c, t, 20)
def w_xs20_trend(c, t): return _xs(c, t, 20, trend=True)


def w_lowvol(c, t, k=20):
    v = c["vol"].loc[t].dropna()
    v = v[c["px"].loc[t].reindex(v.index).notna()]
    pick = v.nsmallest(k).index
    w = pd.Series(0.0, index=c["px"].columns)
    if len(pick): w[pick] = 1.0 / len(pick)
    return w


STRATS = {"buy&hold": w_buyhold, "trend200": w_trend, "tsmom": w_tsmom,
          "tsmom_iv": w_tsmom_iv, "xsmom10": w_xs10, "xsmom20": w_xs20,
          "xsmom20_trend": w_xs20_trend, "lowvol20": w_lowvol}


# ---------- backtest ----------
def backtest(px, wfn):
    c = _ctx(px)
    idx = px.index
    rebals = [d for d in px.resample("ME").last().index if d in set(idx)]
    # NaN everywhere; set the COMPLETE weight vector (0s included) only on
    # rebalance dates, then ffill. This holds positions between rebalances WITHOUT
    # resurrecting dropped ones (a stock sold -> its 0 is carried forward, not lost).
    W = pd.DataFrame(np.nan, index=idx, columns=px.columns)
    log = []
    for t in rebals:
        if idx.get_loc(t) < 252:      # need warmup
            continue
        w = wfn(c, t).reindex(px.columns).fillna(0.0)
        W.loc[t] = w
        held = w[w > 0].sort_values(ascending=False)
        if len(held):
            log.append((t.date(), list(held.index), [round(float(x), 3) for x in held.values]))
    W = W.ffill().fillna(0.0)
    Wp = W.shift(1).fillna(0.0)
    turn = Wp.diff().abs().sum(axis=1).fillna(0.0)
    # DATA-ERROR GUARD: no real stock moves >35% in a day. Clip to neutralise
    # unadjusted-split glitches + the adjusted/unadjusted source seam. (Proper
    # fix = consistent split-adjusted data; this keeps the backtest from blowing
    # up on garbage. Results are robust-but-approximate until data is cleaned.)
    clean_rets = c["rets"].clip(-0.35, 0.35).fillna(0)
    r = (Wp * clean_rets).sum(axis=1) - turn * COST
    r = r[Wp.abs().sum(axis=1) > 0]   # from first invested day
    return r, log


def metrics(r):
    r = r.dropna()
    if len(r) < 60 or r.std() == 0:
        return dict(cagr=0, sharpe=0, maxdd=0, years=0)
    eq = (1 + r).cumprod(); yrs = len(r) / ANN
    return dict(cagr=eq.iloc[-1] ** (1 / yrs) - 1, sharpe=r.mean() / r.std() * np.sqrt(ANN),
                maxdd=(eq / eq.cummax() - 1).min(), years=yrs)


def main():
    universes = ["nifty50", "nifty100", "nifty200", "nifty500", "full"]
    rows = []
    px_cache = {}
    for u in universes:
        syms = universe_symbols(u)
        px = load_prices(syms)
        px_cache[u] = px
        print(f"\n### {u.upper()} — {px.shape[1]} stocks, {px.index[0].date()}..{px.index[-1].date()} ###", flush=True)
        print(f"{'strategy':16}{'CAGR':>8}{'Sharpe':>8}{'MaxDD':>8}{'yrs':>5}")
        print("-" * 45)
        for sname, wfn in STRATS.items():
            r, log = backtest(px, wfn)
            m = metrics(r)
            rows.append(dict(universe=u, strategy=sname, **m))
            print(f"{sname:16}{m['cagr']:>7.1%}{m['sharpe']:>8.2f}{m['maxdd']:>7.0%}{m['years']:>5.0f}")
            # save trade log
            if log:
                tl = pd.DataFrame([(d, ",".join(s), ",".join(map(str, w))) for d, s, w in log],
                                  columns=["month", "holdings", "weights"])
                tl.to_csv(f"{OUT}/trades_{u}_{sname}.csv", index=False)

    mat = pd.DataFrame(rows)
    mat.to_csv(f"{OUT}/summary_matrix.csv", index=False)
    print("\n\n================ BEST (by Sharpe) PER UNIVERSE ================")
    for u in universes:
        sub = mat[mat.universe == u].sort_values("sharpe", ascending=False).iloc[0]
        print(f"  {u:9} -> {sub['strategy']:14} Sharpe {sub['sharpe']:.2f}, "
              f"CAGR {sub['cagr']:.1%}, MaxDD {sub['maxdd']:.0%}")
    print(f"\nSaved: {OUT}/summary_matrix.csv + per-run trade logs (trades_<uni>_<strat>.csv)")


if __name__ == "__main__":
    main()
