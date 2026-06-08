"""AgentNet FastAPI routes."""
from fastapi import APIRouter

from backend.agents.langchain_adapter import get_agent_mode, is_llm_enabled
from backend.agents.orchestrator import AgentOrchestrator
from backend.agents.schemas import (
    AgentExamplesResponse,
    AgentPlanResponse,
    AgentStatusResponse,
    NetworkIntentRequest,
)
from backend.agents.tools import TOOL_SCHEMAS

router = APIRouter(tags=["AgentNet"])
_orchestrator = AgentOrchestrator()

EXAMPLE_INTENTS = [
    "When the cloud link degrades, prioritize smoke alert tasks to complete within 100ms",
    "When the edge node is overloaded, offload normal tasks to the cloud but keep smoke alerts on the edge",
    "Enter emergency mode and prioritize access control and smoke alerts",
    "Does the current system meet low-latency and high QoS requirements?",
    "Automatically select the best offloading strategy for the current network state",
]


@router.get("/status", response_model=AgentStatusResponse)
async def agent_status():
    return AgentStatusResponse(
        agent_layer_enabled=True,
        mode=get_agent_mode(),
        llm_enabled=is_llm_enabled(),
        available_agents=[
            "IntentAgent",
            "PlannerAgent",
            "PolicyAgent",
            "MonitorAgent",
            "ValidatorAgent",
            "RecoveryAgent",
        ],
        available_tools=[t["name"] for t in TOOL_SCHEMAS],
    )


@router.get("/examples", response_model=AgentExamplesResponse)
async def agent_examples():
    return AgentExamplesResponse(examples=EXAMPLE_INTENTS)


@router.get("/tools/schema")
async def agent_tools_schema():
    return {"tools": TOOL_SCHEMAS, "protocol": "MCP-style JSON tool schema"}


@router.post("/plan", response_model=AgentPlanResponse)
async def agent_plan(body: NetworkIntentRequest):
    out = await _orchestrator.plan_only(body.intent_text)
    return AgentPlanResponse(
        plan=out["plan"],
        parsed_intent=out["parsed_intent"],
        workflow_trace=out["workflow_trace"],
    )


@router.post("/intent")
async def agent_intent(body: NetworkIntentRequest):
    result = await _orchestrator.process_intent(body)
    return result.model_dump()
