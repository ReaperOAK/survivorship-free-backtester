#!/usr/bin/env bash
# Keeps the market data store fresh. Run daily via cron (after ~7pm IST, once
# NSE publishes the day's bhavcopy). Idempotent + safe to run multiple times.
cd /home/reaperoak/Documents/AI-Trader || exit 1
export TUSHARE_TOKEN=noop VIBE_TRADING_DATA_CACHE=1
LOG="$HOME/.vibe-trading/cron_update.log"
mkdir -p "$HOME/.vibe-trading"
echo "===== $(date) daily update =====" >> "$LOG"

# 1) daily: pull new bhavcopy days into the store (whole market, ~1 request/day)
.venv/bin/python trading-lab/data_store.py update >> "$LOG" 2>&1

# 2) weekly (Mondays): refresh Nifty index membership — NSE rebalances the
#    indices periodically, so constituents drift over time.
if [ "$(date +%u)" = "1" ]; then
  echo "-- refreshing Nifty index lists (weekly) --" >> "$LOG"
  .venv/bin/python trading-lab/data_store.py indexes >> "$LOG" 2>&1
fi

# 3) refresh the current "what to buy now" signal (validated strategies) so it
#    stays current off the freshly-updated store. Written to a file to read anytime.
SIG="$HOME/.vibe-trading/current_signal.txt"
{ echo "===== $(date) current signals ====="
  .venv/bin/python trading-lab/signal_engine.py nifty200 momentum_trend
  echo; .venv/bin/python trading-lab/signal_engine.py nifty200 lowvol
} > "$SIG" 2>/dev/null
echo "signal refreshed -> $SIG" >> "$LOG"
echo "done." >> "$LOG"
