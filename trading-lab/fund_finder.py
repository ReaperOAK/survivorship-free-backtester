"""
fund_finder.py — objective "best index fund" ranker (defensible, not advice).

For an INDEX fund, "best" is objective: it should track the index as tightly as
possible, as cheaply as possible. We rank Nifty-50 index funds by:
  * TRACKING ERROR (annualised std of daily NAV-return minus index-return) - lower
    is better; a well-run, low-cost fund tracks tightly.
  * 1-year return (sanity; index funds should cluster near the index).
Data: mfapi.in (free MF NAVs) + yfinance ^NSEI benchmark. Facts only; a user
picks. (Expense ratio needs AMFI/Value-Research - noted as a TODO field.)
"""
from __future__ import annotations
import os, time, warnings
import numpy as np
import pandas as pd
import httpx

warnings.filterwarnings("ignore")
ANN = 252


def mfget(url, retries=4):
    for a in range(retries):
        try:
            return httpx.get(url, timeout=40).json()
        except Exception:
            time.sleep(3 + a * 2)
    return None


def fund_navs(code):
    d = mfget(f"https://api.mfapi.in/mf/{code}")
    if not d or not d.get("data"):
        return None, None
    df = pd.DataFrame(d["data"])
    df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    s = df.dropna().set_index("date")["nav"].sort_index()
    return s, d["meta"].get("scheme_name", str(code))


def benchmark():
    os.environ.setdefault("TUSHARE_TOKEN", "noop")
    from backtest.loaders.registry import LOADER_REGISTRY, _ensure_registered
    _ensure_registered()
    end = (pd.Timestamp.utcnow().normalize() - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    df = LOADER_REGISTRY["yfinance"]().fetch(["^NSEI"], "2023-06-01", end, interval="1D").get("^NSEI")
    s = df["close"].astype(float); s.index = pd.to_datetime(s.index)
    return s.sort_index()


def metrics(nav, bench):
    j = pd.concat([nav.rename("f"), bench.rename("b")], axis=1).dropna()
    j = j[j.index >= (j.index.max() - pd.Timedelta(days=400))]
    if len(j) < 150:
        return None
    fr, br = j["f"].pct_change().dropna(), j["b"].pct_change().dropna()
    te = float((fr - br).std() * np.sqrt(ANN))                    # tracking error
    yr = float(j["f"].iloc[-1] / j["f"].iloc[0] - 1)              # ~1y return
    yb = float(j["b"].iloc[-1] / j["b"].iloc[0] - 1)
    return dict(tracking_error=te, ret_1y=yr, bench_1y=yb)


def main():
    print("Finding Nifty-50 index funds (Direct-Growth)...\n")
    # mfapi search is per-AMC-ish; sweep major AMCs and aggregate the plain funds
    def is_plain(name):
        n = name.lower()
        return ("nifty 50 index" in n and "direct" in n and "growth" in n
                and not any(x in n for x in
                    ("500", "100", "momentum", "value", "next", "equal", "quality",
                     "alpha", "low", "midcap", "smallcap", "bank", "idcw")))
    seen, picks = set(), []
    for amc in ["UTI", "HDFC", "SBI", "ICICI", "Nippon", "Axis", "Tata", "DSP",
                "Bandhan", "Motilal", "Kotak", "Aditya"]:
        for f in (mfget(f"https://api.mfapi.in/mf/search?q={amc} Nifty 50") or []):
            if is_plain(f["schemeName"]) and f["schemeCode"] not in seen:
                seen.add(f["schemeCode"]); picks.append(f)
        time.sleep(0.3)
    print(f"({len(picks)} plain Nifty-50 index funds matched across AMCs)\n")
    bench = benchmark()
    rows = []
    for f in picks:
        nav, name = fund_navs(f["schemeCode"])
        if nav is None:
            continue
        m = metrics(nav, bench)
        if m:
            rows.append((name, m["tracking_error"], m["ret_1y"], m["bench_1y"]))
        time.sleep(0.5)
    rows.sort(key=lambda r: r[1])   # best = lowest tracking error
    print(f"{'Fund (Direct-Growth)':52}{'TrackErr':>9}{'1y ret':>8}")
    print("-" * 70)
    for name, te, yr, yb in rows:
        star = "  <-- tightest" if rows and te == rows[0][1] else ""
        print(f"{name[:50]:52}{te:>8.1%}{yr:>8.1%}{star}")
    if rows:
        print(f"\nNifty 50 index itself (1y): {rows[0][3]:+.1%}")
    print("Lower tracking error = follows the index more faithfully = better index fund.")
    print("(Expense ratio would refine this — needs AMFI/Value-Research data. Facts, not advice.)")


if __name__ == "__main__":
    main()
