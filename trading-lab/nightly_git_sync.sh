#!/usr/bin/env bash
# nightly_git_sync.sh — Backs up paper ledger state and logs to git nightly.
set -euo pipefail

REPO_DIR="$HOME/ai-trader"
VIBE_DIR="$HOME/.vibe-trading"
SNAPSHOT_DIR="$REPO_DIR/audit_snapshots"

mkdir -p "$SNAPSHOT_DIR"
cp -f "$VIBE_DIR/india_account.json" "$SNAPSHOT_DIR/india_account.json" 2>/dev/null || true
cp -f "$VIBE_DIR/india_vol_account.json" "$SNAPSHOT_DIR/india_vol_account.json" 2>/dev/null || true
cp -f "$VIBE_DIR/heartbeat.log" "$SNAPSHOT_DIR/heartbeat.log" 2>/dev/null || true
cp -f "$VIBE_DIR/kill_rule_audit.log" "$SNAPSHOT_DIR/kill_rule_audit.log" 2>/dev/null || true

cd "$REPO_DIR"
git add -f audit_snapshots/
if ! git diff --cached --quiet; then
    git commit -m "audit: nightly ledger snapshot $(date -u +%Y-%m-%d)"
    git push origin main || echo "[WARN] git push failed" >&2
fi
