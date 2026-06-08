"""LATE-RL evaluation."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from backend.common.config import LATE_RL_MODEL_PATH, RESULTS_DIR, RL_EPISODE_LENGTH, RL_RANDOM_SEED
from backend.rl.dqn_agent import LateRLAgent
from backend.rl.offload_env import OffloadEnv
from backend.rl.state_encoder import action_to_location

logger = logging.getLogger("rl.evaluate")


def evaluate_late_rl(
    episodes: int = 5,
    episode_length: int = None,
    seed: int = None,
) -> Dict[str, Any]:
    episode_length = episode_length or RL_EPISODE_LENGTH
    seed = seed if seed is not None else RL_RANDOM_SEED

    if not LATE_RL_MODEL_PATH.exists():
        return {
            "status": "missing_model",
            "message": "LATE-RL model not found. Run bash scripts/train_late_rl.sh first.",
        }

    agent = LateRLAgent()
    meta = agent.load(LATE_RL_MODEL_PATH)
    env = OffloadEnv(seed=seed + 1)

    all_rewards: List[float] = []
    all_latencies: List[float] = []
    violations = 0
    total_steps = 0
    safety_critical = 0
    safety_edge = 0
    action_counts = [0, 0, 0]

    for _ in range(episodes):
        state = env.reset()
        for _ in range(episode_length):
            action = agent.act(state, epsilon=0.0)
            next_state, reward, _, info = env.step(action)
            all_rewards.append(reward)
            all_latencies.append(info["latency_ms"])
            if not info["deadline_met"]:
                violations += 1
            action_counts[action] += 1
            task = env.current_task
            if task and task.task_type == "smoke_alert":
                safety_critical += 1
                if action_to_location(action) == "edge":
                    safety_edge += 1
            total_steps += 1
            state = next_state

    lat_arr = np.array(all_latencies) if all_latencies else np.array([0.0])
    total_actions = max(sum(action_counts), 1)
    result = {
        "status": "ok",
        "model_type": meta.get("model_type", "sklearn_fitted_q"),
        "episodes": episodes,
        "episode_length": episode_length,
        "avg_reward": round(float(np.mean(all_rewards)), 4),
        "avg_latency": round(float(np.mean(lat_arr)), 2),
        "p95_latency": round(float(np.percentile(lat_arr, 95)), 2),
        "deadline_violation_rate": round(violations / max(total_steps, 1), 4),
        "safety_critical_edge_rate": round(
            safety_edge / max(safety_critical, 1), 4
        ),
        "action_distribution": {
            "local": round(action_counts[0] / total_actions, 4),
            "edge": round(action_counts[1] / total_actions, 4),
            "cloud": round(action_counts[2] / total_actions, 4),
        },
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RESULTS_DIR / "late_rl_evaluation.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    md_path = RESULTS_DIR / "late_rl_evaluation.md"
    lines = [
        "# LATE-RL Evaluation",
        "",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        f"- **avg_reward**: {result['avg_reward']}",
        f"- **avg_latency**: {result['avg_latency']} ms",
        f"- **p95_latency**: {result['p95_latency']} ms",
        f"- **deadline_violation_rate**: {result['deadline_violation_rate']}",
        f"- **safety_critical_edge_rate**: {result['safety_critical_edge_rate']}",
        f"- **action_distribution**: {result['action_distribution']}",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    result["json_path"] = str(json_path)
    result["md_path"] = str(md_path)
    return result
