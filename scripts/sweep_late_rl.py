#!/usr/bin/env python3
"""LATE-RL 候选训练扫描 — 不覆盖主模型。"""
import argparse
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.rl.train_late_rl import train_late_rl_candidate

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sweep_late_rl")

SWEEP_CONFIGS_FULL = [
    {"name": "ep50_len200", "episodes": 50, "episode_length": 200, "reward_profile": "default"},
    {"name": "ep100_len200", "episodes": 100, "episode_length": 200, "reward_profile": "default"},
    {"name": "ep200_len200", "episodes": 200, "episode_length": 200, "reward_profile": "default"},
    {"name": "ep100_len400", "episodes": 100, "episode_length": 400, "reward_profile": "default"},
    {"name": "ep100_len200_safety_boost", "episodes": 100, "episode_length": 200, "reward_profile": "safety_boost"},
    {"name": "ep100_len200_balanced", "episodes": 100, "episode_length": 200, "reward_profile": "balanced"},
]

SWEEP_CONFIGS_FAST = [
    {"name": "ep20_len100", "episodes": 20, "episode_length": 100, "reward_profile": "default"},
    {"name": "ep50_len100", "episodes": 50, "episode_length": 100, "reward_profile": "default"},
]


def get_sweep_configs() -> list:
    if os.getenv("RL_SWEEP_FAST", "").strip() in ("1", "true", "yes"):
        return SWEEP_CONFIGS_FAST
    configs = SWEEP_CONFIGS_FULL[:4]
    if os.getenv("RL_SWEEP_EXTRA_PROFILES", "").strip() in ("1", "true", "yes"):
        configs = SWEEP_CONFIGS_FULL
    return configs


def main() -> int:
    parser = argparse.ArgumentParser(description="LATE-RL candidate training sweep")
    parser.add_argument("--dry-run", action="store_true", help="List configs without training")
    parser.add_argument("--candidate", type=str, default="", help="Train single candidate by name")
    args = parser.parse_args()

    configs = get_sweep_configs()
    if args.candidate:
        configs = [c for c in configs if c["name"] == args.candidate]
        if not configs:
            all_names = [c["name"] for c in SWEEP_CONFIGS_FULL + SWEEP_CONFIGS_FAST]
            logger.error("Unknown candidate '%s'. Available: %s", args.candidate, ", ".join(all_names))
            return 1

    mode = "FAST" if os.getenv("RL_SWEEP_FAST", "").strip() in ("1", "true", "yes") else "FULL"
    logger.info("Sweep mode=%s candidates=%d", mode, len(configs))

    if args.dry_run:
        for cfg in configs:
            print(
                f"  {cfg['name']}: episodes={cfg['episodes']} "
                f"length={cfg['episode_length']} profile={cfg['reward_profile']}"
            )
        return 0

    seed = int(os.getenv("RL_RANDOM_SEED", "42"))
    results = []
    for i, cfg in enumerate(configs, 1):
        logger.info("[%d/%d] Training candidate %s ...", i, len(configs), cfg["name"])
        meta = train_late_rl_candidate(
            candidate_name=cfg["name"],
            episodes=cfg["episodes"],
            episode_length=cfg["episode_length"],
            reward_profile=cfg["reward_profile"],
            seed=seed,
        )
        results.append(meta)
        logger.info("  -> saved %s", meta.get("model_path"))

    logger.info("Sweep complete. %d candidates saved to data/models/rl_candidates/", len(results))
    logger.info("Next: python scripts/evaluate_rl_candidates.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
