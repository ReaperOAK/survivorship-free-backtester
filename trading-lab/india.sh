#!/usr/bin/env bash
# Indian stock paper account (rupees). All pretend money.
#   ./trading-lab/india.sh status      # what you own & up/down
#   ./trading-lab/india.sh rebalance   # do this month's trades
#   ./trading-lab/india.sh start --cash 10000
cd /home/reaperoak/Documents/AI-Trader || exit 1
export TUSHARE_TOKEN=noop VIBE_TRADING_DATA_CACHE=1
exec .venv/bin/python trading-lab/india_ledger.py "$@"
