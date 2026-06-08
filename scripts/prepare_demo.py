#!/usr/bin/env python3
"""演示前一键：清数据、跑实验、导出报告。"""
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("PYTHONPATH", str(PROJECT_ROOT))

import httpx

from backend.common.config import (
    CLOUD_SERVER_URL,
    DEMO_EXPERIMENT_DURATION_SEC,
    EDGE_SERVER_URL,
    FRONTEND_PORT,
    RESULTS_DIR,
)
from backend.edge_server.experiment_runner import check_services, run_full_experiment


def main():
    duration = int(os.getenv("DEMO_EXPERIMENT_DURATION_SEC", str(DEMO_EXPERIMENT_DURATION_SEC)))
    quick = os.getenv("PREPARE_QUICK", "").lower() in ("1", "true", "yes")

    print("========================================")
    print(" ComputerNet 演示数据准备")
    print("========================================")

    # Step 1: Reset
    print("\n[Step 1] 重置演示数据...")
    subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "reset_demo_data.py")], check=True)

    # Step 2: Check services
    print("\n[Step 2] 检查服务...")
    if not check_services():
        print("\n[错误] Edge/Cloud Server 未运行!")
        print("  请先执行: bash scripts/start_all.sh")
        sys.exit(1)
    print("  Edge + Cloud 服务正常")

    # Step 3: Run experiment matrix
    print(f"\n[Step 3] 运行实验矩阵 (每组 {duration}s)...")
    results = run_full_experiment(duration_sec=duration, quick=quick)

    # Step 4: Export report
    print("\n[Step 4] 导出实验报告...")
    subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "export_report.py")], check=True)

    print("\n========================================")
    print(" 演示准备完成!")
    print("------------------------------------------")
    print(f"  Dashboard:  http://localhost:{FRONTEND_PORT}")
    print(f"  Edge API:   {EDGE_SERVER_URL}/docs")
    print(f"  报告:       {RESULTS_DIR / 'report.md'}")
    print(f"  实验 CSV:   {RESULTS_DIR / 'experiment_summary.csv'}")
    print(f"  实验组数:   {len(results)}")
    print("------------------------------------------")
    print(" 建议 Dashboard 数据视图选择: Recent 100 或 Latest Experiment")
    print("========================================")


if __name__ == "__main__":
    main()
