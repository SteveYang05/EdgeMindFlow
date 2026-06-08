"""ValidatorAgent — 意图闭环验证."""
from typing import Any, Dict, List, Optional

from backend.agents.schemas import ValidationResult


class ValidatorAgent:
    def validate(
        self,
        parsed_intent: Dict[str, Any],
        metrics_before: Dict[str, Any],
        metrics_after: Dict[str, Any],
        extra: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        extra = extra or {}
        checks: List[Dict[str, Any]] = []

        if extra.get("mode") == "query":
            if metrics_after.get("total_tasks", 0) == 0 and not metrics_after:
                return ValidationResult(
                    satisfied=False,
                    status="not_enough_data",
                    summary="指标数据不足，请先运行模拟器产生任务流。",
                    checks=[{"name": "data_available", "passed": False}],
                )
            return ValidationResult(
                satisfied=True,
                status="ok",
                summary="查询模式：已读取当前系统指标。",
                checks=[{"name": "query", "passed": True}],
            )

        if not metrics_after:
            return ValidationResult(
                satisfied=False,
                status="not_enough_data",
                summary="验证失败：缺少 metrics_after 数据。",
                checks=checks,
            )

        target_latency = extra.get("target_latency_ms") or parsed_intent.get("target_latency_ms")
        target_qos = extra.get("target_qos_percent") or parsed_intent.get("target_qos_percent")
        avoid_cloud = extra.get("avoid_cloud", parsed_intent.get("avoid_cloud", False))
        emergency = extra.get("emergency_protection", False)

        urgent = metrics_after.get("emergency_avg_latency_ms") or metrics_after.get("avg_latency_ms") or 0
        avg_lat = metrics_after.get("avg_latency_ms") or 0
        qos = metrics_after.get("qos_satisfaction_rate") or 0
        violation = metrics_after.get("deadline_violation_rate") or 0
        cloud_count = metrics_after.get("cloud_task_count") or 0
        total = metrics_after.get("total_tasks") or 0

        if target_latency is not None:
            ref = urgent if urgent > 0 else avg_lat
            passed = ref <= target_latency or violation == 0
            checks.append({
                "name": "target_latency_ms",
                "passed": passed,
                "expected": target_latency,
                "actual": ref,
            })

        if target_qos is not None:
            passed = qos >= target_qos
            checks.append({
                "name": "target_qos_percent",
                "passed": passed,
                "expected": target_qos,
                "actual": qos,
            })

        if avoid_cloud and total > 0:
            cloud_rate = cloud_count / max(total, 1)
            passed = cloud_rate < 0.5 or metrics_after.get("current_strategy") in ("dynamic", "learned_late")
            checks.append({
                "name": "avoid_cloud",
                "passed": passed,
                "cloud_task_count": cloud_count,
                "total_tasks": total,
            })

        if emergency:
            passed = violation == 0 and metrics_after.get("current_scenario") == "emergency"
            checks.append({
                "name": "emergency_protection",
                "passed": passed,
                "deadline_violation_rate": violation,
                "scenario": metrics_after.get("current_scenario"),
            })

        if not checks:
            checks.append({
                "name": "scenario_strategy_applied",
                "passed": True,
                "scenario": metrics_after.get("current_scenario"),
                "strategy": metrics_after.get("current_strategy"),
            })

        satisfied = all(c.get("passed", False) for c in checks) if checks else False
        if total == 0:
            return ValidationResult(
                satisfied=False,
                status="partial",
                summary="策略已应用，但任务样本不足，无法完整验证时延指标。",
                checks=checks,
            )

        summary = "意图验证通过。" if satisfied else "意图尚未完全达成。"
        return ValidationResult(satisfied=satisfied, status="ok" if satisfied else "failed", summary=summary, checks=checks)
