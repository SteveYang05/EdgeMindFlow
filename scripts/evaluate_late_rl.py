#!/usr/bin/env python3
"""LATE-RL evaluation script."""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("PYTHONPATH", str(PROJECT_ROOT))

from backend.rl.evaluate_late_rl import evaluate_late_rl


def main():
    episodes = int(os.getenv("RL_EVAL_EPISODES", "5"))
    result = evaluate_late_rl(episodes=episodes)
    if result.get("status") == "missing_model":
        print(result["message"])
        sys.exit(0)
    print(f"Evaluation: avg_reward={result['avg_reward']} avg_latency={result['avg_latency']}")
    print(f"Saved: {result.get('json_path')}")


if __name__ == "__main__":
    main()
