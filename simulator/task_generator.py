"""Task generator — produce tasks with different characteristics per device type."""
import uuid
from datetime import datetime
from typing import Dict


DEVICE_PROFILES = {
    "temperature_sensor_01": {
        "task_type": "temperature_report",
        "priority": "low",
        "data_size_kb": 2.0,
        "compute_cost": 0.1,
        "deadline_ms": 3000,
    },
    "humidity_sensor_01": {
        "task_type": "humidity_report",
        "priority": "low",
        "data_size_kb": 2.0,
        "compute_cost": 0.1,
        "deadline_ms": 3000,
    },
    "smoke_sensor_01": {
        "task_type": "smoke_alert",
        "priority": "high",
        "data_size_kb": 5.0,
        "compute_cost": 0.4,
        "deadline_ms": 200,
    },
    "camera_01": {
        "task_type": "image_detection",
        "priority": "high",
        "data_size_kb": 512.0,
        "compute_cost": 0.8,
        "deadline_ms": 500,
    },
    "access_control_01": {
        "task_type": "access_control",
        "priority": "medium",
        "data_size_kb": 8.0,
        "compute_cost": 0.25,
        "deadline_ms": 800,
    },
}


def generate_task(device_id: str, override: Dict = None) -> dict:
    """Generate one task for the specified device."""
    profile = DEVICE_PROFILES.get(device_id, {
        "task_type": "periodic_stats",
        "priority": "medium",
        "data_size_kb": 10.0,
        "compute_cost": 0.3,
        "deadline_ms": 1000,
    })
    if override:
        profile = {**profile, **override}

    task_id = f"task_{uuid.uuid4().hex[:12]}"
    topic = f"smart_park/devices/{device_id}/tasks"

    return {
        "task_id": task_id,
        "device_id": device_id,
        "task_type": profile["task_type"],
        "priority": profile["priority"],
        "data_size_kb": profile["data_size_kb"],
        "compute_cost": profile["compute_cost"],
        "deadline_ms": profile["deadline_ms"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "topic": topic,
    }


def generate_emergency_smoke_task() -> dict:
    """Generate emergency smoke alert task (for emergency scenario demo)."""
    return generate_task("smoke_sensor_01", {
        "priority": "high",
        "deadline_ms": 150,
        "compute_cost": 0.5,
    })
