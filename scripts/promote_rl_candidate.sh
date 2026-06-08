#!/usr/bin/env bash
# 将指定 RL 候选提升为主模型（需用户显式传入 candidate_name）
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

CANDIDATE="${1:-}"
if [ -z "$CANDIDATE" ]; then
  echo "Usage: bash scripts/promote_rl_candidate.sh <candidate_name>"
  echo "Example: bash scripts/promote_rl_candidate.sh ep100_len200_safety_boost"
  exit 1
fi

SRC_PKL="data/models/rl_candidates/late_rl_candidate_${CANDIDATE}.pkl"
SRC_META="data/models/rl_candidates/late_rl_candidate_${CANDIDATE}_metadata.json"
DST_PKL="data/models/late_rl.pkl"
DST_META="data/models/late_rl_metadata.json"

if [ ! -f "$SRC_PKL" ]; then
  echo "Error: candidate not found: $SRC_PKL"
  echo "Available candidates:"
  ls -1 data/models/rl_candidates/late_rl_candidate_*.pkl 2>/dev/null | sed 's|.*/late_rl_candidate_||;s|\.pkl||' || true
  exit 1
fi

BACKUP_DIR="data/models/backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

if [ -f "$DST_PKL" ]; then
  cp "$DST_PKL" "$BACKUP_DIR/late_rl.pkl"
  echo "Backed up $DST_PKL -> $BACKUP_DIR/"
fi
if [ -f "$DST_META" ]; then
  cp "$DST_META" "$BACKUP_DIR/late_rl_metadata.json"
fi

cp "$SRC_PKL" "$DST_PKL"
if [ -f "$SRC_META" ]; then
  cp "$SRC_META" "$DST_META"
fi

echo "Promoted candidate '$CANDIDATE' to main model."
echo "Backup saved to: $BACKUP_DIR"
echo ""
echo "Reload RL model in running Edge server:"
echo "  curl -X POST http://localhost:8000/api/rl/reload"
