"""Cloud node metrics and simulated load."""
import random

import psutil

from backend.common.schemas import NodeMetrics


class CloudMetricsCollector:
    """Cloud metrics collector."""

    def __init__(self):
        self.simulated_cpu = 0.25
        self.simulated_memory = 0.30
        self.extra_delay_ms = 0.0
        self.load_multiplier = 1.0
        self.bandwidth_usage = 0.15
        self.active_tasks = 0
        self.processed_count = 0

    def set_delay(self, delay_ms: float) -> None:
        self.extra_delay_ms = delay_ms

    def set_load(self, load: float) -> None:
        """Set simulated load 0~1."""
        self.simulated_cpu = min(max(load, 0.05), 0.99)
        self.load_multiplier = 1.0 + load

    def get_cpu_load(self) -> float:
        try:
            real = psutil.cpu_percent(interval=0.05) / 100.0
        except Exception:
            real = 0.2
        return min(max(real * 0.2 + self.simulated_cpu * 0.8, 0.05), 0.99)

    def get_memory_load(self) -> float:
        try:
            real = psutil.virtual_memory().percent / 100.0
        except Exception:
            real = 0.3
        return min(max(real * 0.2 + self.simulated_memory * 0.8, 0.05), 0.99)

    def get_metrics(self) -> NodeMetrics:
        return NodeMetrics(
            cpu_percent=round(self.get_cpu_load() * 100, 1),
            memory_percent=round(self.get_memory_load() * 100, 1),
            simulated_load=round(self.get_cpu_load(), 3),
            network_delay_ms=self.extra_delay_ms,
            bandwidth_usage_mbps=round(
                self.bandwidth_usage * 100 * (1 + random.uniform(-0.03, 0.03)), 2
            ),
            active_tasks=self.active_tasks,
        )
