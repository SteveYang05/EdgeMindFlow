"""
IoT 设备模拟器主程序。

支持 HTTP fallback（默认）和 MQTT 两种通信方式。
通过环境变量 COMM_MODE 和 TASK_INTERVAL_SEC 配置。
"""
import json
import logging
import os
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from backend.common.config import (
    COMM_MODE,
    EDGE_PORT,
    MQTT_BROKER_HOST,
    MQTT_BROKER_PORT,
    TASK_INTERVAL_SEC,
)
from simulator.task_generator import (
    DEVICE_PROFILES,
    generate_emergency_smoke_task,
    generate_task,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [simulator] %(levelname)s: %(message)s",
)
logger = logging.getLogger("device_simulator")

EDGE_URL = os.getenv("EDGE_URL", f"http://localhost:{EDGE_PORT}")
DEVICES = list(DEVICE_PROFILES.keys())
EMERGENCY_MODE = os.getenv("EMERGENCY_MODE", "false").lower() == "true"


def submit_via_http(task: dict) -> bool:
    """HTTP Fallback 提交任务。"""
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(f"{EDGE_URL}/api/tasks/submit", json=task)
            if resp.status_code == 200:
                result = resp.json()
                logger.info(
                    "HTTP submit OK: %s | device=%s | decision=%s | latency=%.0fms",
                    task["task_id"],
                    task["device_id"],
                    result.get("decision"),
                    result.get("total_latency_ms", 0),
                )
                return True
            logger.warning("HTTP submit failed: %s", resp.status_code)
            return False
    except Exception as e:
        logger.error("HTTP submit error: %s", e)
        return False


def submit_via_mqtt(task: dict) -> bool:
    """MQTT 发布任务。"""
    try:
        import paho.mqtt.publish as publish
        topic = task["topic"]
        publish.single(
            topic,
            payload=json.dumps(task),
            hostname=MQTT_BROKER_HOST,
            port=MQTT_BROKER_PORT,
        )
        logger.info("MQTT publish OK: %s -> %s", task["task_id"], topic)
        return True
    except Exception as e:
        logger.warning("MQTT publish failed, fallback to HTTP: %s", e)
        return submit_via_http(task)


def submit_task(task: dict) -> bool:
    if COMM_MODE == "mqtt":
        ok = submit_via_mqtt(task)
        if not ok:
            return submit_via_http(task)
        return ok
    return submit_via_http(task)


def run_simulator():
    """主循环：周期性为各设备生成并上报任务。"""
    logger.info("Device Simulator started | COMM_MODE=%s | interval=%.1fs",
                COMM_MODE, TASK_INTERVAL_SEC)
    logger.info("Edge URL: %s", EDGE_URL)
    cycle = 0
    while True:
        try:
            if EMERGENCY_MODE or (cycle % 15 == 0 and random.random() < 0.1):
                task = generate_emergency_smoke_task()
                logger.warning("Generated EMERGENCY smoke alert task!")
            else:
                device_id = random.choice(DEVICES)
                task = generate_task(device_id)

            logger.info(
                "Generated task: %s | device=%s | type=%s | priority=%s | size=%.0fKB",
                task["task_id"],
                task["device_id"],
                task["task_type"],
                task["priority"],
                task["data_size_kb"],
            )
            submit_task(task)
            cycle += 1
            time.sleep(TASK_INTERVAL_SEC)
        except KeyboardInterrupt:
            logger.info("Simulator stopped.")
            break
        except Exception as e:
            logger.error("Simulator error: %s", e)
            time.sleep(2)


if __name__ == "__main__":
    run_simulator()
