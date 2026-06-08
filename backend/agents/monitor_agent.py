"""MonitorAgent — 遥测采集与自然语言摘要."""
from typing import Any, Dict, List

from backend.agents import tools


class MonitorAgent:
    async def snapshot(self, scope: str = "recent_100") -> Dict[str, Any]:
        result = await tools.get_metrics_tool(scope=scope)
        return result.get("data") or {}

    async def get_before(self) -> Dict[str, Any]:
        return await self.snapshot("recent_100")

    async def get_after(self) -> Dict[str, Any]:
        return await self.snapshot("recent_100")

    async def get_recent_tasks(self, limit: int = 20) -> List[Dict[str, Any]]:
        r = await tools.get_recent_tasks_tool(limit=limit)
        return r.get("data") or []

    async def get_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        r = await tools.get_alerts_tool(limit=limit)
        return r.get("data") or []

    def summarize(self, metrics: Dict[str, Any]) -> str:
        if not metrics:
            return "暂无指标数据（可能尚未产生任务）。"
        return (
            f"场景={metrics.get('current_scenario')}，策略={metrics.get('current_strategy')}，"
            f"均延={metrics.get('avg_latency_ms', 0):.1f}ms，"
            f"P95={metrics.get('p95_latency_ms', 0):.1f}ms，"
            f"紧急均延={metrics.get('emergency_avg_latency_ms', 0):.1f}ms，"
            f"QoS={metrics.get('qos_satisfaction_rate', 0):.1f}%，"
            f"cloud/edge/local={metrics.get('cloud_task_count', 0)}/"
            f"{metrics.get('edge_task_count', 0)}/{metrics.get('local_task_count', 0)}"
        )
