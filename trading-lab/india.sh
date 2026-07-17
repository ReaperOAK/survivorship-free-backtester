#!/usr/bin/env bash
# Indian-stock paper account (rupees; pretend money).
#   ./trading-lab/india.sh status | rebalance | cron | start --cash 1000000
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || exit 1
export TUSHARE_TOKEN=noop VIBE_TRADING_DATA_CACHE=1
exec .venv/bin/python trading-lab/india_ledger.py "$@"
