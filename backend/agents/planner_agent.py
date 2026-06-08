"""PlannerAgent — 根据 ParsedIntent 生成 AgentPlan."""
import uuid
from typing import Any, Dict, List

from backend.agents.schemas import AgentPlan, ParsedIntent


class PlannerAgent:
    def plan(self, parsed: ParsedIntent) -> AgentPlan:
        plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        scenario, strategy, rationale = self._recommend(parsed)
        actions = self._build_actions(parsed, scenario, strategy)

        return AgentPlan(
            plan_id=plan_id,
            parsed_intent=parsed,
            recommended_scenario=scenario,
            recommended_strategy=strategy,
            actions=actions,
            expected_metrics={
                "target_latency_ms": parsed.target_latency_ms,
                "target_qos_percent": parsed.target_qos_percent,
                "avoid_cloud": parsed.avoid_cloud,
            },
            rationale=rationale,
        )

    def _recommend(self, parsed: ParsedIntent) -> tuple:
        if parsed.intent_type == "unknown" and not parsed.intent_types:
            return None, None, "意图不明确，建议 dry_run 或补充描述，不执行危险操作。"

        if parsed.intent_type == "experiment_query":
            return parsed.target_scenario or "normal", "dynamic", "查询当前系统状态与指标，不强制切换场景。"

        scenario = parsed.target_scenario
        strategy = parsed.preferred_strategy or "dynamic"

        types = set(parsed.intent_types or [parsed.intent_type])

        if "cloud_avoidance" in types or scenario == "cloud_delay":
            scenario = scenario or "cloud_delay"
            strategy = parsed.preferred_strategy or "learned_late"
            rationale = "云链路劣化场景下，优先 LATE-Learn/LATE-Offload 规避 cloud 高时延。"
        elif "emergency_protection" in types or scenario == "emergency":
            scenario = "emergency"
            strategy = parsed.preferred_strategy or "dynamic"
            rationale = "紧急场景下 Safety Edge Reservation 保障 smoke/access 低时延。"
        elif "edge_overload_mitigation" in types or scenario == "edge_overload":
            scenario = "edge_overload"
            strategy = "dynamic"
            rationale = "边缘过载时分流非关键任务，安全关键任务保留 edge-first。"
        elif "qos_optimization" in types:
            scenario = scenario or "normal"
            strategy = parsed.preferred_strategy or "learned_late"
            rationale = "QoS 优化优先使用 LATE-Learn oracle 映射。"
        elif "latency_guarantee" in types:
            scenario = scenario or "cloud_delay"
            strategy = parsed.preferred_strategy or "dynamic"
            rationale = "时延保障意图，场景自适应卸载。"
        else:
            scenario = scenario or "normal"
            strategy = strategy or "dynamic"
            rationale = "默认使用 LATE-Offload 主策略。"

        if parsed.preferred_strategy:
            strategy = parsed.preferred_strategy

        return scenario, strategy, rationale

    def _build_actions(
        self, parsed: ParsedIntent, scenario: str | None, strategy: str | None
    ) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = [
            {"tool": "run_quick_check", "args": {}},
            {"tool": "get_metrics", "args": {"scope": "recent_100"}},
        ]

        if parsed.intent_type == "experiment_query":
            actions.append({"tool": "validate_intent", "args": {"mode": "query"}})
            return actions

        if scenario:
            actions.append({"tool": "set_scenario", "args": {"scenario": scenario}})
        if strategy:
            actions.append({"tool": "set_strategy", "args": {"strategy": strategy}})

        if "emergency" in (parsed.intent_types or []) or scenario == "emergency":
            if "smoke_alert" in parsed.target_task_types or "烟雾" in parsed.raw_text:
                actions.append({"tool": "trigger_smoke_alert", "args": {}})

        actions.append({"tool": "get_metrics", "args": {"scope": "recent_100"}})
        actions.append({
            "tool": "validate_intent",
            "args": {
                "target_latency_ms": parsed.target_latency_ms,
                "target_qos_percent": parsed.target_qos_percent,
                "avoid_cloud": parsed.avoid_cloud,
                "emergency_protection": "emergency_protection" in (parsed.intent_types or []),
            },
        })
        return actions
