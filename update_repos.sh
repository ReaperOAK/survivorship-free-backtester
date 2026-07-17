#!/usr/bin/env bash
# update_repos.sh — keep third-party REFERENCE repos current, safely.
# Fast-forward ONLY: never merges, never commits, never clobbers local edits.
# Diverged / locally-modified repos are skipped with a note, so it's always safe.
#
# Usage: ./update_repos.sh [dir-containing-the-clones]   (default: current directory)
ROOT="${1:-$PWD}"
cd "$ROOT" 2>/dev/null || { echo "no such dir: $ROOT"; exit 1; }
echo "===== $(date '+%Y-%m-%d %H:%M') updating reference repos in $ROOT ====="
found=0
for d in */; do
  [ -d "${d}.git" ] || continue
  git -C "$d" remote get-url origin >/dev/null 2>&1 || continue
  found=$((found+1))
  printf "  %-34s " "${d%/}"
  out=$(git -C "$d" pull --ff-only --no-tags 2>&1)
  if   echo "$out" | grep -qiE "up to date";        then echo "up to date"
  elif echo "$out" | grep -qiE "Updating|Fast-forw"; then echo "UPDATED"
  else echo "skipped (local changes / diverged — pull manually)"; fi
done
[ "$found" = 0 ] && echo "  (no git clones found here)"
echo "done."
