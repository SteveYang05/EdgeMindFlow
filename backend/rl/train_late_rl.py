"""LATE-RL 训练入口。"""
import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from backend.common.config import (
    LATE_RL_METADATA_PATH,
    LATE_RL_MODEL_PATH,
    RESULTS_DIR,
    RL_CANDIDATES_DIR,
    RL_EPISODE_LENGTH,
    RL_RANDOM_SEED,
    RL_TRAIN_EPISODES,
)
from backend.rl.dqn_agent import MODEL_TYPE, LateRLAgent
from backend.rl.offload_env import OffloadEnv
from backend.rl.state_encoder import ACTIONS

logger = logging.getLogger("rl.train")


def train_late_rl(
    episodes: int = None,
    episode_length: int = None,
    seed: int = None,
) -> Dict[str, Any]:
    episodes = episodes or RL_TRAIN_EPISODES
    episode_length = episode_length or RL_EPISODE_LENGTH
    seed = seed if seed is not None else RL_RANDOM_SEED

    env = OffloadEnv(seed=seed)
    agent = LateRLAgent()
    logger.info("Training LATE-RL: episodes=%d length=%d seed=%d", episodes, episode_length, seed)
    curve = agent.train(env, episodes=episodes, episode_length=episode_length)

    last10 = curve[-10:] if len(curve) >= 10 else curve
    avg_reward_last_10 = sum(r["total_reward"] for r in last10) / max(len(last10), 1)
    best_avg = max(r["total_reward"] for r in curve) if curve else 0.0

    metadata = {
        "model_type": MODEL_TYPE,
        "method": "LATE-RL",
        "episodes": episodes,
        "episode_length": episode_length,
        "avg_reward_last_10": round(avg_reward_last_10, 4),
        "best_avg_reward": round(best_avg, 4),
        "epsilon_final": round(agent.epsilon, 4),
        "state_dim": agent.encoder.state_dim,
        "action_space": ACTIONS,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "fallback_enabled": True,
        "random_seed": seed,
    }

    LATE_RL_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    agent.save(LATE_RL_MODEL_PATH, metadata)
    with open(LATE_RL_METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    curve_path = RESULTS_DIR / "late_rl_training_curve.csv"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    fields = [
        "episode", "total_reward", "avg_latency", "deadline_violation_rate",
        "local_actions", "edge_actions", "cloud_actions", "epsilon",
    ]
    with open(curve_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in curve:
            w.writerow({k: row.get(k, "") for k in fields})

    logger.info("LATE-RL saved to %s avg_reward_last_10=%.3f", LATE_RL_MODEL_PATH, avg_reward_last_10)
    return {**metadata, "curve_path": str(curve_path), "model_path": str(LATE_RL_MODEL_PATH)}


def train_late_rl_candidate(
    candidate_name: str,
    episodes: int,
    episode_length: int,
    reward_profile: str = "default",
    seed: int = None,
) -> Dict[str, Any]:
    """训练候选 LATE-RL 模型，保存至 rl_candidates/，不覆盖主模型。"""
    seed = seed if seed is not None else RL_RANDOM_SEED
    RL_CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)

    output_path = RL_CANDIDATES_DIR / f"late_rl_candidate_{candidate_name}.pkl"
    metadata_path = RL_CANDIDATES_DIR / f"late_rl_candidate_{candidate_name}_metadata.json"
    curve_path = RL_CANDIDATES_DIR / f"late_rl_candidate_{candidate_name}_curve.csv"

    env = OffloadEnv(seed=seed, reward_profile=reward_profile)
    agent = LateRLAgent()
    logger.info(
        "Training LATE-RL candidate '%s': episodes=%d length=%d profile=%s seed=%d",
        candidate_name, episodes, episode_length, reward_profile, seed,
    )
    curve = agent.train(env, episodes=episodes, episode_length=episode_length)

    last10 = curve[-10:] if len(curve) >= 10 else curve
    avg_reward_last_10 = sum(r["total_reward"] for r in last10) / max(len(last10), 1)
    best_avg = max(r["total_reward"] for r in curve) if curve else 0.0

    metadata = {
        "model_type": MODEL_TYPE,
        "method": "LATE-RL",
        "candidate_name": candidate_name,
        "reward_profile": reward_profile,
        "episodes": episodes,
        "episode_length": episode_length,
        "avg_reward_last_10": round(avg_reward_last_10, 4),
        "best_avg_reward": round(best_avg, 4),
        "epsilon_final": round(agent.epsilon, 4),
        "state_dim": agent.encoder.state_dim,
        "action_space": ACTIONS,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "fallback_enabled": True,
        "random_seed": seed,
        "is_candidate": True,
        "model_path": str(output_path),
    }

    agent.save(output_path, metadata)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    fields = [
        "episode", "total_reward", "avg_latency", "deadline_violation_rate",
        "local_actions", "edge_actions", "cloud_actions", "epsilon",
    ]
    with open(curve_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in curve:
            w.writerow({k: row.get(k, "") for k in fields})

    logger.info("Candidate saved to %s avg_reward_last_10=%.3f", output_path, avg_reward_last_10)
    return {
        **metadata,
        "curve_path": str(curve_path),
        "metadata_path": str(metadata_path),
    }
