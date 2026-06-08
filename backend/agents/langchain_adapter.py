"""Optional LangChain LLM adapter — auto-fallback when no API key."""
import json
import logging
import os
import re
from typing import Any, Dict, Optional

from backend.agents.schemas import ParsedIntent

logger = logging.getLogger("agentnet.langchain")

VALID_INTENT_TYPES = {
    "latency_guarantee",
    "emergency_protection",
    "cloud_avoidance",
    "edge_overload_mitigation",
    "qos_optimization",
    "experiment_query",
    "unknown",
}
VALID_PRIORITY = {"high", "medium", "low", "all"}
VALID_SCENARIOS = {"normal", "cloud_delay", "edge_overload", "emergency"}
VALID_STRATEGIES = {
    "local_only", "cloud_only", "edge_only", "static_rule",
    "dynamic", "learned_late", "late_rl",
}


def is_llm_enabled() -> bool:
    if os.getenv("ENABLE_LLM_AGENT", "0") != "1":
        return False
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("AGENT_LLM_API_KEY"))


def get_agent_mode() -> str:
    if is_llm_enabled():
        try:
            import langchain  # noqa: F401
            return "langchain_optional"
        except ImportError:
            return "rule_based"
    return "rule_based"


def _extract_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _normalize_llm_data(data: Dict[str, Any]) -> Dict[str, Any]:
    intent_type = data.get("intent_type", "unknown")
    if intent_type not in VALID_INTENT_TYPES:
        intent_type = "unknown"

    intent_types = [
        t for t in (data.get("intent_types") or [intent_type])
        if t in VALID_INTENT_TYPES
    ] or [intent_type]

    priority = data.get("priority_focus", "all")
    if priority not in VALID_PRIORITY:
        priority = "high" if priority in ("urgent", "latency", "critical") else "all"

    scenario = data.get("target_scenario")
    if scenario not in VALID_SCENARIOS:
        scenario = None

    strategy = data.get("preferred_strategy")
    if strategy not in VALID_STRATEGIES:
        strategy = None

    target_latency = data.get("target_latency_ms")
    if target_latency is not None:
        try:
            target_latency = int(target_latency)
        except (TypeError, ValueError):
            target_latency = None

    target_qos = data.get("target_qos_percent")
    if target_qos is not None:
        try:
            target_qos = float(target_qos)
        except (TypeError, ValueError):
            target_qos = None

    task_types = data.get("target_task_types") or []
    if not isinstance(task_types, list):
        task_types = [str(task_types)]

    return {
        "intent_type": intent_type,
        "intent_types": intent_types,
        "target_task_types": task_types,
        "priority_focus": priority,
        "target_latency_ms": target_latency,
        "target_qos_percent": target_qos,
        "avoid_cloud": bool(data.get("avoid_cloud", False)),
        "avoid_edge_overload": bool(data.get("avoid_edge_overload", False)),
        "preferred_strategy": strategy,
        "target_scenario": scenario,
        "constraints": data.get("constraints") if isinstance(data.get("constraints"), dict) else {},
    }


def try_llm_parse(text: str) -> Optional[ParsedIntent]:
    if not is_llm_enabled():
        return None
    try:
        import langchain  # noqa: F401
    except ImportError:
        logger.info("LangChain not installed, using rule-based parser")
        return None

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("AGENT_LLM_API_KEY")
    if not api_key:
        return None

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        from backend.agents.prompts import INTENT_SYSTEM_PROMPT

        base_url = os.getenv("AGENT_LLM_BASE_URL") or os.getenv("OPENAI_API_BASE")
        model = os.getenv("AGENT_LLM_MODEL", "gpt-4o-mini")
        llm_kwargs = {"model": model, "temperature": 0, "api_key": api_key}
        if base_url:
            llm_kwargs["base_url"] = base_url
        llm = ChatOpenAI(**llm_kwargs)
        resp = llm.invoke([
            SystemMessage(content=INTENT_SYSTEM_PROMPT),
            HumanMessage(content=text),
        ])
        data = _normalize_llm_data(_extract_json(resp.content))
        return ParsedIntent(
            raw_text=text,
            parse_mode="langchain_optional",
            **data,
        )
    except Exception as e:
        logger.warning("LLM parse failed, fallback to rules: %s", e)
        return None
