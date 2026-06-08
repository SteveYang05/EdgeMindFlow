#!/usr/bin/env python3
"""评估 rl_candidates/ 下所有 LATE-RL 候选，并与 current_main 对比。"""
import csv
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.common.config import RESULTS_DIR, RL_EVAL_EPISODE_LENGTH, RL_EVAL_EPISODES
from backend.rl.candidate_eval import evaluate_all_candidates

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("evaluate_rl_candidates")

CSV_FIELDS = [
    "candidate_name", "reward_profile", "episodes", "episode_length", "scenario",
    "avg_reward", "avg_latency", "p95_latency", "deadline_violation_rate",
    "safety_critical_edge_rate", "cloud_action_rate", "edge_action_rate",
    "local_action_rate", "score",
]


def write_csv(path: Path, rows: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in CSV_FIELDS})


def write_md(path: Path, result: dict) -> None:
    rec = result.get("recommendations", {})
    lines = [
        "# LATE-RL Candidate Evaluation",
        "",
        f"生成时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        f"- Episodes per scenario: {result.get('episodes', RL_EVAL_EPISODES)}",
        f"- Episode length: {result.get('episode_length', RL_EVAL_EPISODE_LENGTH)}",
        "",
        "## Recommendations",
        "",
        f"- **Best candidate overall**: `{rec.get('best_overall', 'N/A')}` "
        f"(score={rec.get('overall_scores', {}).get(rec.get('best_overall'), 'N/A')})",
        f"- **Best candidate for emergency**: `{rec.get('best_emergency', 'N/A')}` "
        f"(score={rec.get('emergency_scores', {}).get(rec.get('best_emergency'), 'N/A')})",
        f"- **Best candidate for edge_overload**: `{rec.get('best_edge_overload', 'N/A')}` "
        f"(score={rec.get('edge_overload_scores', {}).get(rec.get('best_edge_overload'), 'N/A')})",
        "",
        "## vs current_main",
        "",
    ]
    if rec.get("current_main_overall") is not None:
        lines += [
            f"- current_main overall: {rec['current_main_overall']}",
            f"- current_main emergency: {rec.get('current_main_emergency', 'N/A')}",
            f"- current_main edge_overload: {rec.get('current_main_edge_overload', 'N/A')}",
            f"- best_overall beats main: {rec.get('best_overall_beats_main', False)}",
            f"- best_emergency beats main: {rec.get('best_emergency_beats_main', False)}",
            f"- best_edge_overload beats main: {rec.get('best_edge_overload_beats_main', False)}",
            "",
            f"**{rec.get('promote_hint', '')}**",
            "",
        ]
    else:
        lines += ["- No current_main model found at data/models/late_rl.pkl", ""]

    lines += ["## Per-candidate results", "", "| candidate | scenario | score | avg_reward | cloud% | safety_edge% |", "|-----------|----------|-------|------------|--------|--------------|"]
    for row in result.get("rows", []):
        lines.append(
            f"| {row['candidate_name']} | {row['scenario']} | {row['score']} | "
            f"{row['avg_reward']} | {row['cloud_action_rate']} | {row['safety_critical_edge_rate']} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    episodes = int(os.getenv("RL_EVAL_EPISODES", str(RL_EVAL_EPISODES)))
    episode_length = int(os.getenv("RL_EVAL_EPISODE_LENGTH", str(RL_EVAL_EPISODE_LENGTH)))

    logger.info("Evaluating RL candidates: episodes=%d length=%d", episodes, episode_length)
    result = evaluate_all_candidates(episodes=episodes, episode_length=episode_length)

    if result.get("status") == "no_candidates":
        logger.warning("No candidates found in data/models/rl_candidates/")
        return 1

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = RESULTS_DIR / "late_rl_candidate_eval.csv"
    md_path = RESULTS_DIR / "late_rl_candidate_eval.md"
    json_path = RESULTS_DIR / "late_rl_candidate_eval.json"

    # Strip model_meta from JSON export
    export_rows = []
    for row in result["rows"]:
        export_rows.append({k: v for k, v in row.items() if k != "model_meta"})
    export = {**result, "rows": export_rows}

    write_csv(csv_path, export_rows)
    write_md(md_path, export)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(export, f, indent=2, ensure_ascii=False)

    rec = result["recommendations"]
    print("\n=== LATE-RL Candidate Evaluation ===")
    print(f"Best candidate overall:       {rec.get('best_overall')}")
    print(f"Best candidate for emergency: {rec.get('best_emergency')}")
    print(f"Best candidate for edge_overload: {rec.get('best_edge_overload')}")
    print(f"\n{rec.get('promote_hint')}")
    print(f"\nResults: {csv_path}, {md_path}, {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
