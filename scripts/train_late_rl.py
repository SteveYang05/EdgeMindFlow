#!/usr/bin/env python3
"""LATE-RL CPU training script."""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("PYTHONPATH", str(PROJECT_ROOT))

from backend.rl.train_late_rl import train_late_rl


def main():
    episodes = int(os.getenv("RL_TRAIN_EPISODES", "200"))
    episode_length = int(os.getenv("RL_EPISODE_LENGTH", "200"))
    seed = int(os.getenv("RL_RANDOM_SEED", "42"))
    print(f"Training LATE-RL (episodes={episodes}, length={episode_length}, seed={seed})...")
    meta = train_late_rl(episodes=episodes, episode_length=episode_length, seed=seed)
    print(f"Done. avg_reward_last_10={meta['avg_reward_last_10']} model={meta['model_path']}")


if __name__ == "__main__":
    main()
