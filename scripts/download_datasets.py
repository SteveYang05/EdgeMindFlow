#!/usr/bin/env python3
"""Download default trace datasets (MEC + EUA); synthetic fallback on failure."""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("PYTHONPATH", str(PROJECT_ROOT))

from backend.datasets.manager import DatasetManager


def main():
    force = os.getenv("FORCE_DOWNLOAD", "").lower() in ("1", "true", "yes")
    dm = DatasetManager()
    results = dm.ensure_default_datasets(force=force)
    print("Dataset download summary:")
    for name, info in results.items():
        print(f"  {name}: status={info.get('status')} source={info.get('source')}")
    print("\nAll datasets (including manual-only registrations):")
    for d in dm.list_all():
        print(f"  {d['name']}: {d.get('status')} auto_download={d.get('auto_download')}")


if __name__ == "__main__":
    main()
