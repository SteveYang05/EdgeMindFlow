"""Synthetic trace-like datasets — fallback when small dataset download fails."""
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

TASK_TYPES = [
    ("temperature_report", "low", 2, 0.1, 5000),
    ("humidity_report", "low", 2, 0.1, 5000),
    ("smoke_alert", "high", 5, 0.4, 300),
    ("image_detection", "high", 512, 0.8, 500),
    ("access_control", "medium", 8, 0.3, 800),
    ("periodic_stats", "low", 50, 0.5, 10000),
]

DEVICES = [
    "temperature_sensor_01", "humidity_sensor_01", "smoke_sensor_01",
    "camera_01", "access_control_01",
]


def generate_mec_edge_synthetic(path: Path, rows: int = 500) -> Dict:
    """Generate MEC-like edge compute task trace CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    base_time = datetime.utcnow()
    fieldnames = [
        "timestamp", "device_id", "task_type", "priority",
        "data_size_kb", "compute_cost", "deadline_ms",
        "edge_cpu_load", "network_delay_ms",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for i in range(rows):
            tt, pri, size, cost, ddl = random.choice(TASK_TYPES)
            w.writerow({
                "timestamp": (base_time + timedelta(seconds=i * 2)).isoformat() + "Z",
                "device_id": random.choice(DEVICES),
                "task_type": tt,
                "priority": pri,
                "data_size_kb": round(size * random.uniform(0.8, 1.2), 2),
                "compute_cost": round(cost * random.uniform(0.9, 1.1), 3),
                "deadline_ms": int(ddl * random.uniform(0.9, 1.1)),
                "edge_cpu_load": round(random.uniform(0.2, 0.9), 3),
                "network_delay_ms": round(random.uniform(30, 120), 1),
            })
    return {"path": str(path), "rows": rows, "source": "synthetic", "kind": "mec_edge"}


def generate_eua_synthetic(path: Path, rows: int = 200) -> Dict:
    """Generate EUA-like edge user allocation trace CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "user_id", "latitude", "longitude", "edge_node_id",
        "request_rate", "avg_data_size_kb", "avg_compute_cost",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for i in range(rows):
            w.writerow({
                "user_id": f"user_{i:04d}",
                "latitude": round(39.9 + random.uniform(-0.05, 0.05), 6),
                "longitude": round(116.3 + random.uniform(-0.05, 0.05), 6),
                "edge_node_id": f"edge_{random.randint(1, 5)}",
                "request_rate": round(random.uniform(0.1, 2.0), 3),
                "avg_data_size_kb": round(random.uniform(2, 256), 2),
                "avg_compute_cost": round(random.uniform(0.05, 0.8), 3),
            })
    return {"path": str(path), "rows": rows, "source": "synthetic", "kind": "eua"}


def generate_synthetic_for(name: str, dest: Path) -> Dict:
    if name == "mec_edge":
        return generate_mec_edge_synthetic(dest)
    if name == "eua":
        return generate_eua_synthetic(dest)
    raise ValueError(f"No synthetic template for {name}")
