"""
daily_heartbeat.py — Automated daily health check, watchdog & dead-man's switch.

Runs daily via cron after market close (17:30 UTC / 23:00 IST).
Checks:
  1. DuckDB price freshness: tightened to 1 business day (skips weekends and NSE holidays).
  2. Ledger integrity: verifies india_account.json and india_vol_account.json.
  3. External Dead-Man's Switch: pings healthchecks.io (or custom URL) on success.
     If the OCI instance dies or is reclaimed, healthchecks.io alerts the user.
  4. Push Alerting: sends immediate webhook/Telegram alert on any failure.
  5. Appends status to ~/.vibe-trading/heartbeat.log and exits with code 1 on failure.

Configuration:
  Set environment variables or create ~/.vibe-trading/alerts.json:
  {
    "healthchecks_url": "https://hc-ping.com/<your-uuid>",
    "webhook_url": "https://discord.com/api/webhooks/...",
    "telegram_bot_token": "...",
    "telegram_chat_id": "..."
  }
"""
from __future__ import annotations
import os, sys, time, json
import urllib.request
import urllib.error
import duckdb
import pandas as pd

ACCOUNT = os.path.expanduser("~/.vibe-trading/india_account.json")
VOL_ACCOUNT = os.path.expanduser("~/.vibe-trading/india_vol_account.json")
DB = os.path.expanduser("~/.vibe-trading/market.duckdb")
LOG = os.path.expanduser("~/.vibe-trading/heartbeat.log")
ALERT_CONFIG = os.path.expanduser("~/.vibe-trading/alerts.json")

# Standard NSE Market Holidays (2026 reference)
NSE_HOLIDAYS_2026 = {
    "2026-01-26", "2026-03-03", "2026-03-26", "2026-04-03", "2026-04-14",
    "2026-05-01", "2026-06-26", "2026-08-15", "2026-08-27", "2026-10-02",
    "2026-10-20", "2026-11-08", "2026-11-10", "2026-11-24", "2026-12-25"
}


def load_config() -> dict:
    cfg = {}
    if os.path.exists(ALERT_CONFIG):
        try:
            with open(ALERT_CONFIG) as f:
                cfg = json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to read {ALERT_CONFIG}: {e}", file=sys.stderr)
    # Environment variables override config file
    if os.environ.get("HEALTHCHECKS_URL"):
        cfg["healthchecks_url"] = os.environ["HEALTHCHECKS_URL"]
    if os.environ.get("ALERT_WEBHOOK_URL"):
        cfg["webhook_url"] = os.environ["ALERT_WEBHOOK_URL"]
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        cfg["telegram_bot_token"] = os.environ["TELEGRAM_BOT_TOKEN"]
    if os.environ.get("TELEGRAM_CHAT_ID"):
        cfg["telegram_chat_id"] = os.environ["TELEGRAM_CHAT_ID"]
    return cfg


def send_ping(url: str, fail: bool = False, msg: str = ""):
    if not url:
        return
    target = url.rstrip("/") + ("/fail" if fail else "")
    try:
        data = msg.encode("utf-8") if (fail and msg) else None
        req = urllib.request.Request(target, data=data, headers={"User-Agent": "ai-trader-heartbeat/1.1"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass
    except Exception as e:
        print(f"[WARN] Dead-man's switch ping to {target} failed: {e}", file=sys.stderr)


def send_push_alert(cfg: dict, message: str):
    # 1. Telegram
    bot_token = cfg.get("telegram_bot_token")
    chat_id = cfg.get("telegram_chat_id")
    if bot_token and chat_id:
        tg_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = json.dumps({"chat_id": chat_id, "text": f"🚨 [AI-TRADER ALERT]\n{message}"}).encode("utf-8")
        try:
            req = urllib.request.Request(tg_url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10):
                pass
        except Exception as e:
            print(f"[WARN] Telegram alert delivery failed: {e}", file=sys.stderr)

    # 2. Webhook (Discord / Slack)
    hook_url = cfg.get("webhook_url")
    if hook_url:
        payload = json.dumps({"content": f"🚨 **[AI-TRADER HEARTBEAT FAILURE]**\n{message}"}).encode("utf-8")
        try:
            req = urllib.request.Request(hook_url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10):
                pass
        except Exception as e:
            print(f"[WARN] Webhook alert delivery failed: {e}", file=sys.stderr)


def get_expected_trading_day(now_dt: pd.Timestamp) -> pd.Timestamp.date:
    """Determine the latest expected NSE trading date based on current time (IST)."""
    # Convert now to IST (UTC+5:30)
    ist = now_dt.tz_convert("Asia/Kolkata") if now_dt.tzinfo else (now_dt + pd.Timedelta(hours=5, minutes=30))
    # If after 18:00 IST on a weekday, today's close should be ingested
    candidate = ist.date()
    if ist.hour < 18:
        candidate -= pd.Timedelta(days=1)
    
    # Roll back past weekends and holidays
    while candidate.weekday() >= 5 or candidate.strftime("%Y-%m-%d") in NSE_HOLIDAYS_2026:
        candidate -= pd.Timedelta(days=1)
    return candidate


def check_heartbeat():
    now_utc = pd.Timestamp.now("UTC")
    now_ts = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    expected_trade_date = get_expected_trading_day(now_utc)
    issues = []
    cfg = load_config()

    # 1. Check DuckDB freshness (tightened to 1 business day)
    max_dt = None
    if not os.path.exists(DB):
        issues.append(f"CRITICAL: DuckDB missing at {DB}")
    else:
        try:
            con = duckdb.connect(DB, read_only=True)
            max_dt = con.execute("SELECT max(date) FROM prices").fetchone()[0]
            con.close()
            if max_dt is None:
                issues.append("CORRUPT: DuckDB prices table is completely empty")
            else:
                # Count missing trading days
                if max_dt < expected_trade_date:
                    # Calculate business day lag
                    cur = max_dt + pd.Timedelta(days=1)
                    missing_b_days = 0
                    while cur <= expected_trade_date:
                        if cur.weekday() < 5 and cur.strftime("%Y-%m-%d") not in NSE_HOLIDAYS_2026:
                            missing_b_days += 1
                        cur += pd.Timedelta(days=1)
                    if missing_b_days > 1:
                        issues.append(
                            f"STALE DATA: DuckDB latest close is {max_dt}; expected {expected_trade_date} "
                            f"({missing_b_days} trading days behind — daily stop rule blind!)"
                        )
        except Exception as e:
            issues.append(f"DUCKDB ERROR: {e}")

    # 2. Check Primary Ledger Freshness & Integrity
    acct_positions, acct_cash = {}, 0.0
    if not os.path.exists(ACCOUNT):
        issues.append(f"CRITICAL: Primary account missing at {ACCOUNT}")
    else:
        try:
            with open(ACCOUNT) as f:
                acct = json.load(f)
            acct_positions = acct.get("positions", {})
            acct_cash = acct.get("cash", 0.0)
            if not acct_positions and acct_cash <= 0:
                issues.append("CORRUPTED ACCOUNT: Primary account has zero cash and zero positions")
        except Exception as e:
            issues.append(f"ACCOUNT JSON ERROR: {e}")

    # 3. Check Vol Ledger Integrity
    vol_positions, vol_cash = {}, 0.0
    if os.path.exists(VOL_ACCOUNT):
        try:
            with open(VOL_ACCOUNT) as f:
                vol_acct = json.load(f)
            vol_positions = vol_acct.get("positions", {})
            vol_cash = vol_acct.get("cash", 0.0)
            if not vol_positions and vol_cash <= 0:
                issues.append("CORRUPTED ACCOUNT: Vol account has zero cash and zero positions")
        except Exception as e:
            issues.append(f"VOL ACCOUNT JSON ERROR: {e}")

    # 4. Formulate Verdict
    status = "HEALTHY" if not issues else "ALERT"
    entry = f"[{now_ts}] Status: {status}"
    if issues:
        entry += f" | Issues: {'; '.join(issues)}"
    else:
        entry += (
            f" | Store: {max_dt} (Expected: {expected_trade_date}) "
            f"| Main Book: {len(acct_positions)} pos, Cash: Rs {acct_cash:,.2f} "
            f"| Vol Book: {len(vol_positions)} pos, Cash: Rs {vol_cash:,.2f}"
        )

    print(entry)
    with open(LOG, "a") as f:
        f.write(entry + "\n")

    # 5. External Dead-Man's Switch & Push Notification
    hc_url = cfg.get("healthchecks_url")
    if not hc_url and not cfg.get("webhook_url") and not cfg.get("telegram_bot_token"):
        print(
            "[NOTICE] No external dead-man's switch or webhook configured in ~/.vibe-trading/alerts.json. "
            "If this OCI instance terminates, failures will go unnotified.", 
            file=sys.stderr
        )

    if issues:
        if hc_url:
            send_ping(hc_url, fail=True, msg="; ".join(issues))
        send_push_alert(cfg, "\n".join(issues))
        sys.exit(1)
    else:
        if hc_url:
            send_ping(hc_url, fail=False)


if __name__ == "__main__":
    check_heartbeat()
