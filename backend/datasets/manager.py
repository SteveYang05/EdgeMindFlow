"""Dataset manager — unified entry point."""
import csv
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.common.config import DATA_DIR
from backend.datasets.downloader import (
    download_auto_datasets,
    download_dataset,
    get_dataset_status,
    load_manifest,
)
from backend.datasets.registry import DATASET_REGISTRY, list_datasets


class DatasetManager:
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or DATA_DIR
        self.traces_dir = self.data_dir

    def ensure_default_datasets(self, force: bool = False) -> Dict[str, Any]:
        return download_auto_datasets(self.traces_dir, force=force)

    def list_all(self) -> List[Dict[str, Any]]:
        return [get_dataset_status(n, self.traces_dir) for n in DATASET_REGISTRY]

    def get(self, name: str) -> Dict[str, Any]:
        return get_dataset_status(name, self.traces_dir)

    def download_one(self, name: str, force: bool = False) -> Dict[str, Any]:
        return download_dataset(name, self.traces_dir, force=force)

    def read_mec_tasks(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Read MEC trace task records (for training/replay)."""
        status = self.get("mec_edge")
        path = Path(status.get("path", ""))
        if not path.exists():
            self.ensure_default_datasets()
            path = Path(self.get("mec_edge").get("path", ""))
        if not path.exists():
            return []
        rows = []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= limit:
                    break
                rows.append(row)
        return rows

    def manifest(self) -> Dict[str, Any]:
        return load_manifest(self.traces_dir)


@lru_cache(maxsize=1)
def get_dataset_manager() -> DatasetManager:
    return DatasetManager()
