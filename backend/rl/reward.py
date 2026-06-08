"""RL reward function — 可解释长期优化目标，支持多种 reward profile。"""
from typing import Dict

from backend.edge_server.offloading import TaskProfile

ACTIONS = ["local", "edge", "cloud"]
REWARD_PROFILES = ("default", "safety_boost", "deadline_boost", "balanced")


def compute_reward(
    action: int,
    profile: TaskProfile,
    latency_ms: float,
    deadline_met: bool,
    scenario: str,
    edge_cpu: float,
    edge_overloaded: bool,
    data_size_kb: float,
    bandwidth_mbps: float,
    success: bool = True,
    reward_profile: str = "default",
) -> tuple[float, Dict[str, float]]:
    """计算 reward 及分项，供报告解释。"""
    location = ACTIONS[action]
    profile_name = reward_profile if reward_profile in REWARD_PROFILES else "default"
    parts: Dict[str, float] = {}

    parts["success_bonus"] = 0.3 if success else 0.0

    if profile_name == "deadline_boost":
        parts["deadline_bonus"] = 1.5 if deadline_met else -3.0
    elif profile_name == "balanced":
        parts["deadline_bonus"] = 1.25 if deadline_met else -2.5
    else:
        parts["deadline_bonus"] = 1.0 if deadline_met else -2.0

    parts["latency_penalty"] = -latency_ms / 1000.0

    transfer = min(data_size_kb * 8.0 / max(bandwidth_mbps, 1.0) / 1000.0, 1.5)
    parts["transfer_penalty"] = -transfer

    safety = 0.0
    if profile.task_category == "safety_critical":
        if profile_name == "safety_boost":
            if location == "edge":
                safety = 1.2
            elif location == "cloud":
                safety = -2.0
            elif location == "local" and profile.compute_cost >= 0.5:
                safety = -0.5
        elif profile_name == "balanced":
            if location == "edge":
                safety = 1.0
            elif location == "cloud":
                safety = -1.5
            elif location == "local" and profile.compute_cost >= 0.5:
                safety = -0.4
        else:
            if location == "edge":
                safety = 0.5
            elif location == "cloud":
                safety = -1.0
            elif location == "local" and profile.compute_cost >= 0.5:
                safety = -0.5
    parts["safety_penalty"] = safety

    if profile_name in ("safety_boost", "balanced") and scenario == "emergency" and location == "cloud":
        parts["emergency_cloud_penalty"] = -1.5 if profile_name == "safety_boost" else -1.0
    else:
        parts["emergency_cloud_penalty"] = 0.0

    overload = 0.0
    if edge_overloaded and location == "edge" and profile.task_category != "safety_critical":
        overload = -0.8
    elif edge_cpu > 0.85 and location == "edge" and profile.task_category != "safety_critical":
        overload = -0.4
    parts["overload_penalty"] = overload

    cloud_delay_pen = 0.0
    if scenario == "cloud_delay" and location == "cloud":
        cloud_delay_pen = -0.8
    parts["cloud_delay_penalty"] = cloud_delay_pen

    total = sum(parts.values())
    parts["total"] = round(total, 6)
    parts["reward_profile"] = profile_name
    return total, parts
