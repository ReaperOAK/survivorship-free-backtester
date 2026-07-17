#!/usr/bin/env bash
# Simple wrapper so you never touch Python/env directly.
# Usage:
#   ./trading-lab/trade.sh status      # show your account (what you own, up/down)
#   ./trading-lab/trade.sh rebalance   # do this month's trades
#   ./trading-lab/trade.sh start --cash 100   # (re)open the account
cd /home/reaperoak/Documents/AI-Trader || exit 1
export TUSHARE_TOKEN=noop VIBE_TRADING_DATA_CACHE=1
exec .venv/bin/python trading-lab/paper_ledger.py "$@"
