"""LATE-Learn inference — learned_late strategy."""
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import joblib
import numpy as np

from backend.common.config import LATE_LEARN_MODEL_PATH
from backend.edge_server.offloading import TaskContext, build_task_profile
from backend.ml.features import extract_features, label_to_location

logger = logging.getLogger("ml.predictor")
LEARN_METHOD = "LATE-Learn"

_model_cache: Dict[str, Any] = {}


def load_model(path: Path = None) -> Optional[Dict[str, Any]]:
    path = path or LATE_LEARN_MODEL_PATH
    key = str(path)
    if key in _model_cache:
        return _model_cache[key]
    if not path.exists():
        return None
    try:
        payload = joblib.load(path)
        _model_cache[key] = payload
        return payload
    except Exception as e:
        logger.warning("Failed to load LATE-Learn model: %s", e)
        return None


def clear_model_cache() -> None:
    _model_cache.clear()


def predict_offloading(
    task: TaskContext,
    edge_state,
    scenario: str = "normal",
    extra_cloud_delay_ms: float = 0.0,
) -> Tuple[Optional[str], str, bool]:
    payload = load_model()
    if payload is None:
        return None, f"{LEARN_METHOD}: model not found, fallback to LATE-Offload", False

    profile = build_task_profile(task)
    network_delay = edge_state.network_delay_ms + extra_cloud_delay_ms * 0.3
    meta = payload.get("meta", {})
    feature_names = meta.get("feature_names")
    task_dict = {
        "priority": task.priority,
        "deadline_ms": task.deadline_ms,
        "data_size_kb": task.data_size_kb,
        "compute_cost": task.compute_cost,
    }
    feat = extract_features(
        task_dict,
        edge_cpu=edge_state.cpu_load,
        network_delay_ms=network_delay,
        scenario=scenario,
        risk_level=profile.risk_level,
        feature_names=feature_names,
    )
    clf = payload["model"]
    pred = int(clf.predict(feat.reshape(1, -1))[0])
    decision = label_to_location(pred)
    proba = clf.predict_proba(feat.reshape(1, -1))[0]
    conf = float(max(proba))
    label_src = meta.get("label_source", "oracle")
    reason = (
        f"{LEARN_METHOD}: learned policy ({label_src} labels) predicts {decision} "
        f"(confidence={conf:.2f}) from trace-trained CPU model."
    )
    if profile.task_category == "safety_critical" and task.deadline_ms <= 500:
        if decision != "edge":
            decision = "edge"
            reason = (
                f"{LEARN_METHOD}: safety-critical override — edge reserved "
                f"despite learned prediction (confidence={conf:.2f})."
            )
    return decision, reason, True
