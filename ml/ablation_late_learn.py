#!/usr/bin/env python3
"""LATE-Learn lightweight ablation — compare full / no_trace / no_scenario / task_only."""
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("PYTHONPATH", str(PROJECT_ROOT))

from backend.common.config import LATE_LEARN_ABLATION_SAMPLES, LATE_LEARN_LABEL_SOURCE, RESULTS_DIR
from backend.datasets.manager import DatasetManager
from backend.ml.train import train_late_learn

VARIANTS = ["full", "no_trace", "no_scenario", "task_only"]
FIELDS = [
    "variant", "accuracy", "macro_f1", "oracle_agreement", "avg_regret",
    "avg_predicted_cost", "avg_oracle_cost", "feature_count", "label_source",
    "train_samples", "test_samples",
]


def _write_md(rows: list, path: Path) -> None:
    lines = [
        "# LATE-Learn Ablation Study",
        "",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "| variant | accuracy | macro_f1 | oracle_agreement | avg_regret | feature_count |",
        "|---------|----------|----------|------------------|------------|---------------|",
    ]
    for r in rows:
        lines.append(
            f"| {r['variant']} | {r['accuracy']} | {r['macro_f1']} | "
            f"{r['oracle_agreement']} | {r['avg_regret']} | {r['feature_count']} |"
        )
    lines += [
        "",
        "## Notes",
        "",
        "- **full**: task + network + load + scenario + trace-derived features",
        "- **no_trace**: remove edge_proximity_score / request_burst_factor",
        "- **no_scenario**: remove scenario_enc",
        "- **task_only**: task features only",
        "",
        "Ablation validates the role of trace and scenario features in oracle labeling learning.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    limit = int(os.getenv("LATE_LEARN_ABLATION_SAMPLES", str(LATE_LEARN_ABLATION_SAMPLES)))
    label_source = os.getenv("LATE_LEARN_LABEL_SOURCE", LATE_LEARN_LABEL_SOURCE)
    print(f"LATE-Learn ablation (samples={limit}, label_source={label_source})")
    DatasetManager().ensure_default_datasets()

    results = []
    for i, variant in enumerate(VARIANTS, 1):
        print(f"[{i}/{len(VARIANTS)}] Training variant={variant} ...")
        meta = train_late_learn(
            limit=limit,
            label_source=label_source,
            feature_variant=variant,
            save_model=(variant == "full"),
        )
        row = {
            "variant": variant,
            "accuracy": meta.get("test_accuracy", 0),
            "macro_f1": meta.get("macro_f1", 0),
            "oracle_agreement": meta.get("oracle_agreement", 0),
            "avg_regret": meta.get("avg_regret", 0),
            "avg_predicted_cost": meta.get("avg_predicted_cost", 0),
            "avg_oracle_cost": meta.get("avg_oracle_cost", 0),
            "feature_count": meta.get("feature_count", 0),
            "label_source": meta.get("label_source", label_source),
            "train_samples": meta.get("train_samples", 0),
            "test_samples": meta.get("test_samples", 0),
        }
        results.append(row)
        print(
            f"  acc={row['accuracy']} oracle_agree={row['oracle_agreement']} "
            f"regret={row['avg_regret']}"
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = RESULTS_DIR / "late_learn_ablation.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(results)
    _write_md(results, RESULTS_DIR / "late_learn_ablation.md")
    print(f"Ablation done: {csv_path}")


if __name__ == "__main__":
    main()
