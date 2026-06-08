"""Pydantic 数据模型 - 任务、决策、指标等。"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    TEMPERATURE = "temperature_report"
    HUMIDITY = "humidity_report"
    SMOKE_ALERT = "smoke_alert"
    IMAGE_DETECTION = "image_detection"
    ACCESS_CONTROL = "access_control"
    PERIODIC_STATS = "periodic_stats"


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ExecutionLocation(str, Enum):
    LOCAL = "local"
    EDGE = "edge"
    CLOUD = "cloud"


class OffloadingStrategy(str, Enum):
    LOCAL_ONLY = "local_only"
    CLOUD_ONLY = "cloud_only"
    EDGE_ONLY = "edge_only"
    STATIC_RULE = "static_rule"
    DYNAMIC = "dynamic"
    LEARNED_LATE = "learned_late"
    LATE_RL = "late_rl"


class Scenario(str, Enum):
    NORMAL = "normal"
    CLOUD_DELAY = "cloud_delay"
    EDGE_OVERLOAD = "edge_overload"
    EMERGENCY = "emergency"


class TaskSubmit(BaseModel):
    """IoT 设备提交的任务。"""
    task_id: str
    device_id: str
    task_type: str
    priority: str = "medium"
    data_size_kb: float = 10.0
    compute_cost: float = 0.3
    deadline_ms: float = 1000.0
    timestamp: str = ""
    topic: str = ""


class OffloadingDecision(BaseModel):
    """卸载决策结果。"""
    task_id: str
    decision: str
    reason: str
    edge_score: float = 0.0
    cloud_score: float = 0.0
    local_score: float = 0.0
    estimated_edge_latency_ms: float = 0.0
    estimated_cloud_latency_ms: float = 0.0
    estimated_local_latency_ms: float = 0.0


class TaskResult(BaseModel):
    """任务执行结果。"""
    task_id: str
    device_id: str
    task_type: str
    priority: str
    decision: str
    reason: str
    execution_location: str
    total_latency_ms: float
    upload_latency_ms: float = 0.0
    queue_latency_ms: float = 0.0
    compute_latency_ms: float = 0.0
    return_latency_ms: float = 0.0
    deadline_ms: float = 0.0
    deadline_met: bool = True
    success: bool = True
    edge_score: float = 0.0
    cloud_score: float = 0.0
    local_score: float = 0.0
    timestamp: str = ""
    scenario: str = "normal"
    strategy: str = "dynamic"


class NodeMetrics(BaseModel):
    """节点负载指标。"""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    simulated_load: float = 0.0
    network_delay_ms: float = 0.0
    bandwidth_usage_mbps: float = 0.0
    active_tasks: int = 0


class SystemMetrics(BaseModel):
    """系统聚合指标。"""
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    edge_task_count: int = 0
    cloud_task_count: int = 0
    local_task_count: int = 0
    success_rate: float = 100.0
    deadline_violation_rate: float = 0.0
    emergency_avg_latency_ms: float = 0.0
    alert_count: int = 0
    total_tasks: int = 0
    task_type_distribution: Dict[str, int] = Field(default_factory=dict)
    strategy_comparison: Dict[str, Any] = Field(default_factory=dict)
    edge_metrics: NodeMetrics = Field(default_factory=NodeMetrics)
    cloud_metrics: NodeMetrics = Field(default_factory=NodeMetrics)
    current_scenario: str = "normal"
    current_strategy: str = "dynamic"
    network_status: str = "healthy"
    security_alert_count: int = 0
    performance_warning_count: int = 0
    system_event_count: int = 0
    data_scope: str = "all"
    scope_hint: str = ""
    qos_satisfaction_rate: float = 0.0


class TopologyResponse(BaseModel):
    """网络拓扑 API 响应。"""
    devices: List[Dict[str, Any]] = Field(default_factory=list)
    edge: Dict[str, Any] = Field(default_factory=dict)
    cloud: Dict[str, Any] = Field(default_factory=dict)
    recent_flow: Dict[str, int] = Field(default_factory=dict)
    latest_task: Optional[Dict[str, Any]] = None
    current_scenario: str = "normal"
    current_strategy: str = "dynamic"


class CloudExecuteRequest(BaseModel):
    """云端执行任务请求。"""
    task_id: str
    task_type: str
    compute_cost: float
    data_size_kb: float
    priority: str = "medium"


class CloudExecuteResponse(BaseModel):
    """云端执行响应。"""
    task_id: str
    success: bool
    compute_latency_ms: float
    return_latency_ms: float = 5.0


class ScenarioState(BaseModel):
    """实验场景状态。"""
    scenario: str
    description: str
    edge_load_multiplier: float = 1.0
    cloud_delay_multiplier: float = 1.0
    network_delay_ms: float = 50.0


class DatasetInfo(BaseModel):
    """Trace 数据集信息。"""
    name: str
    display_name: str
    description: str = ""
    auto_download: bool = False
    size_class: str = "small"
    status: str = "not_downloaded"
    source: Optional[str] = None
    path: Optional[str] = None
    file_exists: bool = False
    manual_only: bool = False
    message: Optional[str] = None
    doc_url: Optional[str] = None


class MLTrainResult(BaseModel):
    """LATE-Learn 训练结果。"""
    method: str = "LATE-Learn"
    status: str
    train_samples: int = 0
    test_accuracy: float = 0.0
    model_path: str = ""
    message: str = ""
