"""Automated strategy comparison experiments."""
import csv
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import httpx

from backend.common.config import (
    CLOUD_SERVER_URL,
    EDGE_SERVER_URL,
    EXPERIMENT_DURATION_SEC,
    RESULTS_DIR,
)
from backend.edge_server import database as db

SCENARIOS = ["normal", "cloud_delay", "edge_overload", "emergency"]
STRATEGIES = ["local_only", "cloud_only", "edge_only", "static_rule", "dynamic", "learned_late", "late_rl"]

CSV_FIELDS = [
    "experiment_id", "scenario", "strategy", "duration_sec",
    "total_tasks", "avg_latency_ms", "p95_latency_ms", "urgent_avg_latency_ms",
    "deadline_violation_rate", "success_rate", "local_task_count",
    "edge_task_count", "cloud_task_count", "cloud_bandwidth_kb",
    "edge_cpu_percent", "cloud_cpu_percent", "alert_count", "qos_satisfaction_rate", "timestamp",
]


def check_services() -> bool:
    try:
        with httpx.Client(timeout=3.0) as client:
            e = client.get(f"{EDGE_SERVER_URL}/api/health")
            c = client.get(f"{CLOUD_SERVER_URL}/api/health")
            return e.status_code == 200 and c.status_code == 200
    except Exception:
        return False


def _post(client: httpx.Client, path: str) -> None:
    resp = client.post(f"{EDGE_SERVER_URL}{path}", timeout=5.0)
    resp.raise_for_status()


def run_single_experiment(
    client: httpx.Client,
    experiment_id: str,
    scenario: str,
    strategy: str,
    duration_sec: int,
) -> Dict[str, Any]:
    """Run a single scenario × strategy experiment."""
    print(f"  [Experiment] scenario={scenario} strategy={strategy} duration={duration_sec}s")

    _post(client, f"/api/scenario/{scenario}")
    _post(client, f"/api/strategy/{strategy}")

    # Record system event
    db.insert_alert(
        task_id=f"exp_{experiment_id}",
        device_id="system",
        message=f"Experiment started: {scenario} / {strategy}",
        alert_category="system",
        alert_level="info",
        alert_type="system_event",
    )

    since_id = db.get_max_task_id()
    alert_before = db.get_alert_counts()["alert_count"]

    time.sleep(duration_sec)

    stats = db.collect_experiment_stats(since_id, scenario, strategy)
    alert_after = db.get_alert_counts()["alert_count"]

    try:
        metrics = client.get(f"{EDGE_SERVER_URL}/api/metrics", timeout=5.0).json()
        edge_cpu = metrics.get("edge_metrics", {}).get("cpu_percent", 0)
        cloud_cpu = metrics.get("cloud_metrics", {}).get("cpu_percent", 0)
    except Exception:
        edge_cpu = cloud_cpu = 0

    record = {
        "experiment_id": experiment_id,
        "scenario": scenario,
        "strategy": strategy,
        "duration_sec": duration_sec,
        "edge_cpu_percent": edge_cpu,
        "cloud_cpu_percent": cloud_cpu,
        "alert_count": max(0, alert_after - alert_before),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        **stats,
    }

    db.insert_experiment_result(record)
    print(
        f"    → tasks={record['total_tasks']} "
        f"local/edge/cloud={record['local_task_count']}/{record['edge_task_count']}/{record['cloud_task_count']} "
        f"avg_lat={record['avg_latency_ms']}ms"
    )
    return record


def run_full_experiment(duration_sec: int = None, quick: bool = False) -> List[Dict[str, Any]]:
    """Run full 4×7 experiment matrix (quick=True: normal scenario only + all 7 strategies)."""
    duration = duration_sec or EXPERIMENT_DURATION_SEC
    scenarios = ["normal"] if quick else SCENARIOS
    strategies = STRATEGIES  # quick mode still runs all 7 strategies (normal scenario only)
    experiment_id = f"exp_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    if not check_services():
        raise RuntimeError(
            "Edge/Cloud Server is not running. Run: bash scripts/start_all.sh"
        )

    print(f"========================================")
    print(f" ComputerNet automated experiment")
    print(f" experiment_id: {experiment_id}")
    print(f" duration: {duration}s × {len(scenarios)} × {len(strategies)} = "
          f"{duration * len(scenarios) * len(strategies)}s total")
    print(f"========================================")

    results: List[Dict[str, Any]] = []
    with httpx.Client() as client:
        for scenario in scenarios:
            for strategy in strategies:
                try:
                    record = run_single_experiment(
                        client, experiment_id, scenario, strategy, duration
                    )
                    results.append(record)
                except Exception as e:
                    print(f"  [Error] {scenario}/{strategy}: {e}")

    # Restore defaults
    try:
        with httpx.Client() as client:
            _post(client, "/api/scenario/normal")
            _post(client, "/api/strategy/dynamic")
    except Exception:
        pass

    save_results(results, experiment_id)
    return results


def save_results(results: List[Dict[str, Any]], experiment_id: str) -> None:
    """Save CSV and JSON."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = RESULTS_DIR / "experiment_summary.csv"
    json_path = RESULTS_DIR / "experiment_summary.json"

    write_header = not csv_path.exists() or csv_path.stat().st_size == 0
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, "") for k in CSV_FIELDS})

    payload = {
        "experiment_id": experiment_id,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "results": results,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved:")
    print(f"  {csv_path}")
    print(f"  {json_path}")
