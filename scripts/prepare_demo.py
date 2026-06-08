#!/usr/bin/env python3
"""One-click demo prep: clear data, run experiments, export report."""
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
    print(" ComputerNet demo data preparation")
    print("========================================")

    # Step 1: Reset
    print("\n[Step 1] Resetting demo data...")
    subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "reset_demo_data.py")], check=True)

    # Step 2: Check services
    print("\n[Step 2] Checking services...")
    if not check_services():
        print("\n[Error] Edge/Cloud Server is not running!")
        print("  Run first: bash scripts/start_all.sh")
        sys.exit(1)
    print("  Edge + Cloud services OK")

    # Step 3: Run experiment matrix
    print(f"\n[Step 3] Running experiment matrix ({duration}s per group)...")
    results = run_full_experiment(duration_sec=duration, quick=quick)

    # Step 4: Export report
    print("\n[Step 4] Exporting experiment report...")
    subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "export_report.py")], check=True)

    print("\n========================================")
    print(" Demo preparation complete!")
    print("------------------------------------------")
    print(f"  Dashboard:  http://localhost:{FRONTEND_PORT}")
    print(f"  Edge API:   {EDGE_SERVER_URL}/docs")
    print(f"  Report:     {RESULTS_DIR / 'report.md'}")
    print(f"  Experiment CSV: {RESULTS_DIR / 'experiment_summary.csv'}")
    print(f"  Experiment groups: {len(results)}")
    print("------------------------------------------")
    print(" Suggested Dashboard data view: Recent 100 or Latest Experiment")
    print("========================================")


if __name__ == "__main__":
    main()
