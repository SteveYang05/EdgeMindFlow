"""State encoder — task + environment → fixed-length vector。"""
from typing import Any, Dict, List, Optional

import numpy as np

from backend.edge_server.offloading import TaskContext, TaskProfile, build_task_profile

TASK_TYPES = [
    "temperature_report", "humidity_report", "smoke_alert", "image_detection",
    "access_control", "statistics_report", "historical_analysis", "periodic_stats",
]
PRIORITIES = ["low", "medium", "high"]
RISK_LEVELS = ["low", "medium", "high", "critical"]
CATEGORIES = [
    "sensor_report", "safety_critical", "vision_analytics", "access_control",
    "batch_analytics", "unknown",
]
SCENARIOS = ["normal", "cloud_delay", "edge_overload", "emergency"]
ACTIONS = ["local", "edge", "cloud"]
ACTION_TO_ID = {a: i for i, a in enumerate(ACTIONS)}
ID_TO_ACTION = {i: a for i, a in enumerate(ACTIONS)}


def _one_hot(value: str, choices: List[str]) -> List[float]:
    return [1.0 if value == c else 0.0 for c in choices]


def _norm(val: float, scale: float) -> float:
    return min(float(val) / max(scale, 1e-6), 2.0)


class StateEncoder:
    """Unified train/inference state encoding."""

    def __init__(self):
        self.numeric_dim = 13
        self.state_dim = (
            len(TASK_TYPES) + len(PRIORITIES) + len(RISK_LEVELS)
            + len(CATEGORIES) + len(SCENARIOS) + self.numeric_dim
        )

    def encode(
        self,
        task: TaskContext,
        profile: Optional[TaskProfile] = None,
        scenario: str = "normal",
        edge_cpu: float = 0.3,
        edge_queue_depth: int = 0,
        cloud_cpu: float = 0.3,
        cloud_queue_depth: int = 0,
        cloud_delay_ms: float = 50.0,
        bandwidth_mbps: float = 100.0,
        recent_avg_latency: float = 100.0,
        recent_deadline_violation_rate: float = 0.0,
        request_burst_factor: float = 0.5,
        edge_proximity_score: float = 0.7,
    ) -> np.ndarray:
        profile = profile or build_task_profile(task)
        burst = request_burst_factor
        if burst == 0.5:
            burst = min(2.0, task.data_size_kb / max(task.deadline_ms, 1.0) * 1000.0)
        prox = edge_proximity_score if edge_proximity_score != 0.7 else max(0.0, 1.0 - edge_cpu)
        vec = (
            _one_hot(task.task_type, TASK_TYPES)
            + _one_hot(task.priority, PRIORITIES)
            + _one_hot(profile.risk_level, RISK_LEVELS)
            + _one_hot(profile.task_category, CATEGORIES)
            + _one_hot(scenario, SCENARIOS)
            + [
                _norm(task.deadline_ms, 5000.0),
                _norm(task.data_size_kb, 512.0),
                _norm(task.compute_cost, 1.0),
                edge_cpu,
                _norm(edge_queue_depth, 20.0),
                cloud_cpu,
                _norm(cloud_queue_depth, 20.0),
                _norm(cloud_delay_ms, 500.0),
                _norm(bandwidth_mbps, 100.0),
                _norm(recent_avg_latency, 1000.0),
                recent_deadline_violation_rate,
                burst,
                prox,
            ]
        )
        return np.array(vec, dtype=np.float64)

    def encode_dict(self, row: Dict[str, Any], env: Dict[str, Any]) -> np.ndarray:
        task = TaskContext(
            task_id=str(row.get("task_id", "rl")),
            task_type=str(row.get("task_type", "temperature_report")),
            priority=str(row.get("priority", "medium")),
            data_size_kb=float(row.get("data_size_kb", 10)),
            compute_cost=float(row.get("compute_cost", 0.3)),
            deadline_ms=float(row.get("deadline_ms", 1000)),
        )
        return self.encode(
            task,
            scenario=str(env.get("scenario", "normal")),
            edge_cpu=float(env.get("edge_cpu", 0.3)),
            edge_queue_depth=int(env.get("edge_queue_depth", 0)),
            cloud_cpu=float(env.get("cloud_cpu", 0.3)),
            cloud_queue_depth=int(env.get("cloud_queue_depth", 0)),
            cloud_delay_ms=float(env.get("cloud_delay_ms", 50.0)),
            bandwidth_mbps=float(env.get("bandwidth_mbps", 100.0)),
            recent_avg_latency=float(env.get("recent_avg_latency", 100.0)),
            recent_deadline_violation_rate=float(env.get("recent_deadline_violation_rate", 0.0)),
            request_burst_factor=float(env.get("request_burst_factor", 0.5)),
            edge_proximity_score=float(env.get("edge_proximity_score", 0.7)),
        )


def action_to_location(action_id: int) -> str:
    return ID_TO_ACTION.get(int(action_id), "edge")


def location_to_action(location: str) -> int:
    return ACTION_TO_ID.get(location, 1)
