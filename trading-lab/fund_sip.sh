#!/usr/bin/env bash
# Two-fund SIP paper account. Idempotent monthly SIP + daily value refresh.
# Expects a venv at the repo root (.venv) — see README.
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || exit 1
exec .venv/bin/python trading-lab/fund_sip.py "${1:-cron}"
