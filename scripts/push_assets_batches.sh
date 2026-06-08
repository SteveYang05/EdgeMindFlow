#!/usr/bin/env bash
# 分批推送大文件到 GitHub，避免单次 upload 超时
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

git config http.postBuffer 524288000
git config http.version HTTP/1.1

push_batch() {
  local msg="$1"
  shift
  echo ""
  echo "========== $msg =========="
  git add "$@"
  git status --short
  git commit -m "$msg"
  for attempt in 1 2 3; do
    if git push origin main; then
      echo "[OK] pushed: $msg"
      return 0
    fi
    echo "[retry $attempt] push failed, wait 5s..."
    sleep 5
  done
  echo "[FAIL] $msg"
  return 1
}

IMG="$ROOT/data/images"
MDL="$ROOT/data/models"
RL="$MDL/rl_candidates"

push_batch "Add core model weights (late_learn, late_rl)" \
  "$MDL/late_learn.pkl" "$MDL/late_rl.pkl"

push_batch "Add RL candidate model ep20" \
  "$RL/late_rl_candidate_ep20_len100.pkl"

push_batch "Add RL candidate model ep50" \
  "$RL/late_rl_candidate_ep50_len100.pkl"

push_batch "Add strategy images batch 1 (local/cloud/edge)" \
  "$IMG/strategy_local_only.png" \
  "$IMG/strategy_cloud_only.png" \
  "$IMG/strategy_edge_only.png"

push_batch "Add strategy images batch 2 (static/offload/rl)" \
  "$IMG/strategy_static_rule.png" \
  "$IMG/strategy_late_offload.png" \
  "$IMG/strategy_late_rl.png"

push_batch "Add strategy image late_learn" \
  "$IMG/strategy_late_learn.png"

push_batch "Add scenario images batch 1 (normal/cloud_delay)" \
  "$IMG/scenario_normal.png" \
  "$IMG/scenario_cloud_delay.png"

push_batch "Add scenario images batch 2 (edge_overload/emergency)" \
  "$IMG/scenario_edge_overload.png" \
  "$IMG/scenario_emergency.png"

push_batch "Add workflow and framework images" \
  "$IMG/agentnet_workflow.png" \
  "$IMG/late_framework_layers.png"

echo ""
echo "All asset batches pushed."
