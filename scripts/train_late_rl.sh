#!/bin/bash
# LATE-RL CPU 训练
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT"
export RL_TRAIN_EPISODES="${RL_TRAIN_EPISODES:-200}"
export RL_EPISODE_LENGTH="${RL_EPISODE_LENGTH:-200}"
export RL_RANDOM_SEED="${RL_RANDOM_SEED:-42}"
python scripts/train_late_rl.py
