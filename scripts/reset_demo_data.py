#!/usr/bin/env python3
"""重置演示用数据库与缓存指标。"""
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
    """通过 API 重置运行时状态（场景/策略/内存指标）。"""
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(f"{EDGE_SERVER_URL}/api/scenario/normal")
            client.post(f"{EDGE_SERVER_URL}/api/strategy/dynamic")
            client.post(f"{EDGE_SERVER_URL}/api/demo/reset_state")
            return True
    except Exception as e:
        print(f"[提示] Edge Server 未运行，跳过 API 重置: {e}")
        return False


def main():
    print("========================================")
    print(" ComputerNet 演示数据重置")
    print("========================================")

    backup_path = db.backup_database()
    print(f"[1/4] 数据库已备份: {backup_path}")

    cleared = db.reset_demo_tables()
    print(f"[2/4] 表已清空: {cleared}")

    db.insert_alert(
        task_id="demo_reset",
        device_id="system",
        message="Demo data reset completed. Ready for presentation.",
        alert_category="system",
        alert_level="info",
        alert_type="system_event",
    )
    print("[3/4] 已写入 system/info 重置事件")

    api_ok = reset_via_api()
    print(f"[4/4] API 状态重置: {'成功' if api_ok else '跳过（请重启服务或手动切换场景/策略）'}")

    print("\n重置完成。建议接下来运行:")
    print("  DEMO_EXPERIMENT_DURATION_SEC=20 bash scripts/prepare_demo.sh")
    print("========================================")


if __name__ == "__main__":
    main()
