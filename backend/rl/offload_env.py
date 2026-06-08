"""OffloadEnv — lightweight RL environment reusing existing latency/cost models."""
import random
from typing import Any, Dict, List, Optional, Tuple

from backend.common.schemas import Scenario
from backend.datasets.manager import DatasetManager
from backend.edge_server.offloading import (
    NodeState,
    TaskContext,
    build_task_profile,
    estimate_location_latencies,
)
from backend.rl.reward import compute_reward
from backend.rl.state_encoder import StateEncoder

SCENARIO_LIST = ["normal", "cloud_delay", "edge_overload", "emergency"]

_SYNTHETIC_TASKS = [
    {"task_type": "temperature_report", "priority": "low", "data_size_kb": 2, "compute_cost": 0.1, "deadline_ms": 5000},
    {"task_type": "humidity_report", "priority": "low", "data_size_kb": 2, "compute_cost": 0.1, "deadline_ms": 5000},
    {"task_type": "smoke_alert", "priority": "high", "data_size_kb": 5, "compute_cost": 0.4, "deadline_ms": 300},
    {"task_type": "image_detection", "priority": "high", "data_size_kb": 512, "compute_cost": 0.8, "deadline_ms": 500},
    {"task_type": "access_control", "priority": "medium", "data_size_kb": 8, "compute_cost": 0.3, "deadline_ms": 800},
    {"task_type": "periodic_stats", "priority": "low", "data_size_kb": 20, "compute_cost": 0.5, "deadline_ms": 3000},
]


class OffloadEnv:
    """Custom offloading RL environment."""

    def __init__(self, seed: int = 42, trace_limit: int = 500, reward_profile: str = "default"):
        self.rng = random.Random(seed)
        self.encoder = StateEncoder()
        self.reward_profile = reward_profile if reward_profile in ("default", "safety_boost", "deadline_boost", "balanced") else "default"
        self.lock_scenario = False
        self.fixed_scenario: Optional[str] = None
        self.trace_rows: List[Dict[str, Any]] = []
        self._load_trace(trace_limit)
        self.scenario = "normal"
        self.edge_cpu = 0.3
        self.cloud_cpu = 0.3
        self.edge_queue_depth = 0
        self.cloud_queue_depth = 0
        self.cloud_delay_ms = 50.0
        self.bandwidth_mbps = 100.0
        self.recent_latencies: List[float] = []
        self.recent_violations: List[int] = []
        self.current_task: Optional[TaskContext] = None
        self.step_count = 0

    def _load_trace(self, limit: int) -> None:
        try:
            dm = DatasetManager()
            dm.ensure_default_datasets()
            rows = dm.read_mec_tasks(limit=limit)
            self.trace_rows = rows if rows else _SYNTHETIC_TASKS.copy()
        except Exception:
            self.trace_rows = _SYNTHETIC_TASKS.copy()

    def _row_to_task(self, row: Dict[str, Any]) -> TaskContext:
        return TaskContext(
            task_id=str(row.get("task_id", f"rl_{self.step_count}")),
            task_type=str(row.get("task_type", "temperature_report")),
            priority=str(row.get("priority", "medium")),
            data_size_kb=float(row.get("data_size_kb", 10)),
            compute_cost=float(row.get("compute_cost", 0.3)),
            deadline_ms=float(row.get("deadline_ms", 1000)),
        )

    def sample_task(self) -> TaskContext:
        row = self.rng.choice(self.trace_rows)
        self.current_task = self._row_to_task(row)
        return self.current_task

    def _apply_scenario(self, scenario: str) -> None:
        self.scenario = scenario
        if scenario == Scenario.CLOUD_DELAY.value:
            self.cloud_delay_ms = 350.0
            self.bandwidth_mbps = 70.0
        elif scenario == Scenario.EDGE_OVERLOAD.value:
            self.edge_cpu = 0.92
            self.edge_queue_depth = max(self.edge_queue_depth, 6)
        elif scenario == Scenario.EMERGENCY.value:
            self.edge_cpu = 0.5
            self.cloud_delay_ms = 40.0
        else:
            self.cloud_delay_ms = 50.0
            self.bandwidth_mbps = 100.0
            if scenario == Scenario.NORMAL.value:
                self.edge_cpu = 0.3

    def reset(self, scenario: Optional[str] = None) -> Any:
        self.step_count = 0
        self.edge_queue_depth = 0
        self.cloud_queue_depth = 0
        self.recent_latencies = []
        self.recent_violations = []
        self.edge_cpu = 0.3
        self.cloud_cpu = 0.3
        sc = scenario or self.fixed_scenario
        if sc:
            self.lock_scenario = True
            self.fixed_scenario = sc
            self._apply_scenario(sc)
        else:
            self.lock_scenario = False
            self._apply_scenario(self.rng.choice(SCENARIO_LIST))
        self.current_task = self.sample_task()
        return self.get_state()

    def get_state(self) -> Any:
        task = self.current_task or self.sample_task()
        viol_rate = (
            sum(self.recent_violations) / len(self.recent_violations)
            if self.recent_violations else 0.0
        )
        avg_lat = (
            sum(self.recent_latencies) / len(self.recent_latencies)
            if self.recent_latencies else 100.0
        )
        return self.encoder.encode(
            task,
            scenario=self.scenario,
            edge_cpu=self.edge_cpu,
            edge_queue_depth=self.edge_queue_depth,
            cloud_cpu=self.cloud_cpu,
            cloud_queue_depth=self.cloud_queue_depth,
            cloud_delay_ms=self.cloud_delay_ms,
            bandwidth_mbps=self.bandwidth_mbps,
            recent_avg_latency=avg_lat,
            recent_deadline_violation_rate=viol_rate,
        )

    def _simulate_latency(self, action: int) -> Tuple[float, bool]:
        task = self.current_task
        assert task is not None
        location = ["local", "edge", "cloud"][action]
        edge_state = NodeState(
            cpu_load=self.edge_cpu,
            network_delay_ms=50.0,
            bandwidth_mbps=self.bandwidth_mbps,
            bandwidth_usage=0.2,
            queue_depth=self.edge_queue_depth,
        )
        cloud_state = NodeState(
            cpu_load=self.cloud_cpu,
            network_delay_ms=self.cloud_delay_ms,
            bandwidth_mbps=self.bandwidth_mbps,
            bandwidth_usage=0.3,
            queue_depth=self.cloud_queue_depth,
        )
        extra = 300.0 if self.scenario == Scenario.CLOUD_DELAY.value else 0.0
        local_lat, edge_lat, cloud_lat = estimate_location_latencies(
            task, edge_state, cloud_state, extra
        )
        lat_map = {"local": local_lat, "edge": edge_lat, "cloud": cloud_lat}
        lat = lat_map[location]
        return lat, lat <= task.deadline_ms

    def step(self, action: int) -> Tuple[Any, float, bool, Dict[str, Any]]:
        task = self.current_task
        assert task is not None
        profile = build_task_profile(task)
        latency_ms, deadline_met = self._simulate_latency(action)
        edge_overloaded = self.edge_cpu > 0.85 or self.scenario == Scenario.EDGE_OVERLOAD.value

        reward, reward_parts = compute_reward(
            action, profile, latency_ms, deadline_met,
            self.scenario, self.edge_cpu, edge_overloaded,
            task.data_size_kb, self.bandwidth_mbps,
            reward_profile=self.reward_profile,
        )

        # Update queue and load
        if action == 1:
            self.edge_queue_depth = max(0, self.edge_queue_depth + 1 - (1 if deadline_met else 0))
            self.edge_cpu = min(0.99, self.edge_cpu + 0.02)
        elif action == 2:
            self.cloud_queue_depth = max(0, self.cloud_queue_depth + 1 - (1 if deadline_met else 0))
            self.cloud_cpu = min(0.99, self.cloud_cpu + 0.015)
        else:
            self.edge_cpu = max(0.1, self.edge_cpu - 0.005)

        self.recent_latencies.append(latency_ms)
        if len(self.recent_latencies) > 50:
            self.recent_latencies.pop(0)
        self.recent_violations.append(0 if deadline_met else 1)
        if len(self.recent_violations) > 50:
            self.recent_violations.pop(0)

        self.step_count += 1
        done = False
        if not self.lock_scenario and self.step_count % 50 == 0:
            self._apply_scenario(self.rng.choice(SCENARIO_LIST))
        self.current_task = self.sample_task()
        next_state = self.get_state()

        info = {
            "latency_ms": latency_ms,
            "deadline_met": deadline_met,
            "action": action,
            "scenario": self.scenario,
            "reward_parts": reward_parts,
        }
        return next_state, reward, done, info
