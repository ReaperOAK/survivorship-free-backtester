#!/usr/bin/env bash
# Legacy US $100 paper account wrapper.
#   ./trading-lab/trade.sh status | rebalance | start --cash 100
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || exit 1
export TUSHARE_TOKEN=noop VIBE_TRADING_DATA_CACHE=1
exec .venv/bin/python trading-lab/paper_ledger.py "$@"
