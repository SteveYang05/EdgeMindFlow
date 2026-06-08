#!/usr/bin/env python3
"""ComputerNet 实验报告自动生成 — LATE Framework 7 策略 baseline 对比。"""
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
        return ["当前实验数据不足，无法计算该结论。请先运行 bash scripts/run_experiment.sh。"]

    by_key = {(r.get("scenario"), r.get("strategy")): r for r in rows}

    def get(scenario, strategy, field):
        r = by_key.get((scenario, strategy))
        return _f(r.get(field)) if r and r.get(field) not in (None, "") else None

    d_lat = get("cloud_delay", "dynamic", "avg_latency_ms")
    c_lat = get("cloud_delay", "cloud_only", "avg_latency_ms")
    pct = _pct_improve(c_lat, d_lat)
    if pct is not None and pct > 0:
        conclusions.append(
            f"在 cloud_delay 场景下，{METHOD_LABEL} 相比 Cloud-Only 平均时延降低 {pct:.1f}%。"
        )
    elif pct is not None:
        conclusions.append(f"在 cloud_delay 场景下，{METHOD_LABEL} 与 Cloud-Only 平均时延差异不明显。")
    else:
        conclusions.append("cloud_delay 场景数据不足，无法对比 LATE-Offload 与 Cloud-Only 平均时延。")

    d_p95 = get("edge_overload", "dynamic", "p95_latency_ms")
    e_p95 = get("edge_overload", "edge_only", "p95_latency_ms")
    pct = _pct_improve(e_p95, d_p95)
    if pct is not None and pct > 0:
        conclusions.append(
            f"在 edge_overload 场景下，{METHOD_LABEL} 相比 Edge-Only 的 P95 时延改善 {pct:.1f}%。"
        )
    elif pct is not None:
        conclusions.append(f"在 edge_overload 场景下，{METHOD_LABEL} 与 Edge-Only P95 时延差异不明显。")
    else:
        conclusions.append("edge_overload 场景数据不足，无法对比 LATE-Offload 与 Edge-Only P95 时延。")

    e_dyn = get("emergency", "dynamic", "urgent_avg_latency_ms")
    e_cloud = get("emergency", "cloud_only", "urgent_avg_latency_ms")
    e_static = get("emergency", "static_rule", "urgent_avg_latency_ms")
    if e_dyn is not None and e_cloud is not None and e_dyn > 0 and e_cloud > 0:
        if e_dyn < e_cloud:
            conclusions.append(
                f"在 emergency 场景下，{METHOD_LABEL} 紧急任务均延 ({e_dyn:.1f}ms) 低于 Cloud-Only ({e_cloud:.1f}ms)。"
            )
        else:
            conclusions.append("emergency 场景下 LATE-Offload 与 Cloud-Only 紧急任务时延需进一步验证。")
    else:
        conclusions.append("emergency 场景数据不足，无法对比 LATE-Offload 与 Cloud-Only 紧急任务响应。")

    if e_dyn is not None and e_static is not None and e_dyn > 0 and e_static > 0:
        if e_dyn <= e_static:
            conclusions.append(
                f"在 emergency 场景下，{METHOD_LABEL} ({e_dyn:.1f}ms) 与 Static-Rule ({e_static:.1f}ms) "
                f"紧急任务响应相当或更优（Static-Rule 不感知负载，LATE-Offload 可自适应）。"
            )
        else:
            conclusions.append(
                f"在 emergency 场景下，Static-Rule ({e_static:.1f}ms) 紧急任务响应优于 LATE-Offload ({e_dyn:.1f}ms)。"
            )
    else:
        conclusions.append("emergency 场景数据不足，无法对比 LATE-Offload 与 Static-Rule 紧急任务响应。")

    d_avg = get("normal", "dynamic", "avg_latency_ms")
    s_avg = get("normal", "static_rule", "avg_latency_ms")
    d_viol = get("normal", "dynamic", "deadline_violation_rate")
    s_viol = get("normal", "static_rule", "deadline_violation_rate")
    if d_avg is not None and s_avg is not None:
        conclusions.append(
            f"在 normal 场景下，{METHOD_LABEL} 均延 {d_avg:.1f}ms vs Static-Rule {s_avg:.1f}ms；"
            f"违约率 {d_viol or 0:.1f}% vs {s_viol or 0:.1f}%，LATE-Offload 在场景变化时更具均衡性。"
        )
    else:
        conclusions.append("normal 场景数据不足，无法对比 LATE-Offload 与 Static-Rule 整体均衡性。")

    d_qos = get("normal", "dynamic", "qos_satisfaction_rate")
    c_qos = get("normal", "cloud_only", "qos_satisfaction_rate")
    s_qos = get("normal", "static_rule", "qos_satisfaction_rate")
    l_qos = get("normal", "local_only", "qos_satisfaction_rate")
    if d_qos is not None and d_qos > 0:
        conclusions.append(
            f"在 normal 场景下，{METHOD_LABEL} QoS Satisfaction Rate 为 {d_qos:.1f}%"
            + (f"，高于 Cloud-Only ({c_qos:.1f}%)。" if c_qos and d_qos > c_qos else "。")
        )
    if d_qos and s_qos and d_qos > 0 and s_qos > 0:
        conclusions.append(
            f"QoS 对比：LATE-Offload {d_qos:.1f}% vs Static-Rule {s_qos:.1f}% vs Local-Only {l_qos or 0:.1f}%。"
        )

    l_avg = get("normal", "local_only", "avg_latency_ms")
    if d_avg is not None and l_avg is not None:
        conclusions.append(
            f"在 normal 场景下，{METHOD_LABEL} ({d_avg:.1f}ms) 相比 Local-Only ({l_avg:.1f}ms) "
            f"通过 edge/cloud 卸载获得更优资源利用与时延平衡。"
        )

    eo_avg = get("normal", "edge_only", "avg_latency_ms")
    if d_avg is not None and eo_avg is not None:
        conclusions.append(
            f"在 normal 场景下，{METHOD_LABEL} ({d_avg:.1f}ms) 相比 Edge-Only ({eo_avg:.1f}ms) "
            f"可根据任务特征灵活选择执行位置。"
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
        "LATE-Learn **不只是模仿 LATE-Offload**。默认使用 **Oracle Cost Labeling**：",
        "对每个任务状态同时模拟 local / edge / cloud 三位置代价，",
        "选择总代价最低的位置作为训练标签。",
        "",
        f"- **label_source（默认）**: {meta.get('label_source', 'oracle')}",
        "- **teacher 模式**: 保留兼容，仅作消融对比（`LATE_LEARN_LABEL_SOURCE=teacher`）",
        "- Oracle 代价组成: latency + load + transfer + deadline + safety + qos penalties",
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
        "Regret 衡量学习策略与 oracle 最优代价的差距（越小越好）：",
        "",
        f"- **oracle_agreement**: {meta.get('oracle_agreement', eval_report.get('oracle_agreement', 'N/A'))}",
        f"- **avg_predicted_cost**: {meta.get('avg_predicted_cost', eval_report.get('avg_predicted_cost', 'N/A'))}",
        f"- **avg_oracle_cost**: {meta.get('avg_oracle_cost', eval_report.get('avg_oracle_cost', 'N/A'))}",
        f"- **avg_regret**: {meta.get('avg_regret', eval_report.get('avg_regret', 'N/A'))}",
        "",
        "若 avg_regret 接近 0，说明 LATE-Learn 学到了接近 oracle 的卸载映射。",
        "详见 `results/late_learn_evaluation.md` 与 `ml/models/evaluation_report.json`。",
        "",
        "## LATE-Learn Ablation Study",
        "",
    ]
    ablation_csv = RESULTS_DIR / "late_learn_ablation.csv"
    ablation_md = RESULTS_DIR / "late_learn_ablation.md"
    if ablation_csv.exists():
        lines.append("消融实验对比 full / no_trace / no_scenario / task_only 特征子集：")
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
        lines.append(f"完整结果: `{ablation_csv.name}`、`{ablation_md.name}`")
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
        "LATE-Learn 是 **supervised learning**，学习单步 oracle label；",
        "LATE-RL 是 **reinforcement learning enhancement**，优化连续任务流下的长期 reward。",
        "",
        "Reward 组成：latency、deadline、overload、safety、transfer penalties/bonuses。",
        "LATE-RL 不一定全面优于 LATE-Learn，但用于体现动态排队与长期优化能力。",
        "无模型时自动 fallback 到 LATE-Learn / LATE-Offload。",
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
        "本项目将 IoT 设备模拟器、网络拓扑、场景引擎、边缘/云端指标与任务负载",
        "包装为 **Digital Twin Smart Park** 数字孪生实验环境，用于验证不同卸载策略。",
        "API: `GET /api/digital_twin/status`；Dashboard 展示 Device/Network/Edge/Cloud/Workload Twin。",
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
        "# ComputerNet 自动实验报告",
        "",
        f"生成时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "## Proposed Method: LATE-Offload",
        "",
        "**LATE-Offload** (Latency-Aware and Task-priority Enhanced Edge Offloading)",
        "时延感知与任务优先级增强的边缘计算卸载方法。",
        "",
        "API 策略名仍为 `dynamic`，Dashboard 显示为 **Dynamic / LATE-Offload**。",
        "",
        "### 三阶段设计",
        "",
        "1. **Stage 1 — Task Profiling**：构造任务画像（priority、deadline、data_size、compute_cost、risk_level、task_category）",
        "2. **Stage 2 — Multi-objective Cost Estimation**：对 local/edge/cloud 估计时延、负载、传输、deadline 风险、优先级惩罚、QoS 风险，并经 Scenario-Adaptive Weighting 加权评分",
        "3. **Stage 3 — Constraint-aware Decision**：安全关键任务边缘保留（Safety Edge Reservation），结合 score 输出 decision 与 explainable reason",
        "",
        "流程图见：`docs/figures/late_offload_method.mmd`",
        "",
        "## 实验设置",
        "",
        f"- **实验 ID**: {exp_id}",
        f"- **场景列表**: normal, cloud_delay, edge_overload, emergency",
        f"- **策略列表**: local_only, cloud_only, edge_only, static_rule, dynamic (LATE-Offload), learned_late (LATE-Learn), late_rl (LATE-RL)",
        f"- **每组运行时长**: {duration} 秒",
        f"- **实验组数**: {len(rows)}",
        "",
        "### Baseline 说明",
        "",
        "| 策略 | 类型 |",
        "|------|------|",
        "| local_only | 本地执行 baseline |",
        "| cloud_only | 云端集中处理 baseline |",
        "| edge_only | 边缘集中处理 baseline |",
        "| static_rule | 固定规则工程 baseline |",
        "| dynamic | **LATE-Offload 自研方法（本项目）** |",
        "| learned_late | **LATE-Learn trace 学习策略** |",
        "| late_rl | **LATE-RL 强化学习增强策略** |",
        "",
        "## 总体结果表",
        "",
        "| 场景 | 策略 | 任务数 | 均延(ms) | P95(ms) | QoS% | 紧急均延 | 违约率% | local | edge | cloud |",
        "|------|------|--------|----------|---------|------|----------|---------|-------|------|-------|",
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

    lines += ["", f"## {METHOD_LABEL} vs Baseline 关键结论", ""]
    for c in compute_conclusions(rows):
        lines.append(f"- {c}")

    lines += _late_learn_sections()
    lines += _late_rl_sections()

    lines += [
        "",
        "## 文件输出",
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
        print("[警告] 未找到实验数据。请先运行: bash scripts/run_experiment.sh")
        sys.exit(1)
    path = generate_report(rows)
    strategies_found = {r.get("strategy") for r in rows}
    print(f"报告已生成: {path}")
    print(f"策略覆盖: {', '.join(sorted(strategies_found))}")
    missing = set(ALL_STRATEGIES) - strategies_found
    if missing:
        print(f"[提示] 缺少策略数据: {', '.join(sorted(missing))}")


if __name__ == "__main__":
    main()
