#!/usr/bin/env python3
"""LATE-Learn CPU training script — Oracle Cost Labeling (default) or Teacher mode."""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("PYTHONPATH", str(PROJECT_ROOT))

from backend.common.config import LATE_LEARN_LABEL_SOURCE
from backend.datasets.manager import DatasetManager
from backend.ml.train import train_late_learn


def main():
    limit = int(os.getenv("LATE_LEARN_TRAIN_LIMIT", "2000"))
    label_source = os.getenv("LATE_LEARN_LABEL_SOURCE", LATE_LEARN_LABEL_SOURCE)
    print("Ensuring trace datasets (MEC/EUA)...")
    DatasetManager().ensure_default_datasets()
    print(f"Training LATE-Learn on CPU (limit={limit}, label_source={label_source})...")
    meta = train_late_learn(limit=limit, label_source=label_source)
    print(
        f"Done. accuracy={meta['test_accuracy']} "
        f"oracle_agreement={meta.get('oracle_agreement')} "
        f"avg_regret={meta.get('avg_regret')} "
        f"samples={meta['train_samples']}"
    )
    print(f"Model: {meta['path']}")
    print(f"Metadata: ml/models/model_metadata.json")


if __name__ == "__main__":
    main()
