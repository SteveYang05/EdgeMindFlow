#!/bin/bash
# ComputerNet 自动化策略对比实验
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

export PYTHONPATH="$PROJECT_ROOT"
export EXPERIMENT_DURATION_SEC="${EXPERIMENT_DURATION_SEC:-30}"

echo "实验时长: ${EXPERIMENT_DURATION_SEC}s / 组"
echo "预计总时长: $(( EXPERIMENT_DURATION_SEC * 28 ))s (4场景 × 7策略)"
echo ""
echo "请确保已运行: bash scripts/start_all.sh"
echo ""

if [ -z "$CONDA_DEFAULT_ENV" ] || [ "$CONDA_DEFAULT_ENV" != "ComputerNet" ]; then
    echo "[提示] 建议先执行: conda activate ComputerNet"
fi

python scripts/run_experiment.py
