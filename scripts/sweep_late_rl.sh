#!/usr/bin/env bash
# LATE-RL candidate training sweep — save to data/models/rl_candidates/, do not overwrite main model
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [ "${RL_SWEEP_FAST:-0}" = "1" ]; then
  echo "[sweep] FAST mode: ep20_len100, ep50_len100"
else
  echo "[sweep] FULL mode: ep50/100/200_len200, ep100_len400 (+ optional extra profiles)"
fi

python scripts/sweep_late_rl.py "$@"
