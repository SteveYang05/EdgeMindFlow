"""Parse user natural-language intent; rule-based by default, optional LLM."""
import os
import re
from typing import List

from backend.agents.schemas import ParsedIntent


class IntentAgent:
    def parse(self, intent_text: str) -> ParsedIntent:
        text = (intent_text or "").strip()
        if not text:
            return ParsedIntent(
                raw_text=text,
                intent_type="unknown",
                clarification="Please provide a network intent description.",
            )

        if os.getenv("ENABLE_LLM_AGENT", "0") == "1":
            from backend.agents.langchain_adapter import try_llm_parse

            llm_result = try_llm_parse(text)
            if llm_result is not None:
                return llm_result

        return self._rule_parse(text)

    def _rule_parse(self, text: str) -> ParsedIntent:
        lower = text.lower()
        intent_types: List[str] = []
        target_task_types: List[str] = []
        priority_focus = "all"
        target_latency_ms = None
        target_qos_percent = None
        avoid_cloud = False
        avoid_edge_overload = False
        preferred_strategy = None
        target_scenario = None
        constraints = {}

        if any(k in text for k in ("烟雾", "smoke", "告警", "alert")):
            target_task_types.append("smoke_alert")
        if any(k in text for k in ("门禁", "access")):
            target_task_types.append("access_control")
        if any(k in text for k in ("温湿度", "温度", "湿度", "temperature", "humidity")):
            target_task_types.extend(["temperature_report", "humidity_report"])

        m = re.search(r"(\d+)\s*ms", text, re.I)
        if m:
            target_latency_ms = int(m.group(1))

        m2 = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
        if m2 and any(k in text for k in ("QoS", "qos", "满意度", "satisfaction")):
            target_qos_percent = float(m2.group(1))

        if any(k in text for k in ("高优先级", "high priority", "紧急", "urgent", "告警", "alert", "门禁和烟雾", "access and smoke")):
            priority_focus = "high"

        if any(k in text for k in ("云端", "云链路", "cloud", "上云")) and any(
            k in text for k in ("差", "延迟", "劣化", "变差", "degraded", "delay", "worse", "avoid", "避免", "不要")
        ):
            intent_types.append("cloud_avoidance")
            avoid_cloud = True
            target_scenario = "cloud_delay"

        if any(k in text for k in ("边缘过载", "边缘节点过载", "edge overload", "边缘负载", "edge overloaded")):
            intent_types.append("edge_overload_mitigation")
            avoid_edge_overload = True
            target_scenario = "edge_overload"

        if any(k in text for k in ("紧急模式", "紧急", "emergency", "突发事件", "emergency mode", "incident")):
            intent_types.append("emergency_protection")
            target_scenario = "emergency"
            priority_focus = "high"

        if any(k in text for k in ("低时延", "low latency", "100ms", "时延", "latency")) and target_latency_ms:
            intent_types.append("latency_guarantee")

        if any(k in text for k in ("QoS", "qos", "满意度", "服务质量", "satisfaction", "service quality")):
            intent_types.append("qos_optimization")
            if target_qos_percent is None:
                target_qos_percent = 95.0

        if any(k in text for k in ("实验", "对比", "28组", "报告", "是否满足", "experiment", "compare", "report", "satisfied")):
            intent_types.append("experiment_query")

        if "learned" in lower or "学习策略" in text or "learned strategy" in lower or "LATE-Learn" in text:
            preferred_strategy = "learned_late"
        elif "LATE-Offload" in text or "动态" in text or "dynamic" in lower:
            preferred_strategy = "dynamic"
        elif "RL" in text or "强化学习" in text or "reinforcement learning" in lower:
            preferred_strategy = "late_rl"

        if not intent_types:
            if target_latency_ms or avoid_cloud:
                intent_types.append("latency_guarantee")
            else:
                intent_types.append("unknown")

        primary = intent_types[0] if intent_types else "unknown"

        if any(k in text for k in ("普通任务", "non-critical", "normal tasks")) and any(
            k in text for k in ("云端", "cloud")
        ) and any(k in text for k in ("烟雾", "smoke")):
            constraints["non_critical_to_cloud"] = True
            constraints["safety_critical_edge"] = True

        return ParsedIntent(
            raw_text=text,
            intent_type=primary,
            intent_types=intent_types,
            target_task_types=list(dict.fromkeys(target_task_types)),
            priority_focus=priority_focus,
            target_latency_ms=target_latency_ms,
            target_qos_percent=target_qos_percent,
            avoid_cloud=avoid_cloud,
            avoid_edge_overload=avoid_edge_overload,
            preferred_strategy=preferred_strategy,
            target_scenario=target_scenario,
            constraints=constraints,
            parse_mode="rule_based",
        )
