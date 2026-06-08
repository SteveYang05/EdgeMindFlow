"""Multi-agent orchestration: Intent → Plan → Execute → Validate in one round."""
import logging
from typing import Any, Dict, List

from backend.agents.intent_agent import IntentAgent
from backend.agents.memory import save_execution
from backend.agents.monitor_agent import MonitorAgent
from backend.agents.planner_agent import PlannerAgent
from backend.agents.policy_agent import PolicyAgent
from backend.agents.recovery_agent import RecoveryAgent
from backend.agents.schemas import AgentExecutionResult, AgentPlan, NetworkIntentRequest, ValidationResult
from backend.agents import tools
from backend.agents.validator_agent import ValidatorAgent

logger = logging.getLogger("agentnet.orchestrator")


class AgentOrchestrator:
    def __init__(self):
        self.intent_agent = IntentAgent()
        self.planner_agent = PlannerAgent()
        self.policy_agent = PolicyAgent()
        self.monitor_agent = MonitorAgent()
        self.validator_agent = ValidatorAgent()
        self.recovery_agent = RecoveryAgent()

    def _trace(self, workflow: List[Dict], agent: str, status: str, inp: Any, out: Any) -> None:
        workflow.append({
            "agent": agent,
            "status": status,
            "input_summary": str(inp)[:200],
            "output_summary": str(out)[:400],
        })

    async def plan_only(self, intent_text: str) -> Dict[str, Any]:
        workflow: List[Dict] = []
        parsed = self.intent_agent.parse(intent_text)
        self._trace(workflow, "IntentAgent", "ok", intent_text, parsed.model_dump())
        plan = self.planner_agent.plan(parsed)
        self._trace(workflow, "PlannerAgent", "ok", parsed.intent_type, plan.model_dump())
        self._trace(workflow, "PolicyAgent", "ok", plan.plan_id, self.policy_agent.summarize(plan))
        return {"plan": plan, "parsed_intent": parsed, "workflow_trace": workflow}

    async def process_intent(self, request: NetworkIntentRequest) -> AgentExecutionResult:
        workflow: List[Dict] = []
        parsed = self.intent_agent.parse(request.intent_text)
        self._trace(workflow, "IntentAgent", "ok", request.intent_text, parsed.model_dump())

        plan = self.planner_agent.plan(parsed)
        self._trace(workflow, "PlannerAgent", "ok", parsed.intent_type, {
            "scenario": plan.recommended_scenario,
            "strategy": plan.recommended_strategy,
        })
        self._trace(workflow, "PolicyAgent", "ok", plan.plan_id, self.policy_agent.summarize(plan))

        metrics_before = await self.monitor_agent.get_before()
        self._trace(workflow, "MonitorAgent", "ok", "before", self.monitor_agent.summarize(metrics_before))

        executed: List[Dict[str, Any]] = []
        recovery_actions: List[Dict[str, Any]] = []
        context: Dict[str, Any] = {
            "parsed_intent": parsed.model_dump(),
            "metrics_before": metrics_before,
        }

        if request.dry_run:
            self._trace(workflow, "Orchestrator", "dry_run", plan.actions, "skipped mutating tools")
            result = AgentExecutionResult(
                plan_id=plan.plan_id,
                parsed_intent=parsed,
                plan=plan,
                executed_actions=[],
                metrics_before=metrics_before,
                metrics_after=metrics_before,
                validation_result=None,
                final_status="dry_run",
                explanation=f"[Dry Run] {plan.rationale}",
                workflow_trace=workflow,
            )
            save_execution(result.model_dump())
            return result

        if parsed.intent_type == "unknown" and not plan.recommended_scenario:
            result = AgentExecutionResult(
                plan_id=plan.plan_id,
                parsed_intent=parsed,
                plan=plan,
                metrics_before=metrics_before,
                metrics_after=metrics_before,
                final_status="failed",
                explanation=plan.rationale or "Intent not recognized; no changes applied.",
                workflow_trace=workflow,
            )
            save_execution(result.model_dump())
            return result

        for action in plan.actions:
            tool = action.get("tool")
            if tool in ("validate_intent",):
                context["metrics_after"] = await self.monitor_agent.get_after()
                continue
            res = await tools.execute_tool(tool, action.get("args", {}), context)
            executed.append({"tool": tool, "args": action.get("args", {}), "result": res})
            self._trace(workflow, "ToolLayer", "ok" if res.get("ok") else "error", tool, res)

        context["metrics_after"] = await self.monitor_agent.get_after()
        metrics_after = context["metrics_after"]
        self._trace(workflow, "MonitorAgent", "ok", "after", self.monitor_agent.summarize(metrics_after))

        val_raw = tools.validate_intent_tool(
            parsed_intent=parsed.model_dump(),
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            target_latency_ms=parsed.target_latency_ms,
            target_qos_percent=parsed.target_qos_percent,
            avoid_cloud=parsed.avoid_cloud,
            emergency_protection="emergency_protection" in (parsed.intent_types or []),
            mode="query" if parsed.intent_type == "experiment_query" else None,
        )
        validation = ValidationResult(**val_raw["validation"])
        self._trace(workflow, "ValidatorAgent", "ok" if validation.satisfied else "warn", validation.summary, validation.model_dump())

        final_status = "satisfied" if validation.satisfied else "failed"

        if not validation.satisfied and request.auto_recover:
            recovery_actions = self.recovery_agent.recover(plan, parsed, validation)
            self._trace(workflow, "RecoveryAgent", "ok", "recover", recovery_actions)
            for action in recovery_actions:
                res = await tools.execute_tool(action["tool"], action.get("args", {}), context)
                executed.append({"tool": action["tool"], "args": action.get("args", {}), "result": res, "recovery": True})
            metrics_after = await self.monitor_agent.get_after()
            context["metrics_after"] = metrics_after
            val_raw2 = tools.validate_intent_tool(
                parsed_intent=parsed.model_dump(),
                metrics_before=metrics_before,
                metrics_after=metrics_after,
                target_latency_ms=parsed.target_latency_ms,
                target_qos_percent=parsed.target_qos_percent,
                avoid_cloud=parsed.avoid_cloud,
                emergency_protection="emergency_protection" in (parsed.intent_types or []),
            )
            validation = ValidationResult(**val_raw2["validation"])
            self._trace(workflow, "ValidatorAgent", "ok" if validation.satisfied else "warn", "post-recovery", validation.summary)
            final_status = "recovered" if validation.satisfied else "failed"

        explanation = (
            f"{plan.rationale} {self.monitor_agent.summarize(metrics_after)} "
            f"Validation: {validation.summary}"
        )

        result = AgentExecutionResult(
            plan_id=plan.plan_id,
            parsed_intent=parsed,
            plan=plan,
            executed_actions=executed,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            validation_result=validation,
            recovery_actions=recovery_actions,
            final_status=final_status,
            explanation=explanation.strip(),
            workflow_trace=workflow,
        )
        save_execution(result.model_dump())
        return result
