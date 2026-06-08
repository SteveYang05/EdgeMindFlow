"""LATE-RL inference — late_rl strategy, fallback chain LATE-Learn → LATE-Offload."""
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import joblib
import numpy as np

from backend.common.config import LATE_RL_METADATA_PATH, LATE_RL_MODEL_PATH
from backend.edge_server.offloading import TaskContext, build_task_profile
from backend.rl.dqn_agent import LateRLAgent
from backend.rl.state_encoder import StateEncoder, action_to_location

logger = logging.getLogger("rl.predictor")
LEARN_METHOD = "LATE-RL"

_agent_cache: Dict[str, Any] = {}
_meta_cache: Dict[str, Any] = {}


def _load_metadata() -> Dict[str, Any]:
    if _meta_cache:
        return _meta_cache
    if LATE_RL_METADATA_PATH.exists():
        import json
        with open(LATE_RL_METADATA_PATH, encoding="utf-8") as f:
            _meta_cache.update(json.load(f))
    return _meta_cache


def load_agent(path: Path = None) -> Optional[LateRLAgent]:
    path = path or LATE_RL_MODEL_PATH
    key = str(path)
    if key in _agent_cache:
        return _agent_cache[key]
    if not path.exists():
        return None
    try:
        agent = LateRLAgent()
        agent.load(path)
        _agent_cache[key] = agent
        return agent
    except Exception as e:
        logger.warning("Failed to load LATE-RL model: %s", e)
        return None


def clear_agent_cache() -> None:
    _agent_cache.clear()
    _meta_cache.clear()


def predict_offloading_rl(
    task: TaskContext,
    edge_state,
    scenario: str = "normal",
    extra_cloud_delay_ms: float = 0.0,
    recent_avg_latency: float = 100.0,
    recent_violation_rate: float = 0.0,
) -> Tuple[Optional[str], str, bool, Dict[str, Any]]:
    """Return (decision, reason, used_rl, extra_info)."""
    extra: Dict[str, Any] = {
        "fallback_used": False,
        "rl_model_type": None,
        "rl_q_values": None,
        "rl_selected_action": None,
    }
    agent = load_agent()
    meta = _load_metadata()
    extra["rl_model_type"] = meta.get("model_type")

    if agent is None:
        extra["fallback_used"] = True
        try:
            from backend.ml.predictor import predict_offloading
            decision, reason, used = predict_offloading(
                task, edge_state, scenario, extra_cloud_delay_ms
            )
            if used:
                return decision, f"{LEARN_METHOD} model not found; fallback to LATE-Learn. {reason}", False, extra
        except ImportError:
            pass
        from backend.edge_server.offloading import decide_late_offload, NodeState
        cloud_state = NodeState(cpu_load=0.3, network_delay_ms=50.0 + extra_cloud_delay_ms)
        decision, reason, _, _ = decide_late_offload(
            task, edge_state, cloud_state,
            extra_cloud_delay_ms,
            edge_state.cpu_load > 0.85,
            scenario,
        )
        return decision, f"{LEARN_METHOD} model not found; fallback to LATE-Offload. {reason}", False, extra

    profile = build_task_profile(task)
    encoder = StateEncoder()
    cloud_delay = edge_state.network_delay_ms + extra_cloud_delay_ms
    state = encoder.encode(
        task,
        profile=profile,
        scenario=scenario,
        edge_cpu=edge_state.cpu_load,
        edge_queue_depth=getattr(edge_state, "queue_depth", 0),
        cloud_cpu=0.3,
        cloud_queue_depth=0,
        cloud_delay_ms=cloud_delay,
        bandwidth_mbps=getattr(edge_state, "bandwidth_mbps", 100.0),
        recent_avg_latency=recent_avg_latency,
        recent_deadline_violation_rate=recent_violation_rate,
    )
    q_values = agent.predict_q_values(state)
    action = int(np.argmax(q_values))
    decision = action_to_location(action)
    extra["rl_q_values"] = [round(float(v), 4) for v in q_values]
    extra["rl_selected_action"] = decision

    if profile.task_category == "safety_critical" and task.deadline_ms <= 500:
        if decision != "edge":
            decision = "edge"
            reason = (
                f"{LEARN_METHOD}: safety-critical override — edge reserved "
                f"(Q={extra['rl_q_values']}, model={extra['rl_model_type']})."
            )
            return decision, reason, True, extra

    reason = (
        f"{LEARN_METHOD}: RL policy selected {decision} to maximize long-term reward "
        f"under current queue, latency, and safety state "
        f"(Q={extra['rl_q_values']}, model={extra['rl_model_type']})."
    )
    return decision, reason, True, extra
