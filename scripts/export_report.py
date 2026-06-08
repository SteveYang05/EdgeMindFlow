#!/usr/bin/env python3
"""ComputerNet automated experiment report — LATE Framework 7-strategy baseline comparison."""
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results"

ALL_STRATEGIES = ["local_only", "cloud_only", "edge_only", "static_rule", "dynamic", "learned_late", "late_rl"]
METHOD_LABEL = "Dynamic / LATE-Offload"


def load_results():
    csv_path = RESULTS_DIR / "experiment_summary.csv"
    json_path = RESULTS_DIR / "experiment_summary.json"
    rows = []
    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            rows = json.load(f).get("results", [])
    elif csv_path.exists():
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    if not rows:
        return rows
    exp_ids = [r.get("experiment_id") for r in rows if r.get("experiment_id")]
    if exp_ids:
        latest = exp_ids[-1]
        latest_rows = [r for r in rows if r.get("experiment_id") == latest]
        if latest_rows:
            return latest_rows
    return rows


def _f(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _pct_improve(baseline, ours, higher_is_better=False):
    if baseline is None or ours is None or baseline <= 0:
        return None
    if higher_is_better:
        return (ours - baseline) / baseline * 100
    return (baseline - ours) / baseline * 100


def compute_conclusions(rows):
    conclusions = []
    if not rows:
        return ["Insufficient experiment data to compute this conclusion. Run bash scripts/run_experiment.sh first."]

    by_key = {(r.get("scenario"), r.get("strategy")): r for r in rows}

    def get(scenario, strategy, field):
        r = by_key.get((scenario, strategy))
        return _f(r.get(field)) if r and r.get(field) not in (None, "") else None

    d_lat = get("cloud_delay", "dynamic", "avg_latency_ms")
    c_lat = get("cloud_delay", "cloud_only", "avg_latency_ms")
    pct = _pct_improve(c_lat, d_lat)
    if pct is not None and pct > 0:
        conclusions.append(
            f"Under cloud_delay, {METHOD_LABEL} reduces average latency by {pct:.1f}% vs Cloud-Only."
        )
    elif pct is not None:
        conclusions.append(f"Under cloud_delay, {METHOD_LABEL} shows no clear average latency improvement vs Cloud-Only.")
    else:
        conclusions.append("Insufficient cloud_delay data to compare LATE-Offload vs Cloud-Only average latency.")

    d_p95 = get("edge_overload", "dynamic", "p95_latency_ms")
    e_p95 = get("edge_overload", "edge_only", "p95_latency_ms")
    pct = _pct_improve(e_p95, d_p95)
    if pct is not None and pct > 0:
        conclusions.append(
            f"Under edge_overload, {METHOD_LABEL} improves P95 latency by {pct:.1f}% vs Edge-Only."
        )
    elif pct is not None:
        conclusions.append(f"Under edge_overload, {METHOD_LABEL} shows no clear P95 improvement vs Edge-Only.")
    else:
        conclusions.append("Insufficient edge_overload data to compare LATE-Offload vs Edge-Only P95 latency.")

    e_dyn = get("emergency", "dynamic", "urgent_avg_latency_ms")
    e_cloud = get("emergency", "cloud_only", "urgent_avg_latency_ms")
    e_static = get("emergency", "static_rule", "urgent_avg_latency_ms")
    if e_dyn is not None and e_cloud is not None and e_dyn > 0 and e_cloud > 0:
        if e_dyn < e_cloud:
            conclusions.append(
                f"Under emergency, {METHOD_LABEL} urgent-task avg latency ({e_dyn:.1f}ms) is lower than Cloud-Only ({e_cloud:.1f}ms)."
            )
        else:
            conclusions.append("Under emergency, LATE-Offload vs Cloud-Only urgent-task latency needs further validation.")
    else:
        conclusions.append("Insufficient emergency data to compare LATE-Offload vs Cloud-Only urgent-task response.")

    if e_dyn is not None and e_static is not None and e_dyn > 0 and e_static > 0:
        if e_dyn <= e_static:
            conclusions.append(
                f"Under emergency, {METHOD_LABEL} ({e_dyn:.1f}ms) matches or beats Static-Rule ({e_static:.1f}ms) "
                f"for urgent tasks (Static-Rule is load-unaware; LATE-Offload adapts)."
            )
        else:
            conclusions.append(
                f"Under emergency, Static-Rule ({e_static:.1f}ms) urgent-task response beats LATE-Offload ({e_dyn:.1f}ms)."
            )
    else:
        conclusions.append("Insufficient emergency data to compare LATE-Offload vs Static-Rule urgent-task response.")

    d_avg = get("normal", "dynamic", "avg_latency_ms")
    s_avg = get("normal", "static_rule", "avg_latency_ms")
    d_viol = get("normal", "dynamic", "deadline_violation_rate")
    s_viol = get("normal", "static_rule", "deadline_violation_rate")
    if d_avg is not None and s_avg is not None:
        conclusions.append(
            f"Under normal, {METHOD_LABEL} avg latency {d_avg:.1f}ms vs Static-Rule {s_avg:.1f}ms; "
            f"violation rate {d_viol or 0:.1f}% vs {s_viol or 0:.1f}% — LATE-Offload is more balanced across scenario changes."
        )
    else:
        conclusions.append("Insufficient normal-scenario data to compare LATE-Offload vs Static-Rule overall balance.")

    d_qos = get("normal", "dynamic", "qos_satisfaction_rate")
    c_qos = get("normal", "cloud_only", "qos_satisfaction_rate")
    s_qos = get("normal", "static_rule", "qos_satisfaction_rate")
    l_qos = get("normal", "local_only", "qos_satisfaction_rate")
    if d_qos is not None and d_qos > 0:
        conclusions.append(
            f"Under normal, {METHOD_LABEL} QoS Satisfaction Rate is {d_qos:.1f}%"
            + (f", higher than Cloud-Only ({c_qos:.1f}%)." if c_qos and d_qos > c_qos else ".")
        )
    if d_qos and s_qos and d_qos > 0 and s_qos > 0:
        conclusions.append(
            f"QoS comparison: LATE-Offload {d_qos:.1f}% vs Static-Rule {s_qos:.1f}% vs Local-Only {l_qos or 0:.1f}%."
        )

    l_avg = get("normal", "local_only", "avg_latency_ms")
    if d_avg is not None and l_avg is not None:
        conclusions.append(
            f"Under normal, {METHOD_LABEL} ({d_avg:.1f}ms) vs Local-Only ({l_avg:.1f}ms) "
            f"achieves better resource utilization and latency balance via edge/cloud offloading."
        )

    eo_avg = get("normal", "edge_only", "avg_latency_ms")
    if d_avg is not None and eo_avg is not None:
        conclusions.append(
            f"Under normal, {METHOD_LABEL} ({d_avg:.1f}ms) vs Edge-Only ({eo_avg:.1f}ms) "
            f"flexibly selects execution location by task characteristics."
        )

    return conclusions


def export_latency_comparison(rows):
    path = RESULTS_DIR / "latency_comparison.csv"
    fields = [
        "scenario", "strategy", "avg_latency_ms", "p95_latency_ms",
        "urgent_avg_latency_ms", "qos_satisfaction_rate",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    return path


def export_strategy_comparison(rows):
    path = RESULTS_DIR / "strategy_comparison.json"
    grouped = defaultdict(list)
    for r in rows:
        grouped[r.get("strategy", "unknown")].append(r)
    summary = {}
    for strategy in ALL_STRATEGIES:
        items = grouped.get(strategy, [])
        lats = [_f(i.get("avg_latency_ms")) for i in items if _f(i.get("avg_latency_ms")) > 0]
        p95s = [_f(i.get("p95_latency_ms")) for i in items if _f(i.get("p95_latency_ms")) > 0]
        qoss = [_f(i.get("qos_satisfaction_rate")) for i in items if _f(i.get("qos_satisfaction_rate")) > 0]
        label = "LATE-Offload" if strategy == "dynamic" else (
            "LATE-Learn" if strategy == "learned_late" else (
                "LATE-RL" if strategy == "late_rl" else strategy
            )
        )
        summary[strategy] = {
            "label": label,
            "experiments": len(items),
            "avg_latency_ms": round(sum(lats) / len(lats), 2) if lats else 0,
            "p95_latency_ms": round(sum(p95s) / len(p95s), 2) if p95s else 0,
            "qos_satisfaction_rate": round(sum(qoss) / len(qoss), 2) if qoss else 0,
            "scenarios": list({i.get("scenario") for i in items}),
        }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    return path


def _load_late_learn_meta():
    meta_path = PROJECT_ROOT / "ml" / "models" / "model_metadata.json"
    eval_path = PROJECT_ROOT / "ml" / "models" / "evaluation_report.json"
    meta, eval_report = {}, {}
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    if eval_path.exists():
        with open(eval_path, encoding="utf-8") as f:
            eval_report = json.load(f)
    return meta, eval_report


def _late_learn_sections():
    meta, eval_report = _load_late_learn_meta()
    lines = [
        "## LATE-Learn Oracle Labeling",
        "",
        "LATE-Learn **does more than mimic LATE-Offload**. By default it uses **Oracle Cost Labeling**:",
        "for each task state, simulate local / edge / cloud costs simultaneously,",
        "and use the lowest-cost location as the training label.",
        "",
        f"- **label_source (default)**: {meta.get('label_source', 'oracle')}",
        "- **teacher mode**: kept for compatibility, ablation comparison only (`LATE_LEARN_LABEL_SOURCE=teacher`)",
        "- Oracle cost components: latency + load + transfer + deadline + safety + qos penalties",
        "",
    ]
    if meta.get("public_trace_used") is not None:
        lines.append(f"- public_trace_used: {meta.get('public_trace_used')}")
    if meta.get("fallback_used") is not None:
        lines.append(f"- fallback_used: {meta.get('fallback_used')}")
    lines += [
        "",
        "## LATE-Learn Regret Evaluation",
        "",
        "Regret measures the gap between learned strategy and oracle optimal cost (lower is better):",
        "",
        f"- **oracle_agreement**: {meta.get('oracle_agreement', eval_report.get('oracle_agreement', 'N/A'))}",
        f"- **avg_predicted_cost**: {meta.get('avg_predicted_cost', eval_report.get('avg_predicted_cost', 'N/A'))}",
        f"- **avg_oracle_cost**: {meta.get('avg_oracle_cost', eval_report.get('avg_oracle_cost', 'N/A'))}",
        f"- **avg_regret**: {meta.get('avg_regret', eval_report.get('avg_regret', 'N/A'))}",
        "",
        "If avg_regret is near 0, LATE-Learn has learned an offloading mapping close to oracle.",
        "See `results/late_learn_evaluation.md` and `ml/models/evaluation_report.json`.",
        "",
        "## LATE-Learn Ablation Study",
        "",
    ]
    ablation_csv = RESULTS_DIR / "late_learn_ablation.csv"
    ablation_md = RESULTS_DIR / "late_learn_ablation.md"
    if ablation_csv.exists():
        lines.append("Ablation comparing full / no_trace / no_scenario / task_only feature subsets:")
        lines.append("")
        lines.append("| variant | oracle_agreement | avg_regret | feature_count |")
        lines.append("|---------|------------------|------------|---------------|")
        with open(ablation_csv, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                lines.append(
                    f"| {row.get('variant','')} | {row.get('oracle_agreement','')} | "
                    f"{row.get('avg_regret','')} | {row.get('feature_count','')} |"
                )
        lines.append("")
        lines.append(f"Full results: `{ablation_csv.name}`, `{ablation_md.name}`")
    else:
        lines.append(
            "Ablation results are not available. Run `python ml/ablation_late_learn.py` first."
        )
    lines.append("")
    return lines


def _late_rl_sections():
    lines = [
        "## Reinforcement Learning Enhancement: LATE-RL",
        "",
        "LATE-Learn is **supervised learning**, learning single-step oracle labels;",
        "LATE-RL is **reinforcement learning enhancement**, optimizing long-term reward over continuous task streams.",
        "",
        "Reward components: latency, deadline, overload, safety, transfer penalties/bonuses.",
        "LATE-RL may not beat LATE-Learn overall, but demonstrates dynamic queuing and long-term optimization.",
        "Falls back to LATE-Learn / LATE-Offload when no model is available.",
        "",
        "## LATE-RL Training Curve",
        "",
    ]
    curve_path = RESULTS_DIR / "late_rl_training_curve.csv"
    if curve_path.exists():
        with open(curve_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        last = rows[-10:] if len(rows) >= 10 else rows
        lines.append("| episode | total_reward | avg_latency | deadline_violation_rate |")
        lines.append("|---------|--------------|-------------|-------------------------|")
        for r in last:
            lines.append(
                f"| {r.get('episode','')} | {r.get('total_reward','')} | "
                f"{r.get('avg_latency','')} | {r.get('deadline_violation_rate','')} |"
            )
    else:
        lines.append("LATE-RL results are not available. Run `bash scripts/train_late_rl.sh` first.")
    lines += ["", "## LATE-RL Evaluation", ""]
    eval_path = RESULTS_DIR / "late_rl_evaluation.json"
    if eval_path.exists():
        with open(eval_path, encoding="utf-8") as f:
            ev = json.load(f)
        lines.append(f"- **avg_reward**: {ev.get('avg_reward', 'N/A')}")
        lines.append(f"- **avg_latency**: {ev.get('avg_latency', 'N/A')} ms")
        lines.append(f"- **deadline_violation_rate**: {ev.get('deadline_violation_rate', 'N/A')}")
        lines.append(f"- **action_distribution**: {ev.get('action_distribution', 'N/A')}")
    else:
        lines.append("LATE-RL evaluation not available. Run `python scripts/evaluate_late_rl.py` first.")
    lines += [
        "",
        "## Digital Twin Smart Park",
        "",
        "This project wraps the IoT device simulator, network topology, scenario engine, edge/cloud metrics, and task workload",
        "into a **Digital Twin Smart Park** experimental environment for validating offloading strategies.",
        "API: `GET /api/digital_twin/status`; Dashboard shows Device/Network/Edge/Cloud/Workload Twin.",
        "",
    ]
    return lines


def generate_report(rows):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = RESULTS_DIR / "report.md"

    exp_ids = list({r.get("experiment_id") for r in rows if r.get("experiment_id")})
    exp_id = exp_ids[-1] if exp_ids else "N/A"
    durations = list({r.get("duration_sec") for r in rows if r.get("duration_sec")})
    duration = durations[0] if durations else "N/A"

    lines = [
        "# ComputerNet Automated Experiment Report",
        "",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "## Proposed Method: LATE-Offload",
        "",
        "**LATE-Offload** (Latency-Aware and Task-priority Enhanced Edge Offloading)",
        "latency-aware, task-priority-enhanced edge compute offloading method.",
        "",
        "API strategy name remains `dynamic`; Dashboard displays **Dynamic / LATE-Offload**.",
        "",
        "### Three-Stage Design",
        "",
        "1. **Stage 1 — Task Profiling**: build task profile (priority, deadline, data_size, compute_cost, risk_level, task_category)",
        "2. **Stage 2 — Multi-objective Cost Estimation**: estimate latency, load, transfer, deadline risk, priority penalty, QoS risk for local/edge/cloud, with Scenario-Adaptive Weighting",
        "3. **Stage 3 — Constraint-aware Decision**: safety-critical edge reservation (Safety Edge Reservation), score-based decision and explainable reason",
        "",
        "Flowchart: `docs/figures/late_offload_method.mmd`",
        "",
        "## Experiment Setup",
        "",
        f"- **Experiment ID**: {exp_id}",
        f"- **Scenarios**: normal, cloud_delay, edge_overload, emergency",
        f"- **Strategies**: local_only, cloud_only, edge_only, static_rule, dynamic (LATE-Offload), learned_late (LATE-Learn), late_rl (LATE-RL)",
        f"- **Duration per group**: {duration} seconds",
        f"- **Experiment groups**: {len(rows)}",
        "",
        "### Baseline Descriptions",
        "",
        "| Strategy | Type |",
        "|----------|------|",
        "| local_only | Local execution baseline |",
        "| cloud_only | Cloud-centric processing baseline |",
        "| edge_only | Edge-centric processing baseline |",
        "| static_rule | Fixed-rule engineering baseline |",
        "| dynamic | **LATE-Offload proposed method (this project)** |",
        "| learned_late | **LATE-Learn trace-learned strategy** |",
        "| late_rl | **LATE-RL reinforcement-learning enhancement** |",
        "",
        "## Overall Results Table",
        "",
        "| Scenario | Strategy | Tasks | Avg(ms) | P95(ms) | QoS% | Urgent Avg | Violation% | local | edge | cloud |",
        "|----------|----------|-------|---------|---------|------|------------|------------|-------|------|-------|",
    ]

    for r in rows:
        strat = r.get("strategy", "")
        if strat == "dynamic":
            strat = "dynamic (LATE)"
        lines.append(
            f"| {r.get('scenario','')} | {strat} | {r.get('total_tasks','0')} | "
            f"{r.get('avg_latency_ms','0')} | {r.get('p95_latency_ms','0')} | "
            f"{r.get('qos_satisfaction_rate','0')} | {r.get('urgent_avg_latency_ms','0')} | "
            f"{r.get('deadline_violation_rate','0')} | "
            f"{r.get('local_task_count','0')} | {r.get('edge_task_count','0')} | "
            f"{r.get('cloud_task_count','0')} |"
        )

    lines += ["", f"## {METHOD_LABEL} vs Baseline Key Conclusions", ""]
    for c in compute_conclusions(rows):
        lines.append(f"- {c}")

    lines += _late_learn_sections()
    lines += _late_rl_sections()

    lines += [
        "",
        "## Output Files",
        "",
        "- `results/experiment_summary.csv`",
        "- `results/experiment_summary.json`",
        "- `results/latency_comparison.csv`",
        "- `results/strategy_comparison.json`",
        "",
    ]

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    export_latency_comparison(rows)
    export_strategy_comparison(rows)
    return report_path


def main():
    rows = load_results()
    if not rows:
        print("[Warning] No experiment data found. Run: bash scripts/run_experiment.sh")
        sys.exit(1)
    path = generate_report(rows)
    strategies_found = {r.get("strategy") for r in rows}
    print(f"Report generated: {path}")
    print(f"Strategy coverage: {', '.join(sorted(strategies_found))}")
    missing = set(ALL_STRATEGIES) - strategies_found
    if missing:
        print(f"[Note] Missing strategy data: {', '.join(sorted(missing))}")


if __name__ == "__main__":
    main()
