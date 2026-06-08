#!/usr/bin/env python3
"""ComputerNet 自动化策略对比实验脚本。"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("PYTHONPATH", str(PROJECT_ROOT))

from backend.edge_server.experiment_runner import run_full_experiment
from backend.common.config import EXPERIMENT_DURATION_SEC


def main():
    duration = int(os.getenv("EXPERIMENT_DURATION_SEC", str(EXPERIMENT_DURATION_SEC)))
    quick = os.getenv("EXPERIMENT_QUICK", "").lower() in ("1", "true", "yes")
    try:
        results = run_full_experiment(duration_sec=duration, quick=quick)
        print(f"\n实验完成，共 {len(results)} 组结果。")
        sys.exit(0)
    except RuntimeError as e:
        print(f"\n[错误] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n实验被中断。")
        sys.exit(130)


if __name__ == "__main__":
    main()
