"""LATE-Learn model evaluation — Regret metrics."""
from typing import Any, Dict, List, Optional

import numpy as np

from backend.ml.features import label_to_location, location_to_label


def _cost_for_label(record: Dict[str, Any], label: int) -> float:
    loc = label_to_location(label)
    key = f"oracle_{loc}_cost"
    return float(record.get(key, record.get(f"oracle_{loc}_cost", 0)))


def oracle_cost_for_location(record: Dict[str, Any], location: str) -> float:
    return float(record.get(f"oracle_{location}_cost", 0))


def compute_regret_metrics(
    y_true_oracle: np.ndarray,
    y_pred: np.ndarray,
    records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute oracle agreement and regret metrics."""
    n = len(records)
    if n == 0:
        return {
            "oracle_agreement": 0.0,
            "avg_predicted_cost": 0.0,
            "avg_oracle_cost": 0.0,
            "avg_regret": 0.0,
            "regret_vs_teacher": None,
            "regret_vs_static_rule": None,
        }

    oracle_labels = np.array([location_to_label(r["oracle_label"]) for r in records])
    agreement = float(np.mean(y_pred == oracle_labels))

    pred_costs = []
    oracle_costs = []
    teacher_costs = []
    static_costs = []
    for i, rec in enumerate(records):
        pred_loc = label_to_location(int(y_pred[i]))
        pred_costs.append(oracle_cost_for_location(rec, pred_loc))
        oracle_costs.append(oracle_cost_for_location(rec, rec["oracle_label"]))
        if rec.get("teacher_decision"):
            teacher_costs.append(oracle_cost_for_location(rec, rec["teacher_decision"]))
        if rec.get("static_rule_decision"):
            static_costs.append(oracle_cost_for_location(rec, rec["static_rule_decision"]))

    avg_pred = float(np.mean(pred_costs))
    avg_oracle = float(np.mean(oracle_costs))
    avg_regret = avg_pred - avg_oracle

    regret_teacher = None
    if teacher_costs:
        regret_teacher = float(np.mean(teacher_costs)) - avg_pred

    regret_static = None
    if static_costs:
        regret_static = float(np.mean(static_costs)) - avg_pred

    return {
        "oracle_agreement": round(agreement, 4),
        "avg_predicted_cost": round(avg_pred, 6),
        "avg_oracle_cost": round(avg_oracle, 6),
        "avg_regret": round(avg_regret, 6),
        "regret_vs_teacher": round(regret_teacher, 6) if regret_teacher is not None else None,
        "regret_vs_static_rule": round(regret_static, 6) if regret_static is not None else None,
        "test_samples": n,
    }
