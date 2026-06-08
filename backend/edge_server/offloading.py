"""
任务卸载决策：LATE-Offload 及多种 baseline 策略。

LATE-Offload (Latency-Aware and Task-priority Enhanced Edge Offloading)
时延感知与任务优先级增强的边缘计算卸载方法。

API 策略名仍为 dynamic；内部实现三阶段 LATE-Offload。
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from backend.common.config import (
    CLOUD_COMPUTE_CAPACITY,
    CLOUD_DELAY_SCENARIO_PENALTY,
    CLOUD_TRANSFER_PENALTY,
    DEFAULT_UPLOAD_BASE_MS,
    EDGE_COMPUTE_CAPACITY,
    EDGE_OVERLOAD_PENALTY,
    EDGE_PREFERENCE_BONUS,
    LARGE_TASK_KB,
    LOCAL_COMPUTE_CAPACITY,
    LOCAL_STABILITY_PENALTY,
    SMALL_TASK_KB,
    WEIGHT_DEADLINE,
    WEIGHT_LATENCY,
    WEIGHT_LOAD,
    WEIGHT_PRIORITY,
    WEIGHT_QOS,
    WEIGHT_TRANSFER,
)
from backend.common.schemas import OffloadingDecision, OffloadingStrategy, Priority, Scenario

METHOD_NAME = "LATE-Offload"


@dataclass
class NodeState:
    cpu_load: float = 0.3
    memory_load: float = 0.3
    network_delay_ms: float = 50.0
    bandwidth_mbps: float = 100.0
    bandwidth_usage: float = 0.1
    queue_depth: int = 0


@dataclass
class TaskContext:
    task_id: str
    task_type: str
    priority: str
    data_size_kb: float
    compute_cost: float
    deadline_ms: float


@dataclass
class TaskProfile:
    """Stage 1: Task Profiling 任务画像。"""
    priority: str
    deadline_ms: float
    data_size_kb: float
    compute_cost: float
    risk_level: str
    task_category: str
    task_type: str


_RISK_LEVEL_MAP = {
    "smoke_alert": "critical",
    "image_detection": "high",
    "access_control": "medium",
    "temperature_report": "low",
    "humidity_report": "low",
    "statistics_report": "low",
    "historical_analysis": "low",
    "periodic_stats": "low",
}

_CATEGORY_MAP = {
    "smoke_alert": "safety_critical",
    "image_detection": "vision_analytics",
    "access_control": "access_control",
    "temperature_report": "sensor_report",
    "humidity_report": "sensor_report",
    "statistics_report": "batch_analytics",
    "historical_analysis": "batch_analytics",
    "periodic_stats": "batch_analytics",
}


def build_task_profile(task: TaskContext) -> TaskProfile:
    """Stage 1: 根据任务字段构造任务画像。"""
    return TaskProfile(
        priority=task.priority,
        deadline_ms=task.deadline_ms,
        data_size_kb=task.data_size_kb,
        compute_cost=task.compute_cost,
        risk_level=_RISK_LEVEL_MAP.get(task.task_type, "medium"),
        task_category=_CATEGORY_MAP.get(task.task_type, "unknown"),
        task_type=task.task_type,
    )


def _priority_value(priority: str) -> float:
    return {"high": 1.0, "medium": 0.5, "low": 0.2}.get(priority, 0.5)


def _is_cloud_friendly_task(task_type: str) -> bool:
    return task_type in (
        "temperature_report", "humidity_report",
        "periodic_stats", "historical_analysis",
    )


def estimate_upload_latency_ms(
    data_size_kb: float,
    bandwidth_mbps: float,
    network_delay_ms: float,
    bandwidth_usage: float = 0.0,
) -> float:
    effective_bw = max(bandwidth_mbps * (1 - bandwidth_usage * 0.5), 1.0)
    transfer_ms = (data_size_kb * 8) / effective_bw
    congestion = bandwidth_usage * 20.0
    return DEFAULT_UPLOAD_BASE_MS + network_delay_ms + transfer_ms + congestion


def estimate_compute_latency_ms(compute_cost: float, node_load: float, capacity: float) -> float:
    base = (compute_cost / max(capacity, 1.0)) * 1000
    return base * (1.0 + node_load * 2.0)


def estimate_queue_latency_ms(queue_depth: int, node_load: float) -> float:
    return queue_depth * 5.0 + node_load * 30.0


def estimate_total_latency(upload_ms, queue_ms, compute_ms, return_ms=5.0) -> float:
    return upload_ms + queue_ms + compute_ms + return_ms


def deadline_violation_risk(estimated_latency_ms: float, deadline_ms: float) -> float:
    if deadline_ms <= 0:
        return 1.0
    ratio = estimated_latency_ms / deadline_ms
    if ratio >= 1.0:
        return 1.0
    return max(0.0, ratio ** 2)


def compute_score(
    estimated_latency_ms: float,
    node_load: float,
    transfer_cost: float,
    deadline_ms: float,
    priority: str,
) -> float:
    """Legacy 评分（baseline 策略展示用）。"""
    norm_latency = min(estimated_latency_ms / 1000.0, 2.0)
    transfer_norm = min(transfer_cost / 500.0, 2.0)
    deadline_risk = deadline_violation_risk(estimated_latency_ms, deadline_ms)
    priority_penalty = 1.0 - _priority_value(priority)
    score = (
        WEIGHT_LATENCY * norm_latency
        + WEIGHT_LOAD * node_load
        + WEIGHT_TRANSFER * transfer_norm
        + WEIGHT_DEADLINE * deadline_risk
        + WEIGHT_PRIORITY * priority_penalty
    )
    return round(score, 4)


def _compute_qos_risk(profile: TaskProfile, estimated_latency_ms: float, node_load: float) -> float:
    """QoS 风险：结合风险等级、deadline 与节点负载。"""
    risk_weight = {
        "critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25,
    }.get(profile.risk_level, 0.5)
    deadline_risk = deadline_violation_risk(estimated_latency_ms, profile.deadline_ms)
    return min(1.0, risk_weight * 0.6 + deadline_risk * 0.3 + node_load * 0.1)


def get_adaptive_weights(
    scenario: str,
    profile: TaskProfile,
    metrics: Dict[str, Any],
) -> Dict[str, float]:
    """Scenario-Adaptive Weighting：按场景与任务画像调整权重。"""
    weights = {
        "w_latency": WEIGHT_LATENCY,
        "w_load": WEIGHT_LOAD,
        "w_transfer": WEIGHT_TRANSFER,
        "w_deadline": WEIGHT_DEADLINE,
        "w_priority": WEIGHT_PRIORITY,
        "w_qos": WEIGHT_QOS,
    }

    if scenario == Scenario.CLOUD_DELAY.value or metrics.get("extra_cloud_delay_ms", 0) > 100:
        weights["w_latency"] += 0.08
        weights["w_transfer"] += 0.07
        weights["w_load"] -= 0.05

    elif scenario == Scenario.EDGE_OVERLOAD.value or metrics.get("edge_overloaded"):
        weights["w_load"] += 0.10
        weights["w_latency"] -= 0.03
        if profile.task_category != "safety_critical":
            weights["w_transfer"] -= 0.02

    elif scenario == Scenario.EMERGENCY.value:
        weights["w_deadline"] += 0.08
        weights["w_priority"] += 0.05
        weights["w_qos"] += 0.07
        weights["w_latency"] -= 0.05

    if profile.risk_level in ("critical", "high"):
        weights["w_qos"] += 0.03
        weights["w_priority"] += 0.02

    total = sum(weights.values())
    if total > 0:
        weights = {k: round(v / total, 4) for k, v in weights.items()}
    return weights


def estimate_node_cost(
    profile: TaskProfile,
    node_type: str,
    edge_state: NodeState,
    cloud_state: NodeState,
    extra_cloud_delay_ms: float = 0.0,
) -> Dict[str, float]:
    """Stage 2: 对 local / edge / cloud 估计多目标代价分量。"""
    if node_type == "local":
        compute = estimate_compute_latency_ms(
            profile.compute_cost, edge_state.cpu_load * 0.5, LOCAL_COMPUTE_CAPACITY
        )
        latency = estimate_total_latency(0, 0, compute)
        transfer = 0.0
        load = edge_state.cpu_load * 0.5
    elif node_type == "edge":
        upload = estimate_upload_latency_ms(
            profile.data_size_kb * 0.1,
            edge_state.bandwidth_mbps,
            edge_state.network_delay_ms * 0.1,
            edge_state.bandwidth_usage,
        )
        queue = estimate_queue_latency_ms(edge_state.queue_depth, edge_state.cpu_load)
        compute = estimate_compute_latency_ms(
            profile.compute_cost, edge_state.cpu_load, EDGE_COMPUTE_CAPACITY
        )
        latency = estimate_total_latency(upload, queue, compute)
        transfer = profile.data_size_kb * 0.1
        load = edge_state.cpu_load
    else:  # cloud
        upload = estimate_upload_latency_ms(
            profile.data_size_kb,
            cloud_state.bandwidth_mbps,
            edge_state.network_delay_ms + extra_cloud_delay_ms,
            cloud_state.bandwidth_usage,
        )
        queue = estimate_queue_latency_ms(cloud_state.queue_depth, cloud_state.cpu_load)
        compute = estimate_compute_latency_ms(
            profile.compute_cost, cloud_state.cpu_load, CLOUD_COMPUTE_CAPACITY
        )
        latency = estimate_total_latency(upload, queue, compute, return_ms=10.0)
        transfer = profile.data_size_kb
        load = cloud_state.cpu_load

    return {
        "estimated_latency_ms": round(latency, 2),
        "resource_load": load,
        "transfer_cost": transfer,
        "deadline_violation_risk": deadline_violation_risk(latency, profile.deadline_ms),
        "priority_penalty": 1.0 - _priority_value(profile.priority),
        "qos_risk": _compute_qos_risk(profile, latency, load),
    }


def compute_late_score(
    cost_components: Dict[str, float],
    adaptive_weights: Dict[str, float],
) -> float:
    """Stage 2: LATE-Offload 自适应加权评分（越低越优）。"""
    norm_latency = min(cost_components["estimated_latency_ms"] / 1000.0, 2.0)
    transfer_norm = min(cost_components["transfer_cost"] / 500.0, 2.0)
    score = (
        adaptive_weights["w_latency"] * norm_latency
        + adaptive_weights["w_load"] * cost_components["resource_load"]
        + adaptive_weights["w_transfer"] * transfer_norm
        + adaptive_weights["w_deadline"] * cost_components["deadline_violation_risk"]
        + adaptive_weights["w_priority"] * cost_components["priority_penalty"]
        + adaptive_weights["w_qos"] * cost_components["qos_risk"]
    )
    return round(score, 4)


def _apply_late_scenario_biases(
    profile: TaskProfile,
    scores: Dict[str, float],
    estimates: Dict[str, Dict[str, float]],
    edge_state: NodeState,
    scenario: str,
    edge_overloaded: bool,
    extra_cloud_delay_ms: float,
) -> Dict[str, float]:
    """场景与任务画像相关的评分偏置（仍通过 score 决策，非硬编码）。"""
    adjusted = dict(scores)

    adjusted["local"] += LOCAL_STABILITY_PENALTY

    if edge_state.cpu_load < 0.75 and not edge_overloaded:
        adjusted["edge"] -= EDGE_PREFERENCE_BONUS

    if profile.data_size_kb <= SMALL_TASK_KB:
        adjusted["cloud"] += CLOUD_TRANSFER_PENALTY * 0.5
    elif profile.data_size_kb >= LARGE_TASK_KB:
        adjusted["cloud"] -= CLOUD_TRANSFER_PENALTY * 0.3

    if _is_cloud_friendly_task(profile.task_type) and scenario != Scenario.CLOUD_DELAY.value:
        adjusted["cloud"] -= 0.08
        adjusted["local"] += 0.05

    if profile.priority == Priority.MEDIUM.value:
        adjusted["edge"] -= 0.06
        adjusted["local"] += 0.04

    if profile.priority == Priority.LOW.value and profile.data_size_kb <= SMALL_TASK_KB:
        if edge_state.cpu_load < 0.5:
            adjusted["local"] += 0.03
        else:
            adjusted["local"] += 0.12
            adjusted["edge"] -= 0.05

    if scenario == Scenario.CLOUD_DELAY.value or extra_cloud_delay_ms > 100:
        adjusted["cloud"] += CLOUD_DELAY_SCENARIO_PENALTY
        adjusted["edge"] -= 0.08

    if scenario == Scenario.EDGE_OVERLOAD.value or edge_overloaded:
        if profile.task_category != "safety_critical":
            adjusted["edge"] += EDGE_OVERLOAD_PENALTY
            adjusted["cloud"] -= 0.06

    return adjusted


def apply_safety_edge_reservation(
    profile: TaskProfile,
    scores: Dict[str, float],
    estimates: Dict[str, Dict[str, float]],
    metrics: Dict[str, Any],
) -> Tuple[Dict[str, float], Optional[str]]:
    """Stage 3: 安全关键任务边缘保留机制（约束感知，仍基于 score）。"""
    if profile.task_category != "safety_critical" or profile.deadline_ms > 500:
        return scores, None

    edge_state: NodeState = metrics["edge_state"]
    edge_overloaded = metrics.get("edge_overloaded", False)
    edge_lat = estimates["edge"]["estimated_latency_ms"]
    cloud_lat = estimates["cloud"]["estimated_latency_ms"]

    adjusted = dict(scores)
    adjusted["edge"] -= 0.30
    adjusted["local"] += 0.12
    adjusted["cloud"] += 0.08

    reservation = "edge"
    if edge_overloaded and edge_state.cpu_load > 0.95 and cloud_lat < edge_lat * 0.85:
        adjusted["edge"] += 0.20
        reservation = "relaxed"
    return adjusted, reservation


def _build_late_reason(
    decision: str,
    profile: TaskProfile,
    scenario: str,
    edge_overloaded: bool,
    extra_cloud_delay_ms: float,
    reservation: Optional[str],
    scores: Dict[str, float],
) -> str:
    """生成 LATE-Offload 可解释 reason。"""
    if reservation == "edge" and decision == "edge":
        return (
            f"{METHOD_NAME}: safety-critical {profile.task_type.replace('_', ' ')} "
            f"reserved at edge for low-latency park response."
        )

    if profile.task_category == "safety_critical" and decision == "edge":
        return (
            f"{METHOD_NAME}: safety-critical task reserved at edge "
            f"despite network stress (scores={scores})."
        )

    if decision != "edge" and edge_overloaded and profile.task_category != "safety_critical":
        if scenario in (Scenario.EDGE_OVERLOAD.value,) or edge_overloaded:
            return (
                f"{METHOD_NAME}: edge avoided for non-critical task due to "
                f"edge_overload load penalty."
            )

    if decision == "cloud":
        if scenario == Scenario.CLOUD_DELAY.value or extra_cloud_delay_ms > 100:
            return (
                f"{METHOD_NAME}: cloud avoided because cloud_delay scenario "
                f"increases transfer and latency risk."
            )
        if _is_cloud_friendly_task(profile.task_type):
            return f"{METHOD_NAME}: cloud selected for batch analytics with adaptive score."
        return f"{METHOD_NAME}: cloud selected with lowest adaptive score under current load."

    if decision == "edge":
        if scenario == Scenario.EMERGENCY.value:
            return f"{METHOD_NAME}: edge selected for emergency scenario with enhanced QoS weights."
        return f"{METHOD_NAME}: selected edge with best adaptive score under normal network condition."

    if decision == "local":
        if profile.task_category == "sensor_report":
            return f"{METHOD_NAME}: lightweight sensor report processed locally with adaptive score."
        return f"{METHOD_NAME}: local selected as lowest adaptive score for lightweight task."

    return f"{METHOD_NAME}: decision={decision} via adaptive multi-objective score (scores={scores})."


def decide_late_offload(
    task: TaskContext,
    edge_state: NodeState,
    cloud_state: NodeState,
    extra_cloud_delay_ms: float = 0.0,
    edge_overloaded: bool = False,
    scenario: str = "normal",
) -> Tuple[str, str, Dict[str, float], Dict[str, Dict[str, float]]]:
    """LATE-Offload 三阶段决策入口。"""
    profile = build_task_profile(task)
    metrics = {
        "edge_state": edge_state,
        "cloud_state": cloud_state,
        "edge_overloaded": edge_overloaded,
        "extra_cloud_delay_ms": extra_cloud_delay_ms,
        "scenario": scenario,
    }
    adaptive_weights = get_adaptive_weights(scenario, profile, metrics)

    estimates = {}
    scores = {}
    for node in ("local", "edge", "cloud"):
        cost = estimate_node_cost(
            profile, node, edge_state, cloud_state, extra_cloud_delay_ms
        )
        estimates[node] = cost
        scores[node] = compute_late_score(cost, adaptive_weights)

    scores = _apply_late_scenario_biases(
        profile, scores, estimates, edge_state, scenario, edge_overloaded, extra_cloud_delay_ms
    )
    scores, reservation = apply_safety_edge_reservation(profile, scores, estimates, metrics)

    decision = min(scores, key=scores.get)
    reason = _build_late_reason(
        decision, profile, scenario, edge_overloaded, extra_cloud_delay_ms, reservation, scores
    )
    return decision, reason, scores, estimates


def estimate_location_latencies(
    task: TaskContext,
    edge_state: NodeState,
    cloud_state: NodeState,
    extra_cloud_delay_ms: float = 0.0,
) -> Tuple[float, float, float]:
    profile = build_task_profile(task)
    local = estimate_node_cost(profile, "local", edge_state, cloud_state, extra_cloud_delay_ms)
    edge = estimate_node_cost(profile, "edge", edge_state, cloud_state, extra_cloud_delay_ms)
    cloud = estimate_node_cost(profile, "cloud", edge_state, cloud_state, extra_cloud_delay_ms)
    return local["estimated_latency_ms"], edge["estimated_latency_ms"], cloud["estimated_latency_ms"]


# Static-Rule baseline
_STATIC_RULE_MAP = {
    "smoke_alert": ("edge", "Static-Rule: smoke_alert mapped to edge for low-latency safety response."),
    "image_detection": ("edge", "Static-Rule: image_detection mapped to edge to reduce cloud transfer."),
    "access_control": ("edge", "Static-Rule: access_control mapped to edge for moderate-latency access."),
    "temperature_report": ("local", "Static-Rule: temperature_report mapped to local as lightweight sensor data."),
    "humidity_report": ("local", "Static-Rule: humidity_report mapped to local as lightweight sensor data."),
    "statistics_report": ("cloud", "Static-Rule: statistics_report mapped to cloud for batch analytics."),
    "historical_analysis": ("cloud", "Static-Rule: historical_analysis mapped to cloud for batch analytics."),
    "periodic_stats": ("cloud", "Static-Rule: periodic_stats mapped to cloud for batch analytics."),
}


def decide_static_rule(task: TaskContext) -> Tuple[str, str]:
    if task.task_type in _STATIC_RULE_MAP:
        return _STATIC_RULE_MAP[task.task_type]
    return ("edge", "Static-Rule: unknown task type defaults to edge for lower latency.")


def decide_offloading(
    task: TaskContext,
    edge_state: NodeState,
    cloud_state: NodeState,
    strategy: str = "dynamic",
    extra_cloud_delay_ms: float = 0.0,
    edge_overloaded: bool = False,
    scenario: str = "normal",
) -> OffloadingDecision:
    local_lat, edge_lat, cloud_lat = estimate_location_latencies(
        task, edge_state, cloud_state, extra_cloud_delay_ms
    )

    transfer_edge = task.data_size_kb * 0.1
    transfer_cloud = task.data_size_kb

    local_score = compute_score(local_lat, edge_state.cpu_load, 0, task.deadline_ms, task.priority)
    edge_score = compute_score(edge_lat, edge_state.cpu_load, transfer_edge, task.deadline_ms, task.priority)
    cloud_score = compute_score(cloud_lat, cloud_state.cpu_load, transfer_cloud, task.deadline_ms, task.priority)

    base = dict(
        edge_score=edge_score, cloud_score=cloud_score, local_score=local_score,
        estimated_edge_latency_ms=round(edge_lat, 2),
        estimated_cloud_latency_ms=round(cloud_lat, 2),
        estimated_local_latency_ms=round(local_lat, 2),
    )

    if strategy == OffloadingStrategy.LOCAL_ONLY.value:
        return OffloadingDecision(
            task_id=task.task_id, decision="local",
            reason="Local-Only strategy: all tasks processed locally on device",
            **base,
        )

    if strategy == OffloadingStrategy.CLOUD_ONLY.value:
        return OffloadingDecision(
            task_id=task.task_id, decision="cloud",
            reason="Cloud-Only strategy: all tasks offloaded to cloud",
            **base,
        )

    if strategy == OffloadingStrategy.EDGE_ONLY.value:
        return OffloadingDecision(
            task_id=task.task_id, decision="edge",
            reason="Edge-Only strategy: all tasks processed at edge",
            **base,
        )

    if strategy == OffloadingStrategy.STATIC_RULE.value:
        decision, reason = decide_static_rule(task)
        return OffloadingDecision(task_id=task.task_id, decision=decision, reason=reason, **base)

    if strategy == OffloadingStrategy.LEARNED_LATE.value:
        try:
            from backend.ml.predictor import predict_offloading
            decision, reason, used = predict_offloading(
                task, edge_state, scenario, extra_cloud_delay_ms
            )
        except ImportError:
            decision, reason, used = None, "LATE-Learn: ML deps missing, fallback to LATE-Offload", False
        if not used:
            decision, reason, late_scores, _ = decide_late_offload(
                task, edge_state, cloud_state, extra_cloud_delay_ms, edge_overloaded, scenario
            )
            return OffloadingDecision(
                task_id=task.task_id, decision=decision, reason=reason,
                edge_score=late_scores.get("edge", edge_score),
                cloud_score=late_scores.get("cloud", cloud_score),
                local_score=late_scores.get("local", local_score),
                estimated_edge_latency_ms=round(edge_lat, 2),
                estimated_cloud_latency_ms=round(cloud_lat, 2),
                estimated_local_latency_ms=round(local_lat, 2),
            )
        return OffloadingDecision(
            task_id=task.task_id, decision=decision, reason=reason,
            edge_score=edge_score, cloud_score=cloud_score, local_score=local_score,
            estimated_edge_latency_ms=round(edge_lat, 2),
            estimated_cloud_latency_ms=round(cloud_lat, 2),
            estimated_local_latency_ms=round(local_lat, 2),
        )

    if strategy == OffloadingStrategy.LATE_RL.value:
        try:
            from backend.rl.predictor import predict_offloading_rl
            decision, reason, used, rl_extra = predict_offloading_rl(
                task, edge_state, scenario, extra_cloud_delay_ms
            )
        except ImportError:
            decision, reason, used, rl_extra = None, "LATE-RL: RL deps missing, fallback to LATE-Offload", False, {}
        if not used:
            decision, reason, late_scores, _ = decide_late_offload(
                task, edge_state, cloud_state, extra_cloud_delay_ms, edge_overloaded, scenario
            )
            fb = "LATE-RL model not found; fallback to LATE-Offload. "
            return OffloadingDecision(
                task_id=task.task_id, decision=decision, reason=fb + reason,
                edge_score=late_scores.get("edge", edge_score),
                cloud_score=late_scores.get("cloud", cloud_score),
                local_score=late_scores.get("local", local_score),
                estimated_edge_latency_ms=round(edge_lat, 2),
                estimated_cloud_latency_ms=round(cloud_lat, 2),
                estimated_local_latency_ms=round(local_lat, 2),
            )
        q_str = ""
        if rl_extra.get("rl_q_values"):
            q_str = f" Q={rl_extra['rl_q_values']}"
        return OffloadingDecision(
            task_id=task.task_id, decision=decision,
            reason=reason + q_str,
            edge_score=edge_score, cloud_score=cloud_score, local_score=local_score,
            estimated_edge_latency_ms=round(edge_lat, 2),
            estimated_cloud_latency_ms=round(cloud_lat, 2),
            estimated_local_latency_ms=round(local_lat, 2),
        )

    # ---- LATE-Offload (API: dynamic) ----
    decision, reason, late_scores, _ = decide_late_offload(
        task, edge_state, cloud_state, extra_cloud_delay_ms, edge_overloaded, scenario
    )

    return OffloadingDecision(
        task_id=task.task_id,
        decision=decision,
        reason=reason,
        edge_score=late_scores.get("edge", edge_score),
        cloud_score=late_scores.get("cloud", cloud_score),
        local_score=late_scores.get("local", local_score),
        estimated_edge_latency_ms=round(edge_lat, 2),
        estimated_cloud_latency_ms=round(cloud_lat, 2),
        estimated_local_latency_ms=round(local_lat, 2),
    )
