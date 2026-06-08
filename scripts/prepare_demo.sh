#!/bin/bash
# One-click demo prep: reset + experiment + report
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT"
export DEMO_EXPERIMENT_DURATION_SEC="${DEMO_EXPERIMENT_DURATION_SEC:-20}"

echo "Experiment duration: ${DEMO_EXPERIMENT_DURATION_SEC}s / group"
echo "Full matrix estimated: $(( DEMO_EXPERIMENT_DURATION_SEC * 12 ))s"
echo ""

python scripts/prepare_demo.py
