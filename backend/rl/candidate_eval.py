"""LATE-RL 候选模型评估 — 按场景统计指标与综合评分。"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend.common.config import (
    LATE_RL_MODEL_PATH,
    RL_CANDIDATES_DIR,
    RL_EVAL_EPISODE_LENGTH,
    RL_EVAL_EPISODES,
    RL_RANDOM_SEED,
)
from backend.edge_server.offloading import build_task_profile
from backend.rl.dqn_agent import LateRLAgent
from backend.rl.offload_env import OffloadEnv, SCENARIO_LIST
from backend.rl.state_encoder import action_to_location

logger = logging.getLogger("rl.candidate_eval")

CANDIDATE_PREFIX = "late_rl_candidate_"


def compute_scenario_score(row: Dict[str, Any]) -> float:
    """单场景综合评分 — emergency/edge_overload 权重更高。"""
    scenario = row["scenario"]
    high_lat_pen = max(0.0, row["avg_latency"] - 100.0) / 1000.0
    score = (
        row["avg_reward"]
        - 0.5 * row["deadline_violation_rate"]
        - 0.2 * high_lat_pen
    )
    if scenario == "emergency":
        score -= 0.3 * row["cloud_action_rate"]
        score += 0.5 * row["safety_critical_edge_rate"]
    elif scenario == "edge_overload":
        score -= 0.15 * max(0.0, row["edge_action_rate"] - 0.6)
        score += 0.2 * min(row["cloud_action_rate"], 0.5)
        score += 0.3 * row["safety_critical_edge_rate"]
    return round(score, 4)


def compute_overall_score(scenario_rows: List[Dict[str, Any]]) -> float:
    """跨场景加权总分。"""
    weights = {"emergency": 0.3, "edge_overload": 0.3, "normal": 0.2, "cloud_delay": 0.2}
    total = 0.0
    w_sum = 0.0
    for row in scenario_rows:
        w = weights.get(row["scenario"], 0.25)
        total += w * row["score"]
        w_sum += w
    return round(total / max(w_sum, 1e-9), 4)


def evaluate_model_on_scenario(
    model_path: Path,
    scenario: str,
    episodes: int = None,
    episode_length: int = None,
    seed: int = None,
    reward_profile: str = "default",
) -> Dict[str, Any]:
    """在固定场景下评估单个模型。"""
    episodes = episodes or RL_EVAL_EPISODES
    episode_length = episode_length or RL_EVAL_EPISODE_LENGTH
    seed = seed if seed is not None else RL_RANDOM_SEED

    agent = LateRLAgent()
    meta = agent.load(model_path)
    profile = meta.get("reward_profile", reward_profile)
    env = OffloadEnv(seed=seed + hash(scenario) % 1000, reward_profile=profile)

    all_rewards: List[float] = []
    all_latencies: List[float] = []
    violations = 0
    total_steps = 0
    safety_critical = 0
    safety_edge = 0
    action_counts = [0, 0, 0]

    for ep in range(episodes):
        state = env.reset(scenario=scenario)
        for _ in range(episode_length):
            action = agent.act(state, epsilon=0.0)
            next_state, reward, _, info = env.step(action)
            all_rewards.append(reward)
            all_latencies.append(info["latency_ms"])
            if not info["deadline_met"]:
                violations += 1
            action_counts[action] += 1
            task = env.current_task
            if task:
                prof = build_task_profile(task)
                if prof.task_category == "safety_critical":
                    safety_critical += 1
                    if action_to_location(action) == "edge":
                        safety_edge += 1
            total_steps += 1
            state = next_state

    lat_arr = np.array(all_latencies) if all_latencies else np.array([0.0])
    total_actions = max(sum(action_counts), 1)
    row = {
        "scenario": scenario,
        "episodes": episodes,
        "episode_length": episode_length,
        "avg_reward": round(float(np.mean(all_rewards)), 4),
        "avg_latency": round(float(np.mean(lat_arr)), 2),
        "p95_latency": round(float(np.percentile(lat_arr, 95)), 2),
        "deadline_violation_rate": round(violations / max(total_steps, 1), 4),
        "safety_critical_edge_rate": round(safety_edge / max(safety_critical, 1), 4),
        "local_action_rate": round(action_counts[0] / total_actions, 4),
        "edge_action_rate": round(action_counts[1] / total_actions, 4),
        "cloud_action_rate": round(action_counts[2] / total_actions, 4),
        "reward_profile": profile,
        "model_meta": meta,
    }
    row["score"] = compute_scenario_score(row)
    return row


def discover_candidates(include_main: bool = True) -> List[Tuple[str, Path, Optional[Path]]]:
    """返回 (candidate_name, model_path, metadata_path) 列表。"""
    found: List[Tuple[str, Path, Optional[Path]]] = []
    RL_CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)

    for pkl in sorted(RL_CANDIDATES_DIR.glob(f"{CANDIDATE_PREFIX}*.pkl")):
        name = pkl.stem[len(CANDIDATE_PREFIX):]
        meta = RL_CANDIDATES_DIR / f"{CANDIDATE_PREFIX}{name}_metadata.json"
        found.append((name, pkl, meta if meta.exists() else None))

    if include_main and LATE_RL_MODEL_PATH.exists():
        meta = LATE_RL_MODEL_PATH.parent / "late_rl_metadata.json"
        found.insert(0, ("current_main", LATE_RL_MODEL_PATH, meta if meta.exists() else None))

    return found


def load_reward_profile(metadata_path: Optional[Path], candidate_name: str) -> str:
    if metadata_path and metadata_path.exists():
        with open(metadata_path, encoding="utf-8") as f:
            meta = json.load(f)
        return meta.get("reward_profile", "default")
    for suffix in ("_safety_boost", "_deadline_boost", "_balanced"):
        if candidate_name.endswith(suffix):
            return suffix[1:]
    return "default"


def evaluate_all_candidates(
    episodes: int = None,
    episode_length: int = None,
    seed: int = None,
) -> Dict[str, Any]:
    """评估所有候选 + current_main baseline。"""
    episodes = episodes or RL_EVAL_EPISODES
    episode_length = episode_length or RL_EVAL_EPISODE_LENGTH
    seed = seed if seed is not None else RL_RANDOM_SEED

    candidates = discover_candidates(include_main=True)
    if not candidates:
        return {"status": "no_candidates", "rows": [], "recommendations": {}}

    rows: List[Dict[str, Any]] = []
    by_candidate: Dict[str, List[Dict[str, Any]]] = {}

    for name, model_path, meta_path in candidates:
        profile = load_reward_profile(meta_path, name)
        scenario_rows = []
        for scenario in SCENARIO_LIST:
            logger.info("Evaluating %s on %s ...", name, scenario)
            row = evaluate_model_on_scenario(
                model_path, scenario,
                episodes=episodes, episode_length=episode_length,
                seed=seed, reward_profile=profile,
            )
            row["candidate_name"] = name
            row["reward_profile"] = profile
            rows.append(row)
            scenario_rows.append(row)
        by_candidate[name] = scenario_rows

    recommendations = _build_recommendations(by_candidate)
    return {
        "status": "ok",
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
        "episodes": episodes,
        "episode_length": episode_length,
        "rows": rows,
        "recommendations": recommendations,
    }


def _build_recommendations(by_candidate: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """生成最佳候选推荐及与 current_main 对比。"""
    overall: Dict[str, float] = {}
    emergency: Dict[str, float] = {}
    edge_overload: Dict[str, float] = {}

    for name, scenario_rows in by_candidate.items():
        overall[name] = compute_overall_score(scenario_rows)
        for row in scenario_rows:
            if row["scenario"] == "emergency":
                emergency[name] = row["score"]
            elif row["scenario"] == "edge_overload":
                edge_overload[name] = row["score"]

    def _best(d: Dict[str, float], exclude: str = "") -> Optional[str]:
        filtered = {k: v for k, v in d.items() if k != exclude}
        if not filtered:
            return None
        return max(filtered, key=filtered.get)

    best_overall = _best(overall)
    best_emergency = _best(emergency)
    best_edge_overload = _best(edge_overload)

    main_overall = overall.get("current_main")
    main_emergency = emergency.get("current_main")
    main_edge = edge_overload.get("current_main")

    def _beats_main(candidate: Optional[str], main_score: Optional[float], scores: Dict[str, float]) -> bool:
        if not candidate or candidate == "current_main" or main_score is None:
            return False
        cand_score = scores.get(candidate)
        if cand_score is None:
            return False
        return cand_score > main_score * 1.02  # 2% margin

    return {
        "best_overall": best_overall,
        "best_emergency": best_emergency,
        "best_edge_overload": best_edge_overload,
        "overall_scores": overall,
        "emergency_scores": emergency,
        "edge_overload_scores": edge_overload,
        "current_main_overall": main_overall,
        "current_main_emergency": main_emergency,
        "current_main_edge_overload": main_edge,
        "best_overall_beats_main": _beats_main(best_overall, main_overall, overall),
        "best_emergency_beats_main": _beats_main(best_emergency, main_emergency, emergency),
        "best_edge_overload_beats_main": _beats_main(best_edge_overload, main_edge, edge_overload),
        "promote_hint": (
            "Run: bash scripts/promote_rl_candidate.sh <candidate_name>"
            if any([
                _beats_main(best_overall, main_overall, overall),
                _beats_main(best_emergency, main_emergency, emergency),
                _beats_main(best_edge_overload, main_edge, edge_overload),
            ])
            else "No candidate significantly beats current_main; keep main model."
        ),
    }
