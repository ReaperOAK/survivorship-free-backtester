"""
strategy_tournament.py — the honest strategy bake-off. Runs a big matrix of
strategies, weightings, combinations, overlays, and invented ensembles through the
SURVIVORSHIP-CORRECTED engine (point-in-time membership via Wayback), so we compare
edges honestly instead of fooling ourselves with today's-list fantasy numbers.

Everything here is cross-sectional (rank the whole universe, hold the best) — the
exact thing TradingView/Pine can't do. Costs (0.05%/turnover), whole-universe
point-in-time membership, drawdowns, and turnover are all reported.

  python strategy_tournament.py [nifty500|nifty200|nifty100] [topk]
"""
from __future__ import annotations
import os, sys, warnings
import numpy as np
import pandas as pd
import duckdb

warnings.filterwarnings("ignore")
DB = os.path.expanduser("~/.vibe-trading/market.duckdb")
COST, ANN, EPS = 0.0005, 252, 1e-9


# ---------- data + point-in-time universe ----------
def load(idx):
    con = duckdb.connect(DB, read_only=True)
    hist = con.execute("SELECT snap_date, symbol FROM index_members_hist WHERE idx=?", [idx]).df()
    hist["snap_date"] = pd.to_datetime(hist["snap_date"])
    snaps = {d: set(g["symbol"]) for d, g in hist.groupby("snap_date")}
    snap_dates = sorted(snaps)
    today = {x[0] for x in con.execute("SELECT symbol FROM index_members WHERE idx=?", [idx]).fetchall()}
    ever = sorted(set(hist["symbol"]) | today)
    store = {x[0] for x in con.execute("SELECT DISTINCT symbol FROM prices").fetchall()}
    have = [s for s in ever if s in store]
    ph = ",".join(["?"] * len(have))
    start = (snap_dates[0] - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    df = con.execute(f"SELECT date,symbol,close FROM prices WHERE symbol IN ({ph}) AND date>=? ORDER BY date",
                     have + [start]).df()
    con.close()
    px = df.pivot(index="date", columns="symbol", values="close").ffill(limit=5)
    px.index = pd.to_datetime(px.index)
    px = px[px.index <= snap_dates[-1] + pd.Timedelta(days=31)]

    def pit(t):
        prior = [d for d in snap_dates if d <= t]
        return snaps[prior[-1]] if prior else snaps[snap_dates[0]]

    return px, pit, len(have), len(ever)


def indicators(px):
    return dict(sma200=px.rolling(200).mean(),
                mom6=px / px.shift(126) - 1,
                car=px.shift(21) / px.shift(252) - 1,          # Carhart 12m-1m
                vol=px.pct_change().rolling(60).std() * np.sqrt(ANN),
                above=px > px.rolling(200).mean())


def rebal_dates(px):
    return [t for t in px.resample("ME").last().index
            if t in px.index and px.index.get_loc(t) >= 252]


# ---------- weight builders (each returns a monthly-set, ffilled daily W) ----------
def build_W(px, ind, uni_fn, kind, k=20, gate=True, weight="equal"):
    W = pd.DataFrame(np.nan, index=px.index, columns=px.columns)
    for t in rebal_dates(px):
        w = pd.Series(0.0, index=px.columns)
        uni = [s for s in uni_fn(t) if s in px.columns]
        if uni:
            if kind == "buyhold":
                sel = [s for s in uni if pd.notna(px.loc[t, s])]
                if sel:
                    w[sel] = 1.0 / len(sel)
            elif kind == "trend":                              # hold all uni above SMA200
                sel = [s for s in uni if bool(ind["above"].loc[t, s])]
                if sel:
                    w[sel] = 1.0 / len(sel)
            else:
                if kind == "car":
                    sc = ind["car"].loc[t, uni]
                elif kind == "mom6":
                    sc = ind["mom6"].loc[t, uni]
                elif kind == "momvol":                         # momentum per unit risk
                    sc = ind["car"].loc[t, uni] / (ind["vol"].loc[t, uni] + EPS)
                elif kind == "lowvol":
                    sc = -ind["vol"].loc[t, uni]
                sc = sc.dropna()
                if gate:
                    ok = ind["above"].loc[t, uni] & (ind["mom6"].loc[t, uni] > 0)
                    sc = sc[ok.reindex(sc.index).fillna(False)]
                top = sc.nlargest(k).index
                if len(top):
                    if weight == "ivol":
                        iv = (1.0 / (ind["vol"].loc[t, top] + EPS))
                        w[top] = (iv / iv.sum()).values
                    else:                                       # equal, 1/k -> partial cash if < k qualify
                        w[top] = 1.0 / k
        W.loc[t] = w
    return W.ffill().fillna(0.0)


# ---------- performance ----------
def returns(px, W):
    rets = px.pct_change().clip(-0.35, 0.35).fillna(0)
    Wp = W.shift(1).fillna(0)
    turn = Wp.diff().abs().sum(axis=1).fillna(0)
    r = (Wp * rets).sum(axis=1) - turn * COST
    inv = Wp.abs().sum(axis=1) > 0
    return r[inv], turn[inv]


def market_regime(px):
    """Broad equal-weight proxy trend filter (go to cash when proxy < its SMA200)."""
    proxy = (1 + px.pct_change().clip(-0.35, 0.35).mean(axis=1).fillna(0)).cumprod()
    on = proxy > proxy.rolling(200).mean()
    return on


def vol_manage(r, target=0.15):
    """Scale a return stream toward target vol, capped at 1x (no leverage, no look-ahead)."""
    rv = r.rolling(20).std() * np.sqrt(ANN)
    s = (target / (rv + EPS)).clip(0, 1).shift(1)
    return (r * s).dropna()


def stats(r, turn=None, years=None):
    r = r.dropna(); eq = (1 + r).cumprod(); yrs = len(r) / ANN
    d = dict(cagr=eq.iloc[-1] ** (1 / yrs) - 1, sharpe=r.mean() / r.std() * np.sqrt(ANN),
             maxdd=(eq / eq.cummax() - 1).min())
    d["turn"] = (turn.sum() / yrs) if turn is not None else np.nan   # annual 2-way turnover
    return d


# ---------- the tournament ----------
def main():
    idx = sys.argv[1] if len(sys.argv) > 1 else "nifty500"
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    px, pit, have, ever = load(idx)
    ind = indicators(px)
    regime = market_regime(px)

    # base strategies: (label, kind, k, gate, weight)
    specs = [
        ("buy&hold (all members)",       "buyhold", k, False, "equal"),
        ("trend200 (all>SMA200)",        "trend",   k, False, "equal"),
        (f"mom Carhart k{k} (no gate)",  "car",     k, False, "equal"),
        (f"mom+trend k{k} ★",            "car",     k, True,  "equal"),
        ("mom+trend k10",                "car",     10, True, "equal"),
        ("mom+trend k30",                "car",     30, True, "equal"),
        (f"mom+trend k{k} inv-vol wt",   "car",     k, True,  "ivol"),
        (f"mom6+trend k{k}",             "mom6",    k, True,  "equal"),
        (f"lowvol k{k}",                 "lowvol",  k, False, "equal"),
        (f"mom/vol+trend k{k}",          "momvol",  k, True,  "equal"),
    ]

    results = {}
    Ws = {}
    for label, kind, kk, gate, wt in specs:
        W = build_W(px, ind, pit, kind, k=kk, gate=gate, weight=wt)
        r, turn = returns(px, W)
        results[label] = stats(r, turn)
        Ws[label] = (W, r)

    # ---- invented combos / overlays ----
    base_lbl = f"mom+trend k{k} ★"
    Wbase, rbase = Ws[base_lbl]

    # 1) regime cash overlay on the champion base
    r_reg = (rbase * regime.shift(1).reindex(rbase.index).fillna(True)).dropna()
    _, turn_base = returns(px, Wbase)
    results[f"{base_lbl} + regime-cash"] = stats(r_reg, turn_base)

    # 2) volatility-managed champion (target 15%, no leverage)
    results[f"{base_lbl} + vol-managed"] = stats(vol_manage(rbase), turn_base)

    # 3) ensemble: average weights of momentum, low-vol, mom/vol (diversify the signal)
    Wens = (Ws[base_lbl][0] + Ws[f"lowvol k{k}"][0] + Ws[f"mom/vol+trend k{k}"][0]) / 3.0
    r_ens, turn_ens = returns(px, Wens)
    results["ENSEMBLE mom+lowvol+momvol"] = stats(r_ens, turn_ens)

    # 4) ensemble + regime overlay (the "kitchen sink")
    r_ens_reg = (r_ens * regime.shift(1).reindex(r_ens.index).fillna(True)).dropna()
    results["ENSEMBLE + regime-cash"] = stats(r_ens_reg, turn_ens)

    # 5) ensemble + vol-managed
    results["ENSEMBLE + vol-managed"] = stats(vol_manage(r_ens), turn_ens)

    # ---- report, ranked by honest Sharpe ----
    w0, w1 = px.index.min().date(), px.index.max().date()
    print(f"\nHONEST strategy tournament — {idx} point-in-time ({have}/{ever} priced), {w0}..{w1}")
    print(f"(survivorship-corrected, costs {COST:.2%}/turnover, monthly rebalance)\n")
    print(f"{'#':>2}  {'strategy':32}{'Sharpe':>7}{'CAGR':>8}{'MaxDD':>7}{'Turn/yr':>9}")
    print("-" * 66)
    ranked = sorted(results.items(), key=lambda kv: (kv[1]["sharpe"] if pd.notna(kv[1]["sharpe"]) else -9),
                    reverse=True)
    for i, (label, s) in enumerate(ranked, 1):
        star = "  <<" if s["sharpe"] == ranked[0][1]["sharpe"] else ""
        print(f"{i:>2}  {label:32}{s['sharpe']:>7.2f}{s['cagr']:>7.1%}{s['maxdd']:>7.0%}"
              f"{s['turn']:>8.0%}{star}")
    print(f"\nMaxDD = worst peak-to-trough. Turn/yr = 2-way annual turnover (higher = more cost/tax).")
    print(f"Past performance is NOT indicative of future results.")


if __name__ == "__main__":
    main()
