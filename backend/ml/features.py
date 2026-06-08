"""LATE-Learn 特征工程 — 支持消融 variant。"""
from typing import Any, Dict, List, Optional

import numpy as np

PRIORITY_MAP = {"high": 2, "medium": 1, "low": 0}
RISK_MAP = {"critical": 3, "high": 2, "medium": 1, "low": 0}
SCENARIO_MAP = {"normal": 0, "cloud_delay": 1, "edge_overload": 2, "emergency": 3}
LABEL_MAP = {"local": 0, "edge": 1, "cloud": 2}
INV_LABEL_MAP = {v: k for k, v in LABEL_MAP.items()}

ALL_FEATURE_NAMES = [
    "priority_enc", "deadline_ms", "data_size_kb", "compute_cost", "risk_enc",
    "edge_cpu_load", "network_delay_ms", "scenario_enc",
    "edge_proximity_score", "request_burst_factor",
]

FEATURE_VARIANTS = {
    "full": ALL_FEATURE_NAMES,
    "no_trace": [
        "priority_enc", "deadline_ms", "data_size_kb", "compute_cost", "risk_enc",
        "edge_cpu_load", "network_delay_ms", "scenario_enc",
    ],
    "no_scenario": [
        "priority_enc", "deadline_ms", "data_size_kb", "compute_cost", "risk_enc",
        "edge_cpu_load", "network_delay_ms",
        "edge_proximity_score", "request_burst_factor",
    ],
    "task_only": [
        "priority_enc", "deadline_ms", "data_size_kb", "compute_cost", "risk_enc",
    ],
}

# 向后兼容旧 8 维模型
FEATURE_NAMES = FEATURE_VARIANTS["no_trace"]


def _trace_features(row: Dict[str, Any], edge_cpu: float) -> Dict[str, float]:
    edge_proximity = max(0.0, 1.0 - float(edge_cpu))
    ddl = max(float(row.get("deadline_ms", 1000)), 1.0)
    burst = min(2.0, float(row.get("data_size_kb", 10)) / ddl * 1000.0)
    return {"edge_proximity_score": edge_proximity, "request_burst_factor": burst}


def build_feature_dict(
    task: Dict[str, Any],
    edge_cpu: float = 0.3,
    network_delay_ms: float = 50.0,
    scenario: str = "normal",
    risk_level: str = "medium",
) -> Dict[str, float]:
    trace = _trace_features(task, edge_cpu)
    return {
        "priority_enc": float(PRIORITY_MAP.get(str(task.get("priority", "medium")), 1)),
        "deadline_ms": float(task.get("deadline_ms", 1000)),
        "data_size_kb": float(task.get("data_size_kb", 10)),
        "compute_cost": float(task.get("compute_cost", 0.3)),
        "risk_enc": float(RISK_MAP.get(risk_level, 1)),
        "edge_cpu_load": float(edge_cpu),
        "network_delay_ms": float(network_delay_ms),
        "scenario_enc": float(SCENARIO_MAP.get(scenario, 0)),
        **trace,
    }


def extract_features(
    task: Dict[str, Any],
    edge_cpu: float = 0.3,
    network_delay_ms: float = 50.0,
    scenario: str = "normal",
    risk_level: str = "medium",
    feature_names: Optional[List[str]] = None,
    variant: str = "full",
) -> np.ndarray:
    names = feature_names or FEATURE_VARIANTS.get(variant, ALL_FEATURE_NAMES)
    fd = build_feature_dict(task, edge_cpu, network_delay_ms, scenario, risk_level)
    return np.array([fd[n] for n in names], dtype=np.float64)


def label_to_location(label: int) -> str:
    return INV_LABEL_MAP.get(int(label), "edge")


def location_to_label(location: str) -> int:
    return LABEL_MAP.get(location, 1)
