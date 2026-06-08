"""Convert public remote CSV to ComputerNet internal trace schema."""
import csv
import math
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MEC_FIELDS = [
    "timestamp", "device_id", "task_type", "priority",
    "data_size_kb", "compute_cost", "deadline_ms",
    "edge_cpu_load", "network_delay_ms",
]

EUA_FIELDS = [
    "user_id", "latitude", "longitude", "edge_node_id",
    "request_rate", "avg_data_size_kb", "avg_compute_cost",
]

_TASK_TYPE_MAP = {
    "sensor": "temperature_report",
    "image": "image_detection",
    "video": "image_detection",
    "smoke": "smoke_alert",
    "access": "access_control",
}

_COMPLEXITY_MAP = {
    "low": ("low", 0.15, 5000),
    "medium": ("medium", 0.45, 1500),
    "high": ("high", 0.75, 500),
}


def _normalize_header(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("(", "").replace(")", "").replace("%", "pct")


def _read_csv_rows(path: Path, limit: int = 0) -> Tuple[List[str], List[Dict[str, str]]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        rows = []
        for i, row in enumerate(reader):
            if limit and i >= limit:
                break
            rows.append({(_normalize_header(k)): v for k, v in row.items() if k})
        norm_fields = [_normalize_header(x) for x in fields]
        return norm_fields, rows


def validate_mec_schema(path: Path) -> bool:
    fields, _ = _read_csv_rows(path, limit=1)
    return all(f in fields for f in MEC_FIELDS)


def validate_eua_schema(path: Path) -> bool:
    fields, _ = _read_csv_rows(path, limit=1)
    return all(f in fields for f in EUA_FIELDS)


def _matches_internal_schema(path: Path) -> bool:
    return validate_mec_schema(path)


def convert_mec_edge_csv(src: Path, dest: Path, max_rows: int = 2000) -> Dict[str, Any]:
    """Convert public MEC CSV to internal project trace format."""
    if _matches_internal_schema(src):
        if src.resolve() != dest.resolve():
            dest.write_bytes(src.read_bytes())
        _, rows = _read_csv_rows(dest)
        return {"rows": len(rows), "converter": "passthrough"}

    _, rows = _read_csv_rows(src, limit=max_rows)
    if not rows:
        raise ValueError(f"Empty source CSV: {src}")

    base_time = datetime.utcnow()
    out_rows: List[Dict[str, Any]] = []
    for i, row in enumerate(rows):
        raw_type = str(row.get("task_type", row.get("task", "Sensor"))).strip()
        mapped_type = _TASK_TYPE_MAP.get(raw_type.lower(), "temperature_report")
        complexity = str(row.get("task_complexity", "medium")).strip().lower()
        priority, compute_cost, deadline_ms = _COMPLEXITY_MAP.get(complexity, _COMPLEXITY_MAP["medium"])

        data_mb = row.get("data_size_mb", row.get("data_size", "1"))
        try:
            data_size_kb = float(data_mb) * 1024.0
        except (TypeError, ValueError):
            data_size_kb = 10.0

        cpu_pct = row.get("cpu_usage_pct", row.get("cpu_usage", "30"))
        try:
            edge_cpu = min(1.0, max(0.0, float(cpu_pct) / 100.0))
        except (TypeError, ValueError):
            edge_cpu = 0.3

        net_lat = row.get("network_latency_ms", row.get("network_latency", "50"))
        try:
            network_delay_ms = float(net_lat)
        except (TypeError, ValueError):
            network_delay_ms = 50.0

        device_id = row.get("device_id", row.get("device", f"device_{i+1}"))
        out_rows.append({
            "timestamp": (base_time + timedelta(seconds=i * 2)).isoformat() + "Z",
            "device_id": f"device_{device_id}",
            "task_type": mapped_type,
            "priority": priority,
            "data_size_kb": round(data_size_kb, 2),
            "compute_cost": round(compute_cost, 3),
            "deadline_ms": int(deadline_ms),
            "edge_cpu_load": round(edge_cpu, 3),
            "network_delay_ms": round(network_delay_ms, 1),
        })

    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MEC_FIELDS)
        w.writeheader()
        w.writerows(out_rows)
    return {"rows": len(out_rows), "converter": "mobile_edge_dataset"}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def convert_eua_csv(
    users_src: Path,
    edge_sites_src: Path,
    dest: Path,
    max_users: int = 1000,
) -> Dict[str, Any]:
    """PhuLai/eua-dataset → eua_users.csv schema。"""
    if validate_eua_schema(users_src) and users_src.resolve() != dest.resolve():
        dest.write_bytes(users_src.read_bytes())
        _, rows = _read_csv_rows(dest)
        return {"rows": len(rows), "converter": "passthrough"}

    _, user_rows = _read_csv_rows(users_src, limit=max_users)
    _, site_rows = _read_csv_rows(edge_sites_src, limit=5000)
    if not user_rows:
        raise ValueError(f"Empty EUA users CSV: {users_src}")
    if not site_rows:
        raise ValueError(f"Empty EUA edge sites CSV: {edge_sites_src}")

    sites = []
    for s in site_rows:
        try:
            sites.append({
                "id": str(s.get("site_id", s.get("id", ""))),
                "lat": float(s.get("latitude", s.get("lat", 0))),
                "lon": float(s.get("longitude", s.get("lon", 0))),
            })
        except (TypeError, ValueError):
            continue
    if not sites:
        raise ValueError("No valid edge sites parsed")

    rng = random.Random(42)
    out_rows: List[Dict[str, Any]] = []
    for i, u in enumerate(user_rows):
        try:
            lat = float(u.get("latitude", u.get("lat", 0)))
            lon = float(u.get("longitude", u.get("lon", 0)))
        except (TypeError, ValueError):
            continue
        nearest = min(sites, key=lambda s: _haversine_km(lat, lon, s["lat"], s["lon"]))
        out_rows.append({
            "user_id": u.get("user_id", u.get("ip", f"user_{i:04d}")),
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "edge_node_id": nearest["id"],
            "request_rate": round(rng.uniform(0.2, 2.0), 3),
            "avg_data_size_kb": round(rng.uniform(5, 256), 2),
            "avg_compute_cost": round(rng.uniform(0.1, 0.7), 3),
        })

    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=EUA_FIELDS)
        w.writeheader()
        w.writerows(out_rows)
    return {"rows": len(out_rows), "converter": "phulai_eua_dataset"}
