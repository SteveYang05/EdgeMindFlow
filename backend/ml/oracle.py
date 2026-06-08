"""Oracle Cost Labeling — generate optimal cost labels for LATE-Learn."""
from typing import Any, Dict, Tuple

from backend.common.config import (
    CLOUD_COMPUTE_CAPACITY,
    EDGE_COMPUTE_CAPACITY,
    LARGE_TASK_KB,
    LOCAL_COMPUTE_CAPACITY,
)
from backend.common.schemas import Scenario
from backend.edge_server.offloading import (
    NodeState,
    TaskContext,
    TaskProfile,
    build_task_profile,
    deadline_violation_risk,
    estimate_compute_latency_ms,
    estimate_node_cost,
    estimate_queue_latency_ms,
    estimate_total_latency,
    estimate_upload_latency_ms,
    _compute_qos_risk,
)


def _safety_penalty(profile: TaskProfile, node_type: str) -> float:
    """Penalize cloud for safety-critical tasks; no hardcoded edge."""
    if profile.task_category != "safety_critical":
        return 0.0
    if node_type == "cloud":
        return 0.85
    if node_type == "local" and profile.task_type == "smoke_alert":
        return 0.25
    return 0.0


def _local_compute_penalty(profile: TaskProfile, node_type: str) -> float:
    """Add compute penalty for high-compute tasks executed locally."""
    if node_type != "local":
        return 0.0
    if profile.compute_cost >= 0.6 or profile.data_size_kb >= LARGE_TASK_KB:
        return 0.35 * profile.compute_cost
    return 0.0


def _scenario_penalties(
    node_type: str,
    scenario: str,
    extra_cloud_delay_ms: float,
    edge_overloaded: bool,
) -> float:
    penalty = 0.0
    if scenario == Scenario.CLOUD_DELAY.value or extra_cloud_delay_ms > 100:
        if node_type == "cloud":
            penalty += 0.55
    if scenario == Scenario.EDGE_OVERLOAD.value or edge_overloaded:
        if node_type == "edge":
            penalty += 0.40
    return penalty


def compute_oracle_node_cost(
    profile: TaskProfile,
    node_type: str,
    edge_state: NodeState,
    cloud_state: NodeState,
    extra_cloud_delay_ms: float = 0.0,
    edge_overloaded: bool = False,
    scenario: str = "normal",
) -> Dict[str, float]:
    """Compute per-node oracle total cost and components."""
    base = estimate_node_cost(
        profile, node_type, edge_state, cloud_state, extra_cloud_delay_ms
    )
    latency_ms = base["estimated_latency_ms"]
    latency_cost = min(latency_ms / 1000.0, 2.0)
    load_cost = base["resource_load"]
    transfer_cost = min(base["transfer_cost"] / 500.0, 2.0)
    deadline_penalty = base["deadline_violation_risk"]
    qos_penalty = base["qos_risk"]
    safety_penalty = _safety_penalty(profile, node_type)
    local_compute_penalty = _local_compute_penalty(profile, node_type)
    scenario_penalty = _scenario_penalties(
        node_type, scenario, extra_cloud_delay_ms, edge_overloaded
    )

    total = (
        0.30 * latency_cost
        + 0.20 * load_cost
        + 0.15 * transfer_cost
        + 0.15 * deadline_penalty
        + 0.10 * safety_penalty
        + 0.10 * qos_penalty
        + local_compute_penalty
        + scenario_penalty
    )
    return {
        "total_cost": round(total, 6),
        "latency_cost": round(latency_cost, 6),
        "load_cost": round(load_cost, 6),
        "transfer_cost": round(transfer_cost, 6),
        "deadline_penalty": round(deadline_penalty, 6),
        "safety_penalty": round(safety_penalty, 6),
        "qos_penalty": round(qos_penalty, 6),
        "scenario_penalty": round(scenario_penalty, 6),
        "local_compute_penalty": round(local_compute_penalty, 6),
    }


def compute_oracle_labels(
    task: TaskContext,
    edge_state: NodeState,
    cloud_state: NodeState,
    scenario: str = "normal",
    extra_cloud_delay_ms: float = 0.0,
    edge_overloaded: bool = False,
) -> Dict[str, Any]:
    """Simulate local/edge/cloud costs and return oracle label."""
    profile = build_task_profile(task)
    costs = {}
    for node in ("local", "edge", "cloud"):
        costs[node] = compute_oracle_node_cost(
            profile, node, edge_state, cloud_state,
            extra_cloud_delay_ms, edge_overloaded, scenario,
        )
    oracle_label = min(costs, key=lambda n: costs[n]["total_cost"])
    return {
        "oracle_label": oracle_label,
        "oracle_local_cost": costs["local"]["total_cost"],
        "oracle_edge_cost": costs["edge"]["total_cost"],
        "oracle_cloud_cost": costs["cloud"]["total_cost"],
        "costs": costs,
    }
