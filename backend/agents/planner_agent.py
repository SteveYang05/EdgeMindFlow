"""PlannerAgent — generate AgentPlan from ParsedIntent."""
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
            return None, None, "Intent unclear; recommend dry_run or more detail — no risky changes will be applied."

        if parsed.intent_type == "experiment_query":
            return parsed.target_scenario or "normal", "dynamic", "Query current system state and metrics without forcing a scenario switch."

        scenario = parsed.target_scenario
        strategy = parsed.preferred_strategy or "dynamic"

        types = set(parsed.intent_types or [parsed.intent_type])

        if "cloud_avoidance" in types or scenario == "cloud_delay":
            scenario = scenario or "cloud_delay"
            strategy = parsed.preferred_strategy or "learned_late"
            rationale = "Under cloud link degradation, prefer LATE-Learn/LATE-Offload to avoid high cloud latency."
        elif "emergency_protection" in types or scenario == "emergency":
            scenario = "emergency"
            strategy = parsed.preferred_strategy or "dynamic"
            rationale = "In emergency mode, Safety Edge Reservation keeps smoke/access tasks low-latency."
        elif "edge_overload_mitigation" in types or scenario == "edge_overload":
            scenario = "edge_overload"
            strategy = "dynamic"
            rationale = "When edge is overloaded, offload non-critical tasks; safety-critical tasks stay edge-first."
        elif "qos_optimization" in types:
            scenario = scenario or "normal"
            strategy = parsed.preferred_strategy or "learned_late"
            rationale = "For QoS optimization, prefer LATE-Learn oracle mapping."
        elif "latency_guarantee" in types:
            scenario = scenario or "cloud_delay"
            strategy = parsed.preferred_strategy or "dynamic"
            rationale = "Latency guarantee intent — scenario-adaptive offloading."
        else:
            scenario = scenario or "normal"
            strategy = strategy or "dynamic"
            rationale = "Default to LATE-Offload as the primary strategy."

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
            if "smoke_alert" in parsed.target_task_types or "烟雾" in parsed.raw_text or "smoke" in parsed.raw_text.lower():
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
