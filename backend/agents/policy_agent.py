"""PolicyAgent — strategy/scenario execution and decision logging."""
from typing import Any, Dict, List

from backend.agents.schemas import AgentPlan


class PolicyAgent:
    def summarize(self, plan: AgentPlan) -> Dict[str, Any]:
        return {
            "recommended_scenario": plan.recommended_scenario,
            "recommended_strategy": plan.recommended_strategy,
            "rationale": plan.rationale,
            "action_count": len(plan.actions),
        }

    def filter_executable_actions(self, plan: AgentPlan, dry_run: bool) -> List[Dict[str, Any]]:
        if dry_run:
            return []
        blocked = {"set_scenario", "set_strategy", "trigger_smoke_alert"}
        return [a for a in plan.actions if a.get("tool") not in blocked or not dry_run]
