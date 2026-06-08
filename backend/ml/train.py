"""LATE-Learn CPU 训练 — Oracle Cost Labeling + Teacher 兼容模式。"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

from backend.common.config import (
    LATE_LEARN_LABEL_SOURCE,
    LATE_LEARN_MIN_SAMPLES,
    LATE_LEARN_MODEL_PATH,
    ML_EVAL_REPORT_PATH,
    ML_METADATA_PATH,
    ML_MODELS_DIR,
    MODELS_DIR,
    RESULTS_DIR,
)
from backend.datasets.manager import DatasetManager
from backend.edge_server.offloading import (
    NodeState,
    TaskContext,
    build_task_profile,
    decide_late_offload,
    decide_static_rule,
)
from backend.ml.evaluate import compute_regret_metrics
from backend.ml.features import FEATURE_VARIANTS, extract_features, location_to_label
from backend.ml.oracle import compute_oracle_labels

logger = logging.getLogger("ml.train")
METHOD_NAME = "LATE-Learn"


def _trace_row_to_task(row: Dict[str, Any]) -> TaskContext:
    return TaskContext(
        task_id=str(row.get("task_id", row.get("timestamp", "trace"))),
        task_type=str(row.get("task_type", "temperature_report")),
        priority=str(row.get("priority", "medium")),
        data_size_kb=float(row.get("data_size_kb", 10)),
        compute_cost=float(row.get("compute_cost", 0.3)),
        deadline_ms=float(row.get("deadline_ms", 1000)),
    )


def _dataset_trace_info(dm: DatasetManager) -> Dict[str, Any]:
    trace_ds = dm.get("mec_edge")
    return {
        "public_trace_used": trace_ds.get("source") == "remote",
        "fallback_used": trace_ds.get("source") == "synthetic",
        "trace_status": trace_ds.get("status"),
        "trace_source": trace_ds.get("source"),
    }


def build_training_records(
    limit: int = 2000,
    scenarios: Optional[List[str]] = None,
    label_source: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """从 MEC trace 构建带 oracle/teacher 标签的训练记录。"""
    label_source = (label_source or LATE_LEARN_LABEL_SOURCE or "oracle").lower()
    if label_source not in ("oracle", "teacher"):
        raise ValueError(f"Invalid label_source: {label_source}")

    scenarios = scenarios or ["normal", "cloud_delay", "edge_overload", "emergency"]
    dm = DatasetManager()
    dm.ensure_default_datasets()
    rows = dm.read_mec_tasks(limit=limit)
    if not rows:
        raise RuntimeError("No trace tasks available for LATE-Learn training")

    trace_info = _dataset_trace_info(dm)
    records: List[Dict[str, Any]] = []
    cloud_state = NodeState(cpu_load=0.3, network_delay_ms=50.0)

    for row in rows:
        task = _trace_row_to_task(row)
        profile = build_task_profile(task)
        edge_cpu = float(row.get("edge_cpu_load", 0.3))
        net_delay = float(row.get("network_delay_ms", 50.0))

        for scenario in scenarios:
            edge_state = NodeState(cpu_load=edge_cpu, network_delay_ms=net_delay)
            extra_cloud = 300.0 if scenario == "cloud_delay" else 0.0
            edge_overloaded = scenario == "edge_overload" or edge_cpu > 0.85

            oracle = compute_oracle_labels(
                task, edge_state, cloud_state, scenario, extra_cloud, edge_overloaded
            )
            teacher_decision, _, _, _ = decide_late_offload(
                task, edge_state, cloud_state, extra_cloud, edge_overloaded, scenario
            )
            static_decision, _ = decide_static_rule(task)

            oracle_label = oracle["oracle_label"]
            teacher_label = teacher_decision
            label = oracle_label if label_source == "oracle" else teacher_label

            rec = {
                "task_type": task.task_type,
                "priority": task.priority,
                "deadline_ms": task.deadline_ms,
                "data_size_kb": task.data_size_kb,
                "compute_cost": task.compute_cost,
                "edge_cpu_load": edge_cpu,
                "network_delay_ms": net_delay,
                "scenario": scenario,
                "risk_level": profile.risk_level,
                "label_source": label_source,
                "oracle_label": oracle_label,
                "teacher_label": teacher_label,
                "teacher_decision": teacher_decision,
                "static_rule_decision": static_decision,
                "label": label,
                "oracle_local_cost": oracle["oracle_local_cost"],
                "oracle_edge_cost": oracle["oracle_edge_cost"],
                "oracle_cloud_cost": oracle["oracle_cloud_cost"],
            }
            records.append(rec)

    return records, trace_info


def records_to_xy(
    records: List[Dict[str, Any]],
    variant: str = "full",
) -> Tuple[np.ndarray, np.ndarray]:
    feature_names = FEATURE_VARIANTS[variant]
    X_list, y_list = [], []
    for rec in records:
        feat = extract_features(
            rec,
            edge_cpu=rec["edge_cpu_load"],
            network_delay_ms=rec["network_delay_ms"],
            scenario=rec["scenario"],
            risk_level=rec["risk_level"],
            feature_names=feature_names,
        )
        X_list.append(feat)
        y_list.append(location_to_label(rec["label"]))
    return np.vstack(X_list), np.array(y_list, dtype=np.int64)


def build_training_set(
    limit: int = 2000,
    scenarios: Optional[List[str]] = None,
    label_source: Optional[str] = None,
    variant: str = "full",
) -> Tuple[np.ndarray, np.ndarray, List[Dict[str, Any]]]:
    records, _ = build_training_records(limit, scenarios, label_source)
    X, y = records_to_xy(records, variant)
    return X, y, records


def _write_evaluation_md(metrics: Dict[str, Any], path: Path) -> None:
    lines = [
        "# LATE-Learn Regret Evaluation",
        "",
        f"生成时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "## 指标",
        "",
        f"- **label_source**: {metrics.get('label_source', 'N/A')}",
        f"- **oracle_agreement**: {metrics.get('oracle_agreement', 0)}",
        f"- **avg_predicted_cost**: {metrics.get('avg_predicted_cost', 0)}",
        f"- **avg_oracle_cost**: {metrics.get('avg_oracle_cost', 0)}",
        f"- **avg_regret**: {metrics.get('avg_regret', 0)}",
        f"- **regret_vs_teacher**: {metrics.get('regret_vs_teacher')}",
        f"- **regret_vs_static_rule**: {metrics.get('regret_vs_static_rule')}",
        "",
        "## 解释",
        "",
        "Regret 越小，说明模型决策越接近 oracle 最优代价。",
        "若 avg_regret 接近 0，说明 LATE-Learn 学到了接近 oracle 的卸载映射。",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def train_late_learn(
    output_path: Path = None,
    limit: int = 2000,
    label_source: Optional[str] = None,
    feature_variant: str = "full",
    save_model: bool = True,
) -> Dict[str, Any]:
    """CPU 训练 RandomForest 并保存模型与评估报告。"""
    output_path = output_path or LATE_LEARN_MODEL_PATH
    label_source = (label_source or LATE_LEARN_LABEL_SOURCE or "oracle").lower()
    if save_model:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
    ML_MODELS_DIR.mkdir(parents=True, exist_ok=True)

    records, trace_info = build_training_records(limit=limit, label_source=label_source)
    feature_names = FEATURE_VARIANTS[feature_variant]
    X, y = records_to_xy(records, feature_variant)

    if len(X) < LATE_LEARN_MIN_SAMPLES:
        raise RuntimeError(f"Insufficient samples: {len(X)} < {LATE_LEARN_MIN_SAMPLES}")

    idx = np.arange(len(records))
    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        X, y, idx, test_size=0.2, random_state=42, stratify=y,
    )
    test_records = [records[i] for i in idx_test]

    clf = RandomForestClassifier(
        n_estimators=64,
        max_depth=12,
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    macro_f1 = f1_score(y_test, y_pred, average="macro", zero_division=0)

    regret = compute_regret_metrics(
        np.array([location_to_label(r["oracle_label"]) for r in test_records]),
        y_pred,
        test_records,
    )

    meta = {
        "method": METHOD_NAME,
        "model_type": "RandomForestClassifier",
        "feature_names": feature_names,
        "feature_variant": feature_variant,
        "feature_count": len(feature_names),
        "label_source": label_source,
        "train_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
        "test_accuracy": round(acc, 4),
        "macro_f1": round(macro_f1, 4),
        "trained_at": datetime.utcnow().isoformat() + "Z",
        **trace_info,
        **regret,
    }

    eval_report = {**meta, "sample_records": records[:5]}
    payload = {"model": clf, "meta": meta}
    if save_model:
        joblib.dump(payload, output_path)

    if feature_variant == "full" and save_model:
        with open(ML_METADATA_PATH, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        with open(ML_EVAL_REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(eval_report, f, indent=2, ensure_ascii=False)
        _write_evaluation_md(meta, RESULTS_DIR / "late_learn_evaluation.md")
        with open(ML_MODELS_DIR / "training_sample.json", "w", encoding="utf-8") as f:
            json.dump(records[:20], f, indent=2, ensure_ascii=False)

    logger.info(
        "LATE-Learn saved: %s label=%s acc=%.3f regret=%.4f",
        output_path if save_model else "(memory)", label_source, acc, regret["avg_regret"],
    )
    return {**meta, "path": str(output_path) if save_model else ""}
