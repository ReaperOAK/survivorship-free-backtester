#!/usr/bin/env bash
# Cron wrapper for the two-fund SIP paper account. Idempotent monthly SIP + daily value refresh.
cd /home/reaperoak/Documents/AI-Trader || exit 1
exec ./.venv/bin/python trading-lab/fund_sip.py "${1:-cron}"
