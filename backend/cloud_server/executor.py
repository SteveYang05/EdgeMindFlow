"""Cloud task execution simulator."""
import asyncio
import random

from backend.common.config import CLOUD_COMPUTE_CAPACITY
from backend.cloud_server.metrics import CloudMetricsCollector


async def execute_task(
    task_id: str,
    compute_cost: float,
    data_size_kb: float,
    metrics: CloudMetricsCollector,
) -> dict:
    """
    Simulate cloud task execution.
    Returns compute_latency_ms and return_latency_ms.
    """
    metrics.active_tasks += 1
    metrics.processed_count += 1
    load = metrics.get_cpu_load()
    # Compute latency modeling
    base_compute = (compute_cost / CLOUD_COMPUTE_CAPACITY) * 1000
    compute_ms = base_compute * (1 + load * 2) * metrics.load_multiplier
    # Extra cloud link delay
    compute_ms += metrics.extra_delay_ms * 0.3
    # Data size impact
    compute_ms += data_size_kb * 0.02
    # Simulate execution time (shortened actual wait)
    await asyncio.sleep(min(compute_ms / 1000, 0.3))
    compute_ms += random.uniform(-5, 15)
    metrics.active_tasks = max(0, metrics.active_tasks - 1)
    return {
        "task_id": task_id,
        "success": True,
        "compute_latency_ms": round(max(compute_ms, 10), 2),
        "return_latency_ms": round(5 + data_size_kb * 0.001, 2),
    }
