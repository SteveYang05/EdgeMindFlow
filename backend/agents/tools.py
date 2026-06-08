"""AgentNet Tool Layer — 封装 Edge Server 能力."""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from backend.common.schemas import OffloadingStrategy, Scenario
from backend.edge_server import database as db
from backend.edge_server import models as edge_models

logger = logging.getLogger("agentnet.tools")

ALLOWED_SCENARIOS = {s.value for s in Scenario}
ALLOWED_STRATEGIES = {s.value for s in OffloadingStrategy}


def _metrics_to_dict(metrics_obj) -> Dict[str, Any]:
    if metrics_obj is None:
        return {}
    if hasattr(metrics_obj, "model_dump"):
        d = metrics_obj.model_dump()
    elif isinstance(metrics_obj, dict):
        d = metrics_obj
    else:
        return {}
    edge = d.get("edge_metrics") or {}
    if hasattr(edge, "model_dump"):
        edge = edge.model_dump()
    cloud = d.get("cloud_metrics") or {}
    if hasattr(cloud, "model_dump"):
        cloud = cloud.model_dump()
    d["edge_metrics"] = edge
    d["cloud_metrics"] = cloud
    return d


async def _apply_scenario(scenario: str) -> None:
    from backend.edge_server.main import _apply_scenario as apply

    await apply(scenario)


async def get_metrics_tool(scope: str = "recent_100") -> Dict[str, Any]:
    try:
        from backend.edge_server.main import get_metrics

        m = await get_metrics(scope=scope)
        return {"ok": True, "data": _metrics_to_dict(m)}
    except Exception as e:
        logger.exception("get_metrics_tool failed")
        return {"ok": False, "error": str(e), "data": {}}


async def set_scenario_tool(scenario: str) -> Dict[str, Any]:
    if scenario not in ALLOWED_SCENARIOS:
        return {"ok": False, "error": f"Invalid scenario: {scenario}"}
    try:
        await _apply_scenario(scenario)
        return {"ok": True, "scenario": scenario}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def set_strategy_tool(strategy: str) -> Dict[str, Any]:
    if strategy not in ALLOWED_STRATEGIES:
        return {"ok": False, "error": f"Invalid strategy: {strategy}"}
    try:
        edge_models.current_strategy = strategy
        db.insert_alert(
            task_id=f"agent_strategy_{strategy}",
            device_id="agentnet",
            message=f"AgentNet set strategy: {strategy}",
            alert_category="system",
            alert_level="info",
            alert_type="agent_policy",
        )
        return {"ok": True, "strategy": strategy}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def get_recent_tasks_tool(limit: int = 20) -> Dict[str, Any]:
    try:
        tasks = db.get_recent_tasks(limit)
        return {"ok": True, "data": tasks}
    except Exception as e:
        return {"ok": False, "error": str(e), "data": []}


async def get_alerts_tool(limit: int = 20) -> Dict[str, Any]:
    try:
        alerts = db.get_alerts(limit)
        return {"ok": True, "data": alerts}
    except Exception as e:
        return {"ok": False, "error": str(e), "data": []}


async def trigger_smoke_alert_tool() -> Dict[str, Any]:
    try:
        from backend.edge_server.main import process_task

        task_data = {
            "task_id": f"agent_smoke_{uuid.uuid4().hex[:8]}",
            "device_id": "smoke_sensor_01",
            "task_type": "smoke_alert",
            "priority": "high",
            "data_size_kb": 2.0,
            "compute_cost": 0.2,
            "deadline_ms": 200,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        result = await process_task(task_data)
        return {"ok": True, "data": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def run_quick_check_tool() -> Dict[str, Any]:
    try:
        from backend.edge_server.main import digital_twin_status_api, health

        h = await health()
        metrics = await get_metrics_tool("recent_100")
        twin = await digital_twin_status_api()
        twin_data = twin.model_dump() if hasattr(twin, "model_dump") else twin
        return {
            "ok": True,
            "health": h,
            "metrics_summary": {
                "avg_latency_ms": metrics.get("data", {}).get("avg_latency_ms"),
                "qos_satisfaction_rate": metrics.get("data", {}).get("qos_satisfaction_rate"),
                "current_scenario": metrics.get("data", {}).get("current_scenario"),
                "current_strategy": metrics.get("data", {}).get("current_strategy"),
            },
            "digital_twin": twin_data,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def validate_intent_tool(
    parsed_intent: Optional[Dict[str, Any]] = None,
    metrics_before: Optional[Dict[str, Any]] = None,
    metrics_after: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> Dict[str, Any]:
    from backend.agents.validator_agent import ValidatorAgent

    v = ValidatorAgent()
    result = v.validate(
        parsed_intent=parsed_intent or {},
        metrics_before=metrics_before or {},
        metrics_after=metrics_after or {},
        extra=kwargs,
    )
    return {"ok": True, "validation": result.model_dump()}


async def execute_tool(name: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    args = args or {}
    if name == "get_metrics":
        return await get_metrics_tool(args.get("scope", "recent_100"))
    if name == "set_scenario":
        return await set_scenario_tool(args["scenario"])
    if name == "set_strategy":
        return await set_strategy_tool(args["strategy"])
    if name == "get_recent_tasks":
        return await get_recent_tasks_tool(args.get("limit", 20))
    if name == "get_alerts":
        return await get_alerts_tool(args.get("limit", 20))
    if name == "trigger_smoke_alert":
        return await trigger_smoke_alert_tool()
    if name == "run_quick_check":
        return await run_quick_check_tool()
    if name == "validate_intent":
        return validate_intent_tool(
            parsed_intent=context.get("parsed_intent"),
            metrics_before=context.get("metrics_before"),
            metrics_after=context.get("metrics_after"),
            **args,
        )
    return {"ok": False, "error": f"Unknown tool: {name}"}


TOOL_SCHEMAS = [
    {
        "name": "get_metrics",
        "description": "获取系统指标",
        "parameters": {"scope": {"type": "string", "default": "recent_100"}},
    },
    {
        "name": "set_scenario",
        "description": "切换实验场景",
        "parameters": {"scenario": {"type": "string", "enum": list(ALLOWED_SCENARIOS)}},
    },
    {
        "name": "set_strategy",
        "description": "切换卸载策略",
        "parameters": {"strategy": {"type": "string", "enum": list(ALLOWED_STRATEGIES)}},
    },
    {"name": "get_recent_tasks", "description": "获取最近任务", "parameters": {"limit": {"type": "integer"}}},
    {"name": "get_alerts", "description": "获取告警", "parameters": {"limit": {"type": "integer"}}},
    {"name": "trigger_smoke_alert", "description": "触发烟雾告警任务", "parameters": {}},
    {"name": "run_quick_check", "description": "健康与孪生快速检查", "parameters": {}},
    {"name": "validate_intent", "description": "验证意图是否达成", "parameters": {}},
]
