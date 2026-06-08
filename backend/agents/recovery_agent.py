"""RecoveryAgent — self-healing strategy when validation fails."""
from typing import Any, Dict, List

from backend.agents.schemas import AgentPlan, ParsedIntent, ValidationResult


class RecoveryAgent:
    def recover(
        self,
        plan: AgentPlan,
        parsed: ParsedIntent,
        validation: ValidationResult,
    ) -> List[Dict[str, Any]]:
        if validation.satisfied:
            return []

        actions: List[Dict[str, Any]] = []
        scenario = plan.recommended_scenario
        strategy = plan.recommended_strategy

        if scenario == "cloud_delay" or parsed.avoid_cloud:
            actions.append({"tool": "set_scenario", "args": {"scenario": "cloud_delay"}})
            actions.append({"tool": "set_strategy", "args": {"strategy": "dynamic"}})

        if scenario == "edge_overload" or parsed.avoid_edge_overload:
            actions.append({"tool": "set_scenario", "args": {"scenario": "edge_overload"}})
            actions.append({"tool": "set_strategy", "args": {"strategy": "dynamic"}})

        if strategy == "learned_late" and scenario == "edge_overload":
            actions.append({"tool": "set_strategy", "args": {"strategy": "dynamic"}})

        if scenario == "emergency" or "emergency_protection" in (parsed.intent_types or []):
            actions.append({"tool": "set_scenario", "args": {"scenario": "emergency"}})
            actions.append({"tool": "set_strategy", "args": {"strategy": "dynamic"}})

        if not actions:
            actions.append({"tool": "set_strategy", "args": {"strategy": "dynamic"}})

        dedup = []
        seen = set()
        for a in actions:
            key = (a["tool"], str(a.get("args")))
            if key not in seen:
                seen.add(key)
                dedup.append(a)
        return dedup
