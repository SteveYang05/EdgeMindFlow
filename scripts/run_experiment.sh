#!/bin/bash
# ComputerNet automated strategy comparison experiment
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

export PYTHONPATH="$PROJECT_ROOT"
export EXPERIMENT_DURATION_SEC="${EXPERIMENT_DURATION_SEC:-30}"

echo "Experiment duration: ${EXPERIMENT_DURATION_SEC}s / group"
echo "Estimated total: $(( EXPERIMENT_DURATION_SEC * 28 ))s (4 scenarios × 7 strategies)"
echo ""
echo "Ensure you have run: bash scripts/start_all.sh"
echo ""

if [ -z "$CONDA_DEFAULT_ENV" ] || [ "$CONDA_DEFAULT_ENV" != "ComputerNet" ]; then
    echo "[Note] Recommended: conda activate ComputerNet"
fi

python scripts/run_experiment.py
