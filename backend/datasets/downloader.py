"""小数据集下载，失败时用 synthetic trace 兜底。"""
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from backend.datasets.converters import (
    convert_mec_edge_csv,
    convert_eua_csv,
    validate_mec_schema,
    validate_eua_schema,
)
from backend.datasets.registry import DATASET_REGISTRY, get_dataset
from backend.datasets.synthetic import generate_synthetic_for

logger = logging.getLogger("datasets.downloader")


def _dataset_dir(base: Path, name: str) -> Path:
    return base / "traces" / name


def _status_path(base: Path) -> Path:
    return base / "datasets" / "manifest.json"


def load_manifest(base: Path) -> Dict[str, Any]:
    p = _status_path(base)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {"datasets": {}, "updated_at": None}


def save_manifest(base: Path, manifest: Dict[str, Any]) -> None:
    p = _status_path(base)
    p.parent.mkdir(parents=True, exist_ok=True)
    manifest["updated_at"] = datetime.utcnow().isoformat() + "Z"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def _try_download(url: str, dest: Path, timeout: float = 30.0) -> bool:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            content = resp.content
            if len(content) < 50:
                return False
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
            return True
    except Exception as e:
        logger.warning("Download failed %s: %s", url, e)
        return False


def _count_csv_rows(path: Path) -> int:
    try:
        with open(path, encoding="utf-8") as f:
            return max(sum(1 for _ in f) - 1, 0)
    except OSError:
        return 0


def _resolve_url(meta: Dict[str, Any]) -> str:
    return os.getenv(meta["url_env"], "") or meta.get("default_url", "")


def _download_mec_remote(url: str, dest_file: Path) -> Optional[Dict[str, Any]]:
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw_mec.csv"
        if not _try_download(url, raw):
            return None
        try:
            info = convert_mec_edge_csv(raw, dest_file)
            if not validate_mec_schema(dest_file):
                return None
            return {
                "status": "ready",
                "source": "remote",
                "url": url,
                "size_bytes": dest_file.stat().st_size,
                "rows": info.get("rows", _count_csv_rows(dest_file)),
                "converter": info.get("converter"),
                "remote_repo": "nicsdee/Mobile-Edge-Computing-Dataset",
            }
        except Exception as e:
            logger.warning("MEC convert failed: %s", e)
            return None


def _download_eua_remote(meta: Dict[str, Any], dest_file: Path) -> Optional[Dict[str, Any]]:
    users_url = _resolve_url(meta)
    sites_url = os.getenv(meta.get("secondary_url_env", "EUA_EDGE_SITES_URL"), "") or meta.get("secondary_url", "")
    if not users_url or not sites_url:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        users_raw = Path(tmp) / "users_raw.csv"
        sites_raw = Path(tmp) / "sites_raw.csv"
        if not _try_download(users_url, users_raw):
            return None
        if not _try_download(sites_url, sites_raw):
            return None
        try:
            info = convert_eua_csv(users_raw, sites_raw, dest_file)
            if not validate_eua_schema(dest_file):
                return None
            return {
                "status": "ready",
                "source": "remote",
                "url": users_url,
                "secondary_url": sites_url,
                "size_bytes": dest_file.stat().st_size,
                "rows": info.get("rows", _count_csv_rows(dest_file)),
                "converter": info.get("converter"),
                "remote_repo": "PhuLai/eua-dataset",
            }
        except Exception as e:
            logger.warning("EUA convert failed: %s", e)
            return None


def download_dataset(
    name: str,
    traces_dir: Path,
    force: bool = False,
) -> Dict[str, Any]:
    """下载单个数据集；manual_only 数据集拒绝自动下载。"""
    meta = get_dataset(name)
    if meta.get("manual_only"):
        return {
            "name": name,
            "status": "manual_only",
            "message": meta.get("note", "Large trace — manual download only"),
            "auto_download": False,
        }

    dest_dir = _dataset_dir(traces_dir, name)
    dest_file = dest_dir / meta["filename"]
    manifest = load_manifest(traces_dir)
    cached = manifest.get("datasets", {}).get(name, {})

    if dest_file.exists() and not force:
        if cached.get("source") == "remote" and cached.get("status") == "ready":
            return {**cached, "name": name, "cached": True}
        if cached.get("status") in ("ready", "synthetic") and dest_file.stat().st_size > 0:
            if cached.get("source") != "synthetic":
                return {**cached, "name": name, "cached": True}

    url = _resolve_url(meta)
    record: Dict[str, Any] = {
        "name": name,
        "display_name": meta["display_name"],
        "path": str(dest_file),
        "auto_download": meta.get("auto_download", False),
    }

    remote_info: Optional[Dict[str, Any]] = None
    if name == "mec_edge" and url:
        remote_info = _download_mec_remote(url, dest_file)
    elif name == "eua":
        remote_info = _download_eua_remote(meta, dest_file)

    if remote_info:
        record.update(remote_info)
        logger.info("Downloaded %s from remote (%s rows)", name, record.get("rows"))
    else:
        if url:
            logger.warning("Download/convert failed for %s — generating synthetic fallback", name)
        else:
            logger.info("No URL for %s — generating synthetic fallback", name)
        syn = generate_synthetic_for(name, dest_file)
        record.update({
            "status": "synthetic",
            "source": "synthetic",
            "rows": syn["rows"],
            "message": "Remote download failed or URL not configured; using synthetic trace-like dataset",
        })

    manifest.setdefault("datasets", {})[name] = record
    save_manifest(traces_dir, manifest)
    return record


def download_auto_datasets(traces_dir: Path, force: bool = False) -> Dict[str, Any]:
    """仅下载 auto_download=True 的数据集（MEC + EUA）。"""
    results = {}
    for name, meta in DATASET_REGISTRY.items():
        if meta.get("auto_download"):
            results[name] = download_dataset(name, traces_dir, force=force)
    return results


def get_dataset_status(name: str, traces_dir: Path) -> Dict[str, Any]:
    meta = get_dataset(name)
    manifest = load_manifest(traces_dir)
    entry = manifest.get("datasets", {}).get(name, {})
    dest = _dataset_dir(traces_dir, name)
    if meta.get("filename"):
        fpath = dest / meta["filename"]
        exists = fpath.exists()
    else:
        exists = dest.exists() and any(dest.iterdir()) if dest.exists() else False

    return {
        **meta,
        "status": entry.get("status", "ready" if exists else "not_downloaded"),
        "source": entry.get("source"),
        "path": entry.get("path") or (str(dest / meta["filename"]) if meta.get("filename") else str(dest)),
        "rows": entry.get("rows"),
        "message": entry.get("message") or meta.get("note"),
        "file_exists": exists,
        "remote_repo": entry.get("remote_repo"),
        "converter": entry.get("converter"),
    }
