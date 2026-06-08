#!/bin/bash
# 演示前一键准备：重置 + 实验 + 报告
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT"
export DEMO_EXPERIMENT_DURATION_SEC="${DEMO_EXPERIMENT_DURATION_SEC:-20}"

echo "实验时长: ${DEMO_EXPERIMENT_DURATION_SEC}s / 组"
echo "完整矩阵预计: $(( DEMO_EXPERIMENT_DURATION_SEC * 12 ))s"
echo ""

python scripts/prepare_demo.py
