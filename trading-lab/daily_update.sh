#!/usr/bin/env bash
# Keep the market data store fresh (bhavcopy daily, index lists weekly, signal refresh).
# Idempotent + safe to run multiple times. Run daily via cron after NSE publishes bhavcopy.
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || exit 1
export TUSHARE_TOKEN=noop VIBE_TRADING_DATA_CACHE=1
LOG="$HOME/.vibe-trading/cron_update.log"
mkdir -p "$HOME/.vibe-trading"
echo "===== $(date) daily update =====" >> "$LOG"
.venv/bin/python trading-lab/data_store.py update >> "$LOG" 2>&1
if [ "$(date +%u)" = "1" ]; then
  echo "-- refreshing Nifty index lists (weekly) --" >> "$LOG"
  .venv/bin/python trading-lab/data_store.py indexes >> "$LOG" 2>&1
fi
SIG="$HOME/.vibe-trading/current_signal.txt"
{ echo "===== $(date) current signal (champion) ====="
  .venv/bin/python trading-lab/signal_engine.py nifty500 ensemble_regime
} > "$SIG" 2>/dev/null
echo "done." >> "$LOG"
