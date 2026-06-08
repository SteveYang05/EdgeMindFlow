"""AgentNet Pydantic data models."""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


IntentType = Literal[
    "latency_guarantee",
    "emergency_protection",
    "cloud_avoidance",
    "edge_overload_mitigation",
    "qos_optimization",
    "experiment_query",
    "unknown",
]

FinalStatus = Literal["satisfied", "recovered", "failed", "dry_run", "partial"]
PriorityFocus = Literal["high", "medium", "low", "all"]


class NetworkIntentRequest(BaseModel):
    intent_text: str
    dry_run: bool = False
    auto_recover: bool = True


class ParsedIntent(BaseModel):
    raw_text: str
    intent_type: IntentType = "unknown"
    intent_types: List[str] = Field(default_factory=list)
    target_task_types: List[str] = Field(default_factory=list)
    priority_focus: PriorityFocus = "all"
    target_latency_ms: Optional[int] = None
    target_qos_percent: Optional[float] = None
    avoid_cloud: bool = False
    avoid_edge_overload: bool = False
    preferred_strategy: Optional[str] = None
    target_scenario: Optional[str] = None
    constraints: Dict[str, Any] = Field(default_factory=dict)
    parse_mode: str = "rule_based"
    clarification: Optional[str] = None


class AgentPlan(BaseModel):
    plan_id: str
    parsed_intent: ParsedIntent
    recommended_scenario: Optional[str] = None
    recommended_strategy: Optional[str] = None
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    expected_metrics: Dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class ValidationResult(BaseModel):
    satisfied: bool
    checks: List[Dict[str, Any]] = Field(default_factory=list)
    summary: str = ""
    status: str = "ok"


class AgentExecutionResult(BaseModel):
    plan_id: str
    parsed_intent: ParsedIntent
    plan: AgentPlan
    executed_actions: List[Dict[str, Any]] = Field(default_factory=list)
    metrics_before: Dict[str, Any] = Field(default_factory=dict)
    metrics_after: Dict[str, Any] = Field(default_factory=dict)
    validation_result: Optional[ValidationResult] = None
    recovery_actions: List[Dict[str, Any]] = Field(default_factory=list)
    final_status: FinalStatus = "failed"
    explanation: str = ""
    workflow_trace: List[Dict[str, Any]] = Field(default_factory=list)


class AgentStatusResponse(BaseModel):
    agent_layer_enabled: bool = True
    mode: str = "rule_based"
    llm_enabled: bool = False
    available_agents: List[str] = Field(default_factory=list)
    available_tools: List[str] = Field(default_factory=list)


class AgentExamplesResponse(BaseModel):
    examples: List[str] = Field(default_factory=list)


class AgentPlanResponse(BaseModel):
    plan: AgentPlan
    parsed_intent: ParsedIntent
    workflow_trace: List[Dict[str, Any]] = Field(default_factory=list)
