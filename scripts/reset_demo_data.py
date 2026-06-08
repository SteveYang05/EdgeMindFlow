#!/usr/bin/env python3
"""Reset demo database and cached metrics."""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("PYTHONPATH", str(PROJECT_ROOT))

import httpx

from backend.common.config import EDGE_SERVER_URL
from backend.edge_server import database as db


def reset_via_api():
    """Reset runtime state via API (scenario/strategy/in-memory metrics)."""
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(f"{EDGE_SERVER_URL}/api/scenario/normal")
            client.post(f"{EDGE_SERVER_URL}/api/strategy/dynamic")
            client.post(f"{EDGE_SERVER_URL}/api/demo/reset_state")
            return True
    except Exception as e:
        print(f"[Note] Edge Server not running, skipping API reset: {e}")
        return False


def main():
    print("========================================")
    print(" ComputerNet demo data reset")
    print("========================================")

    backup_path = db.backup_database()
    print(f"[1/4] Database backed up: {backup_path}")

    cleared = db.reset_demo_tables()
    print(f"[2/4] Tables cleared: {cleared}")

    db.insert_alert(
        task_id="demo_reset",
        device_id="system",
        message="Demo data reset completed. Ready for presentation.",
        alert_category="system",
        alert_level="info",
        alert_type="system_event",
    )
    print("[3/4] Wrote system/info reset event")

    api_ok = reset_via_api()
    print(f"[4/4] API state reset: {'OK' if api_ok else 'skipped (restart services or switch scenario/strategy manually)'}")

    print("\nReset complete. Suggested next steps:")
    print("  DEMO_EXPERIMENT_DURATION_SEC=20 bash scripts/prepare_demo.sh")
    print("========================================")


if __name__ == "__main__":
    main()
