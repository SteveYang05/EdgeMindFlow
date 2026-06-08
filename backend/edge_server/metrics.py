"""边缘节点指标采集与模拟。"""
import random
import time
from typing import Dict

import psutil

from backend.common.schemas import NodeMetrics, Scenario


class EdgeMetricsCollector:
    """边缘节点指标采集器，结合真实 psutil 与场景模拟。"""

    def __init__(self):
        self.scenario = Scenario.NORMAL.value
        self.simulated_cpu = 0.3
        self.simulated_memory = 0.35
        self.network_delay_ms = 50.0
        self.bandwidth_usage = 0.1
        self.active_tasks = 0
        self.queue_depth = 0
        self.extra_cloud_delay_ms = 0.0
        self.edge_load_multiplier = 1.0
        self._strategy_stats: Dict[str, Dict] = {
            "local_only": {"latencies": [], "count": 0},
            "cloud_only": {"latencies": [], "count": 0},
            "edge_only": {"latencies": [], "count": 0},
            "static_rule": {"latencies": [], "count": 0},
            "dynamic": {"latencies": [], "count": 0},
            "learned_late": {"latencies": [], "count": 0},
            "late_rl": {"latencies": [], "count": 0},
        }

    def set_scenario(self, scenario: str) -> None:
        """切换实验场景。"""
        self.scenario = scenario
        if scenario == Scenario.NORMAL.value:
            self.simulated_cpu = 0.3
            self.simulated_memory = 0.35
            self.network_delay_ms = 50.0
            self.extra_cloud_delay_ms = 0.0
            self.edge_load_multiplier = 1.0
            self.bandwidth_usage = 0.1
        elif scenario == Scenario.CLOUD_DELAY.value:
            self.network_delay_ms = 50.0
            self.extra_cloud_delay_ms = 300.0
            self.bandwidth_usage = 0.3
        elif scenario == Scenario.EDGE_OVERLOAD.value:
            self.simulated_cpu = 0.92
            self.simulated_memory = 0.88
            self.edge_load_multiplier = 2.5
            self.queue_depth = 8
        elif scenario == Scenario.EMERGENCY.value:
            self.simulated_cpu = 0.5
            self.network_delay_ms = 40.0

    def get_cpu_load(self) -> float:
        """获取 CPU 负载 (0~1)，结合真实值与模拟值。"""
        try:
            real = psutil.cpu_percent(interval=0.1) / 100.0
        except Exception:
            real = 0.3
        simulated = min(self.simulated_cpu * self.edge_load_multiplier, 0.99)
        return min(max(real * 0.3 + simulated * 0.7, 0.05), 0.99)

    def get_memory_load(self) -> float:
        """获取内存负载。"""
        try:
            real = psutil.virtual_memory().percent / 100.0
        except Exception:
            real = 0.35
        return min(max(real * 0.3 + self.simulated_memory * 0.7, 0.05), 0.99)

    def increment_active_tasks(self) -> None:
        self.active_tasks += 1
        self.queue_depth += 1

    def decrement_active_tasks(self) -> None:
        self.active_tasks = max(0, self.active_tasks - 1)
        self.queue_depth = max(0, self.queue_depth - 1)

    def record_strategy_latency(self, strategy: str, latency_ms: float) -> None:
        """记录策略下的时延用于对比。"""
        if strategy in self._strategy_stats:
            stats = self._strategy_stats[strategy]
            stats["latencies"].append(latency_ms)
            stats["count"] += 1
            if len(stats["latencies"]) > 200:
                stats["latencies"] = stats["latencies"][-200:]

    def get_strategy_comparison(self) -> Dict:
        """获取七种策略的对比数据。"""
        result = {}
        for name, stats in self._strategy_stats.items():
            lats = stats["latencies"]
            if lats:
                result[name] = {
                    "avg_latency_ms": round(sum(lats) / len(lats), 2),
                    "count": stats["count"],
                    "p95_latency_ms": round(
                        sorted(lats)[int(len(lats) * 0.95)] if len(lats) > 1 else lats[0],
                        2,
                    ),
                }
            else:
                result[name] = {"avg_latency_ms": 0, "count": 0, "p95_latency_ms": 0}
        return result

    def get_node_metrics(self) -> NodeMetrics:
        """返回当前节点指标。"""
        cpu = self.get_cpu_load()
        mem = self.get_memory_load()
        status = "healthy"
        if self.scenario == Scenario.CLOUD_DELAY.value:
            status = "cloud_link_degraded"
        elif self.scenario == Scenario.EDGE_OVERLOAD.value:
            status = "edge_overloaded"
        elif self.scenario == Scenario.EMERGENCY.value:
            status = "emergency_active"

        return NodeMetrics(
            cpu_percent=round(cpu * 100, 1),
            memory_percent=round(mem * 100, 1),
            simulated_load=round(cpu, 3),
            network_delay_ms=self.network_delay_ms + self.extra_cloud_delay_ms,
            bandwidth_usage_mbps=round(
                self.bandwidth_usage * 100 * (1 + random.uniform(-0.05, 0.05)), 2
            ),
            active_tasks=self.active_tasks,
        )

    def is_edge_overloaded(self) -> bool:
        return self.get_cpu_load() > 0.85 or self.scenario == Scenario.EDGE_OVERLOAD.value

    def reset_strategy_stats(self) -> None:
        """重置内存中的策略对比统计。"""
        self._strategy_stats = {
            "local_only": {"latencies": [], "count": 0},
            "cloud_only": {"latencies": [], "count": 0},
            "edge_only": {"latencies": [], "count": 0},
            "static_rule": {"latencies": [], "count": 0},
            "dynamic": {"latencies": [], "count": 0},
            "learned_late": {"latencies": [], "count": 0},
            "late_rl": {"latencies": [], "count": 0},
        }
