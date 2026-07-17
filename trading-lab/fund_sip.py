"""
fund_sip.py — LIVE paper-trading account for the validated two-fund SIP plan:
  Rs 1,000/month into a plain Nifty 500 index fund  +  Rs 1,000/month into Nifty 500 Momentum 50.

Buys REAL fund units at REAL NAVs (mfapi.in, free, EOD). Mutual-fund units are
FRACTIONAL, so Rs 1,000 always fully invests — no whole-share problem.

Strategy = baseline SIP with the F3 dip-rule: on the monthly buy, if the market is
>10% below its peak BUT still above its 200-day trend (a pullback in an uptrend, not a
crash), send the whole Rs 2,000 to the momentum fund that month; otherwise Rs1k/Rs1k.

Separate from the research account (india_account.json) — this one lives at
~/.vibe-trading/fund_sip_account.json.

  python fund_sip.py start     # open the account + do the first month's SIP
  python fund_sip.py status    # mark-to-market report (plain English)
  python fund_sip.py sip        # force a contribution now (manual)
  python fund_sip.py cron       # idempotent: invest once per new month, else just refresh
"""
from __future__ import annotations
import os, sys, json, time
import httpx

ACCOUNT = os.path.expanduser("~/.vibe-trading/fund_sip_account.json")
MONTHLY = 1000.0                      # rupees per fund per month
FUNDS = {                            # sleeve -> (mfapi scheme code, human name)
    "plain":    ("153161", "ICICI Pru Nifty 500 Index (Direct-Growth)"),
    "momentum": ("153244", "Axis Nifty 500 Momentum 50 (Direct-Growth)"),
}


def _today():
    return time.strftime("%Y-%m-%d")


def _month():
    return time.strftime("%Y-%m")


def fetch_nav(code):
    """Latest NAV + date from mfapi.in (retries). Returns (nav, date) or (None, None)."""
    for _ in range(3):
        try:
            d = httpx.get(f"https://api.mfapi.in/mf/{code}", timeout=30).json()
            row = d["data"][0]
            return float(row["nav"]), row["date"]
        except Exception:
            time.sleep(2)
    return None, None


def market_state():
    """(risk_on, drawdown) from our store; None if unavailable (F3 falls back to Rs1k/Rs1k)."""
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        import signal_engine as se
        return se.market_state("nifty500")
    except Exception as e:
        print(f"  (market state unavailable, using plain Rs1k/Rs1k split: {e})")
        return None


def load_acct():
    return json.load(open(ACCOUNT)) if os.path.exists(ACCOUNT) else None


def save_acct(a):
    os.makedirs(os.path.dirname(ACCOUNT), exist_ok=True)
    json.dump(a, open(ACCOUNT, "w"), indent=2)


def start():
    if load_acct():
        print("Account already exists. Use status / sip / cron.")
        return load_acct()
    a = {"opened": _today(), "monthly_per_fund": MONTHLY,
         "funds": {k: {"code": c, "name": n, "units": 0.0, "invested": 0.0,
                       "last_nav": None, "last_nav_date": None} for k, (c, n) in FUNDS.items()},
         "last_sip_month": None, "history": []}
    save_acct(a)
    print(f"Opened a NEW paper SIP account at {ACCOUNT}\n(research account is untouched.)\n")
    return do_sip(a)


def _allocation():
    """F3 dip-rule -> how to split this month's Rs 2,000."""
    ms = market_state()
    if ms and ms["risk_on"] and ms["drawdown"] <= -0.10:
        print(f"  F3 DIP-RULE: market {ms['drawdown']:.0%} off peak but still in uptrend "
              f"-> full Rs {2*MONTHLY:,.0f} into MOMENTUM this month.")
        return {"plain": 0.0, "momentum": 2 * MONTHLY}, ms
    if ms:
        state = "risk-ON" if ms["risk_on"] else "risk-OFF (below 200-day trend)"
        print(f"  Market: {state}, {ms['drawdown']:.0%} off peak -> normal Rs{MONTHLY:,.0f}/Rs{MONTHLY:,.0f} split.")
    return {"plain": MONTHLY, "momentum": MONTHLY}, ms


def do_sip(a):
    alloc, _ = _allocation()
    # need NAVs for any sleeve we're buying
    navs = {}
    for k, amt in alloc.items():
        if amt <= 0:
            continue
        nav, date = fetch_nav(a["funds"][k]["code"])
        if nav is None:
            print(f"  Could not fetch NAV for {a['funds'][k]['name']} — skipping SIP, will retry next run.")
            return a
        navs[k] = (nav, date)
    for k, amt in alloc.items():
        if amt <= 0:
            continue
        nav, date = navs[k]
        units = amt / nav
        f = a["funds"][k]
        f["units"] += units; f["invested"] += amt
        f["last_nav"], f["last_nav_date"] = nav, date
        a["history"].append({"date": _today(), "fund": k, "amount": amt,
                             "nav": round(nav, 4), "units": round(units, 4)})
        print(f"  BOUGHT Rs {amt:,.0f} of {f['name']} @ NAV Rs {nav:.4f} = {units:.4f} units")
    a["last_sip_month"] = _month()
    save_acct(a)
    return a


def refresh_navs(a):
    for k, f in a["funds"].items():
        nav, date = fetch_nav(f["code"])
        if nav is not None:
            f["last_nav"], f["last_nav_date"] = nav, date
    save_acct(a)


def _report(a):
    print("=" * 60)
    print(f"FUND SIP PAPER ACCOUNT (INR)   (opened {a['opened']})")
    print("=" * 60)
    tot_inv = tot_val = 0.0
    for k, f in a["funds"].items():
        nav = f["last_nav"] or 0.0
        val = f["units"] * nav
        tot_inv += f["invested"]; tot_val += val
        gain = val - f["invested"]
        print(f"{f['name']}")
        print(f"   {f['units']:.4f} units | invested Rs {f['invested']:,.0f} | "
              f"NAV Rs {nav:.4f} ({f['last_nav_date']}) | worth Rs {val:,.0f} "
              f"({'+' if gain >= 0 else ''}Rs {gain:,.0f})")
    pnl = tot_val - tot_inv
    pct = pnl / tot_inv * 100 if tot_inv else 0
    print("-" * 60)
    print(f"TOTAL invested: Rs {tot_inv:,.0f}   |   TOTAL value: Rs {tot_val:,.0f}")
    print(f"You are {'UP' if pnl >= 0 else 'DOWN'} Rs {abs(pnl):,.0f} ({'+' if pnl>=0 else ''}{pct:.1f}%). "
          f"{len([h for h in a['history']])} buys since {a['opened']}.")
    print("=" * 60)
    print("Paper money. Monthly SIP. Past != future.")


def status(a):
    refresh_navs(a)
    _report(a)


def cron(a):
    if a["last_sip_month"] != _month():
        print(f"[{_today()}] New month ({_month()}) — running SIP:")
        a = do_sip(a)
    else:
        print(f"[{_today()}] SIP for {_month()} already done — refreshing values only.")
        refresh_navs(a)
    _report(a)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    a = load_acct()
    if cmd == "start":
        start()
    elif a is None:
        print("No account yet. Run: python fund_sip.py start")
    elif cmd == "sip":
        do_sip(a); _report(a)
    elif cmd == "cron":
        cron(a)
    else:
        status(a)


if __name__ == "__main__":
    main()
