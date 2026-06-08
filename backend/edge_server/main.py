"""
Edge Server - edge compute task offloading and scheduling service
Port: 8000
"""
import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.common.config import (
    AUTO_DOWNLOAD_DATASETS,
    CLOUD_SERVER_URL,
    COMM_MODE,
    EDGE_PORT,
    MQTT_BROKER_HOST,
    MQTT_BROKER_PORT,
)
from backend.common.schemas import (
    DatasetInfo,
    MLTrainResult,
    OffloadingStrategy,
    Scenario,
    ScenarioState,
    SystemMetrics,
    TaskSubmit,
    TopologyResponse,
)
from backend.datasets.manager import get_dataset_manager
from backend.edge_server import database as db
from backend.edge_server.http_ingest import normalize_task
from backend.edge_server.metrics import EdgeMetricsCollector
from backend.edge_server.models import (
    REGISTERED_DEVICES,
    current_scenario,
    current_strategy,
    metrics_collector,
)
from backend.edge_server import models as edge_models
from backend.edge_server.mqtt_client import EdgeMQTTSubscriber
from backend.edge_server.offloading import (
    NodeState,
    TaskContext,
    decide_offloading,
    estimate_compute_latency_ms,
    estimate_queue_latency_ms,
    estimate_total_latency,
    estimate_upload_latency_ms,
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("edge_server")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IMAGES_DIR = PROJECT_ROOT / "data" / "images"

_mqtt_sub: EdgeMQTTSubscriber | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: dataset init + optional MQTT subscription."""
    global _mqtt_sub
    db.init_db()
    if AUTO_DOWNLOAD_DATASETS:
        try:
            dm = get_dataset_manager()
            results = dm.ensure_default_datasets()
            logger.info("Default datasets ready: %s", list(results.keys()))
        except Exception as e:
            logger.warning("Dataset auto-download failed (synthetic fallback may apply): %s", e)
    if COMM_MODE == "mqtt":
        _mqtt_sub = EdgeMQTTSubscriber(
            MQTT_BROKER_HOST, MQTT_BROKER_PORT, _mqtt_task_handler
        )
        ok = _mqtt_sub.start()
        logger.info("MQTT mode: subscriber started=%s", ok)
    else:
        logger.info("HTTP fallback mode (COMM_MODE=http)")
    yield
    if _mqtt_sub:
        _mqtt_sub.stop()


app = FastAPI(
    title="ComputerNet Edge Server",
    description="Edge compute task offloading and low-latency network optimization for smart campuses",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# init_db is called in lifespan (supports dataset directory initialization)


async def fetch_cloud_metrics() -> NodeState:
    """Fetch cloud state from Cloud Server."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{CLOUD_SERVER_URL}/api/cloud/metrics")
            data = resp.json()
            return NodeState(
                cpu_load=data.get("simulated_load", 0.3),
                memory_load=data.get("memory_percent", 30) / 100,
                network_delay_ms=data.get("network_delay_ms", 50),
                bandwidth_usage=data.get("bandwidth_usage_mbps", 10) / 100,
            )
    except Exception:
        return NodeState(cpu_load=0.3, memory_load=0.3)


async def execute_on_cloud(task: dict) -> dict:
    """Forward task to Cloud Server for execution."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{CLOUD_SERVER_URL}/api/cloud/execute",
            json={
                "task_id": task["task_id"],
                "task_type": task["task_type"],
                "compute_cost": task["compute_cost"],
                "data_size_kb": task["data_size_kb"],
                "priority": task["priority"],
            },
        )
        return resp.json()


async def process_task(task_data: dict) -> dict:
    """
    Core task processing pipeline:
    receive -> offloading decision -> execute -> record result
    """
    metrics_collector.increment_active_tasks()
    task = TaskContext(
        task_id=task_data["task_id"],
        task_type=task_data["task_type"],
        priority=task_data.get("priority", "medium"),
        data_size_kb=task_data.get("data_size_kb", 10),
        compute_cost=task_data.get("compute_cost", 0.3),
        deadline_ms=task_data.get("deadline_ms", 1000),
    )

    edge_state = NodeState(
        cpu_load=metrics_collector.get_cpu_load(),
        memory_load=metrics_collector.get_memory_load(),
        network_delay_ms=metrics_collector.network_delay_ms,
        bandwidth_usage=metrics_collector.bandwidth_usage,
        queue_depth=metrics_collector.queue_depth,
    )
    cloud_state = await fetch_cloud_metrics()
    extra_delay = metrics_collector.extra_cloud_delay_ms

    decision = decide_offloading(
        task,
        edge_state,
        cloud_state,
        strategy=edge_models.current_strategy,
        extra_cloud_delay_ms=extra_delay,
        edge_overloaded=metrics_collector.is_edge_overloaded(),
        scenario=edge_models.current_scenario,
    )

    loc = decision.decision
    upload_ms = queue_ms = compute_ms = return_ms = 0.0
    success = True

    try:
        if loc == "cloud":
            upload_ms = estimate_upload_latency_ms(
                task.data_size_kb,
                edge_state.bandwidth_mbps,
                edge_state.network_delay_ms + extra_delay,
                edge_state.bandwidth_usage,
            )
            queue_ms = estimate_queue_latency_ms(cloud_state.queue_depth, cloud_state.cpu_load)
            cloud_result = await execute_on_cloud(task_data)
            compute_ms = cloud_result.get("compute_latency_ms", 50)
            return_ms = cloud_result.get("return_latency_ms", 5)
        elif loc == "edge":
            upload_ms = estimate_upload_latency_ms(
                task.data_size_kb * 0.1,
                edge_state.bandwidth_mbps,
                edge_state.network_delay_ms * 0.1,
            )
            queue_ms = estimate_queue_latency_ms(edge_state.queue_depth, edge_state.cpu_load)
            from backend.common.config import EDGE_COMPUTE_CAPACITY
            compute_ms = estimate_compute_latency_ms(
                task.compute_cost, edge_state.cpu_load, EDGE_COMPUTE_CAPACITY
            )
            await asyncio.sleep(min(compute_ms / 2000, 0.15))
            return_ms = 5.0
        else:  # local
            from backend.common.config import LOCAL_COMPUTE_CAPACITY
            compute_ms = estimate_compute_latency_ms(
                task.compute_cost, 0.2, LOCAL_COMPUTE_CAPACITY
            )
            await asyncio.sleep(min(compute_ms / 2000, 0.1))
            return_ms = 2.0
    except Exception as e:
        logger.error("Task execution failed: %s", e)
        success = False
        compute_ms = 999

    total_ms = estimate_total_latency(upload_ms, queue_ms, compute_ms, return_ms)
    deadline_met = total_ms <= task.deadline_ms

    result = {
        "task_id": task.task_id,
        "device_id": task_data.get("device_id", "unknown"),
        "task_type": task.task_type,
        "priority": task.priority,
        "decision": loc,
        "reason": decision.reason,
        "execution_location": loc,
        "total_latency_ms": round(total_ms, 2),
        "upload_latency_ms": round(upload_ms, 2),
        "queue_latency_ms": round(queue_ms, 2),
        "compute_latency_ms": round(compute_ms, 2),
        "return_latency_ms": round(return_ms, 2),
        "deadline_ms": task.deadline_ms,
        "deadline_met": deadline_met,
        "success": success,
        "edge_score": decision.edge_score,
        "cloud_score": decision.cloud_score,
        "local_score": decision.local_score,
        "timestamp": datetime.utcnow().isoformat(),
        "scenario": edge_models.current_scenario,
        "strategy": edge_models.current_strategy,
        "data_size_kb": task_data.get("data_size_kb", 10),
    }

    db.insert_task(result)
    metrics_collector.record_strategy_latency(edge_models.current_strategy, total_ms)
    metrics_collector.decrement_active_tasks()

    # Persist alerts with category classification
    device_id = task_data.get("device_id", "unknown")
    if task.task_type == "smoke_alert":
        db.insert_alert(
            task_id=task.task_id,
            device_id=device_id,
            message=f"Security alert: smoke detected from {device_id}, latency={total_ms:.0f}ms",
            alert_category="security",
            alert_level="critical",
            alert_type="smoke_alert",
        )
        logger.warning("SECURITY ALERT: smoke_alert from %s", device_id)
    elif not success:
        db.insert_alert(
            task_id=task.task_id,
            device_id=device_id,
            message=f"Task execution failed: {task.task_type} from {device_id}",
            alert_category="performance",
            alert_level="warning",
            alert_type="task_failure",
        )
    elif not deadline_met:
        db.insert_alert(
            task_id=task.task_id,
            device_id=device_id,
            message=f"Deadline violation: {task.task_type} latency={total_ms:.0f}ms > deadline={task.deadline_ms:.0f}ms",
            alert_category="performance",
            alert_level="warning",
            alert_type="deadline_violation",
        )

    # Performance alerts: edge/cloud overload
    if metrics_collector.is_edge_overloaded() and task.priority != "high":
        if task.task_type != "smoke_alert":
            pass  # edge_overload system events are recorded only on scenario switch

    logger.info(
        "Task %s -> %s | latency=%.0fms | reason=%s",
        task.task_id, loc, total_ms, decision.reason[:60],
    )
    return result


async def _sync_cloud_scenario(scenario: str):
    """Sync cloud experiment parameters via API."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            if scenario == Scenario.CLOUD_DELAY.value:
                await client.post(f"{CLOUD_SERVER_URL}/api/cloud/set_delay", json={"delay_ms": 300})
                await client.post(f"{CLOUD_SERVER_URL}/api/cloud/set_load", json={"load": 0.3})
            elif scenario == Scenario.EDGE_OVERLOAD.value:
                await client.post(f"{CLOUD_SERVER_URL}/api/cloud/set_delay", json={"delay_ms": 0})
                await client.post(f"{CLOUD_SERVER_URL}/api/cloud/set_load", json={"load": 0.4})
            else:
                await client.post(f"{CLOUD_SERVER_URL}/api/cloud/set_delay", json={"delay_ms": 0})
                await client.post(f"{CLOUD_SERVER_URL}/api/cloud/set_load", json={"load": 0.3})
    except Exception as e:
        logger.warning("Cloud scenario sync failed: %s", e)


async def _apply_scenario(scenario: str):
    """Apply scenario and sync cloud parameters."""
    edge_models.current_scenario = scenario
    metrics_collector.set_scenario(scenario)
    await _sync_cloud_scenario(scenario)
    db.insert_alert(
        task_id=f"scenario_{scenario}",
        device_id="system",
        message=f"Scenario switched to: {scenario}",
        alert_category="system",
        alert_level="info",
        alert_type="system_event",
    )
    if scenario == Scenario.EDGE_OVERLOAD.value:
        db.insert_alert(
            task_id=f"perf_edge_{scenario}",
            device_id="system",
            message="Performance warning: edge node CPU load is high",
            alert_category="performance",
            alert_level="warning",
            alert_type="edge_overload",
        )
    if scenario == Scenario.CLOUD_DELAY.value:
        db.insert_alert(
            task_id=f"perf_cloud_{scenario}",
            device_id="system",
            message="Performance warning: cloud link delay is elevated",
            alert_category="performance",
            alert_level="warning",
            alert_type="cloud_delay",
        )


# ---- API Routes ----

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "edge_server",
        "port": EDGE_PORT,
        "comm_mode": COMM_MODE,
        "strategy": edge_models.current_strategy,
        "scenario": edge_models.current_scenario,
    }


@app.post("/api/tasks/submit")
async def submit_task(task: TaskSubmit):
    """HTTP Fallback: IoT device task submission endpoint."""
    data = normalize_task(task)
    result = await process_task(data)
    return result


@app.get("/api/tasks")
async def list_tasks(limit: int = 100):
    return db.get_all_tasks(limit)


@app.get("/api/tasks/recent")
async def recent_tasks(limit: int = 30):
    return db.get_recent_tasks(limit)


@app.get("/api/metrics")
async def get_metrics(scope: str = "all"):
    db_metrics = db.get_metrics_scoped(scope)
    scope_hint = ""

    if db_metrics.get("empty"):
        scope_hint = "No experiment data yet — run bash scripts/prepare_demo.sh first"
        db_metrics = db.get_metrics_scoped("recent_100") if scope == "latest_experiment" else db_metrics

    if scope in ("recent_100", "recent_300"):
        loc_counts = {
            "local": db_metrics.get("local_task_count", 0),
            "edge": db_metrics.get("edge_task_count", 0),
            "cloud": db_metrics.get("cloud_task_count", 0),
        }
        type_dist = db_metrics.get("task_type_distribution", {})
        strategy_comp = metrics_collector.get_strategy_comparison()
    elif scope == "latest_experiment" and not db_metrics.get("empty"):
        loc_counts = {
            "local": db_metrics.get("local_task_count", 0),
            "edge": db_metrics.get("edge_task_count", 0),
            "cloud": db_metrics.get("cloud_task_count", 0),
        }
        type_dist = db_metrics.get("task_type_distribution", {})
        strategy_comp = db_metrics.get("strategy_comparison", {})
        scope_hint = f"Experiment ID: {db_metrics.get('experiment_id', 'N/A')}"
    else:
        loc_counts = db.count_by_location()
        type_dist = db_metrics.get("task_type_distribution") or db.count_by_type()
        strategy_comp = metrics_collector.get_strategy_comparison()

    edge_m = metrics_collector.get_node_metrics()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            cloud_resp = await client.get(f"{CLOUD_SERVER_URL}/api/cloud/metrics")
            cloud_data = cloud_resp.json()
    except Exception:
        cloud_data = {"cpu_percent": 0, "memory_percent": 0, "simulated_load": 0.3}

    from backend.common.schemas import NodeMetrics
    cloud_m = NodeMetrics(
        cpu_percent=cloud_data.get("cpu_percent", 0),
        memory_percent=cloud_data.get("memory_percent", 0),
        simulated_load=cloud_data.get("simulated_load", 0.3),
        network_delay_ms=cloud_data.get("network_delay_ms", 0),
        bandwidth_usage_mbps=cloud_data.get("bandwidth_usage_mbps", 0),
        active_tasks=cloud_data.get("active_tasks", 0),
    )

    network_status = "healthy"
    if edge_models.current_scenario == Scenario.CLOUD_DELAY.value:
        network_status = "cloud_link_degraded"
    elif edge_models.current_scenario == Scenario.EDGE_OVERLOAD.value:
        network_status = "edge_overloaded"
    elif edge_models.current_scenario == Scenario.EMERGENCY.value:
        network_status = "emergency_active"

    return SystemMetrics(
        avg_latency_ms=db_metrics.get("avg_latency_ms", 0),
        p95_latency_ms=db_metrics.get("p95_latency_ms", 0),
        edge_task_count=loc_counts.get("edge", 0),
        cloud_task_count=loc_counts.get("cloud", 0),
        local_task_count=loc_counts.get("local", 0),
        success_rate=db_metrics.get("success_rate", 100),
        deadline_violation_rate=db_metrics.get("deadline_violation_rate", 0),
        emergency_avg_latency_ms=db_metrics.get("emergency_avg_latency_ms", 0),
        alert_count=db_metrics.get("alert_count", 0),
        security_alert_count=db_metrics.get("security_alert_count", 0),
        performance_warning_count=db_metrics.get("performance_warning_count", 0),
        system_event_count=db_metrics.get("system_event_count", 0),
        total_tasks=db_metrics.get("total_tasks", 0),
        task_type_distribution=type_dist,
        strategy_comparison=strategy_comp,
        edge_metrics=edge_m,
        cloud_metrics=cloud_m,
        current_scenario=edge_models.current_scenario,
        current_strategy=edge_models.current_strategy,
        network_status=network_status,
        data_scope=scope,
        scope_hint=scope_hint,
        qos_satisfaction_rate=db_metrics.get("qos_satisfaction_rate", 0),
    )


@app.get("/api/devices")
async def get_devices():
    return REGISTERED_DEVICES


@app.get("/api/alerts")
async def get_alerts(limit: int = 20, category: str = None):
    return db.get_alerts(limit, category)


@app.get("/api/topology", response_model=TopologyResponse)
async def get_topology(scope: str = "recent_100"):
    """Network topology and task flow data."""
    edge_m = metrics_collector.get_node_metrics()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            cloud_resp = await client.get(f"{CLOUD_SERVER_URL}/api/cloud/metrics")
            cloud_data = cloud_resp.json()
    except Exception:
        cloud_data = {}

    flow_limit = {"all": 500, "recent_100": 100, "recent_300": 300, "latest_experiment": 100}.get(scope, 100)
    recent = db.get_recent_tasks(1)
    latest = recent[0] if recent else None
    flow = db.get_flow_stats(flow_limit)

    return TopologyResponse(
        devices=REGISTERED_DEVICES,
        edge={
            "name": "Edge Server",
            "cpu_percent": edge_m.cpu_percent,
            "memory_percent": edge_m.memory_percent,
            "network_delay_ms": edge_m.network_delay_ms,
            "status": "online",
        },
        cloud={
            "name": "Cloud Server",
            "cpu_percent": cloud_data.get("cpu_percent", 0),
            "memory_percent": cloud_data.get("memory_percent", 0),
            "network_delay_ms": cloud_data.get("network_delay_ms", 0),
            "status": "online",
        },
        recent_flow=flow,
        latest_task={
            "task_id": latest.get("task_id"),
            "device_id": latest.get("device_id"),
            "decision": latest.get("execution_location"),
            "task_type": latest.get("task_type"),
        } if latest else None,
        current_scenario=edge_models.current_scenario,
        current_strategy=edge_models.current_strategy,
    )


@app.get("/api/experiments/summary")
async def experiments_summary(limit: int = 50):
    return db.get_experiment_results(limit)


@app.get("/api/experiments/latest")
async def experiments_latest():
    results = db.get_experiment_results(1)
    return results[0] if results else {}


@app.get("/api/export/summary")
async def export_summary():
    """Export current metrics summary."""
    from backend.common.config import RESULTS_DIR
    import json
    metrics = await get_metrics()
    path = RESULTS_DIR / "current_metrics.json"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(metrics.model_dump(), f, indent=2)
    return {"status": "ok", "path": str(path), "metrics": metrics.model_dump()}


@app.get("/api/scenario")
async def get_scenario():
    descriptions = {
        "normal": "Normal network, dynamic offloading",
        "cloud_delay": "Elevated cloud link latency",
        "edge_overload": "Edge node overloaded",
        "emergency": "Smoke alert / emergency event",
    }
    return ScenarioState(
        scenario=edge_models.current_scenario,
        description=descriptions.get(edge_models.current_scenario, ""),
        edge_load_multiplier=metrics_collector.edge_load_multiplier,
        cloud_delay_multiplier=1.0 if edge_models.current_scenario != "cloud_delay" else 6.0,
        network_delay_ms=metrics_collector.network_delay_ms,
    )


@app.post("/api/scenario/normal")
async def scenario_normal():
    await _apply_scenario(Scenario.NORMAL.value)
    return {"scenario": "normal", "status": "ok"}


@app.post("/api/scenario/cloud_delay")
async def scenario_cloud_delay():
    await _apply_scenario(Scenario.CLOUD_DELAY.value)
    return {"scenario": "cloud_delay", "status": "ok"}


@app.post("/api/scenario/edge_overload")
async def scenario_edge_overload():
    await _apply_scenario(Scenario.EDGE_OVERLOAD.value)
    return {"scenario": "edge_overload", "status": "ok"}


@app.post("/api/scenario/emergency")
async def scenario_emergency():
    await _apply_scenario(Scenario.EMERGENCY.value)
    return {"scenario": "emergency", "status": "ok"}


@app.post("/api/strategy/{strategy_name}")
async def set_strategy(strategy_name: str):
    allowed = [s.value for s in OffloadingStrategy]
    if strategy_name not in allowed:
        raise HTTPException(400, f"Unknown strategy. Allowed: {allowed}")
    edge_models.current_strategy = strategy_name
    db.insert_alert(
        task_id=f"strategy_{strategy_name}",
        device_id="system",
        message=f"Strategy switched to: {strategy_name}",
        alert_category="system",
        alert_level="info",
        alert_type="system_event",
    )
    return {"strategy": strategy_name, "status": "ok"}


# ---- Dataset API ----

@app.get("/api/datasets")
async def list_datasets_api():
    """List all trace datasets (including Google/Alibaba documentation registry entries)."""
    dm = get_dataset_manager()
    return {"datasets": dm.list_all()}


@app.get("/api/datasets/{name}")
async def get_dataset_api(name: str):
    dm = get_dataset_manager()
    try:
        return dm.get(name)
    except KeyError:
        raise HTTPException(404, f"Unknown dataset: {name}")


@app.post("/api/datasets/download")
async def download_default_datasets(force: bool = False):
    """Download MEC + EUA only (auto_download=True); synthetic fallback on failure."""
    dm = get_dataset_manager()
    results = dm.ensure_default_datasets(force=force)
    return {"status": "ok", "downloaded": results}


@app.post("/api/datasets/download/{name}")
async def download_dataset_api(name: str, force: bool = False):
    dm = get_dataset_manager()
    try:
        result = dm.download_one(name, force=force)
    except KeyError:
        raise HTTPException(404, f"Unknown dataset: {name}")
    if result.get("status") == "manual_only":
        raise HTTPException(
            400,
            result.get("message", "Large trace — register only, manual download required"),
        )
    return result


# ---- LATE-Learn ML API ----

@app.post("/api/ml/train", response_model=MLTrainResult)
async def train_late_learn_api(
    limit: int = 2000,
    label_source: str = None,
):
    """CPU-train LATE-Learn (default Oracle Cost Labeling, optional teacher)."""
    from backend.common.config import LATE_LEARN_LABEL_SOURCE
    from backend.ml.predictor import clear_model_cache
    from backend.ml.train import train_late_learn
    src = (label_source or LATE_LEARN_LABEL_SOURCE or "oracle").lower()
    try:
        get_dataset_manager().ensure_default_datasets()
        meta = train_late_learn(limit=limit, label_source=src)
        clear_model_cache()
        return MLTrainResult(
            status="ok",
            train_samples=meta.get("train_samples", 0),
            test_accuracy=meta.get("test_accuracy", 0),
            model_path=meta.get("path", ""),
            message=f"LATE-Learn trained (label_source={src})",
        )
    except Exception as e:
        logger.exception("LATE-Learn training failed")
        return MLTrainResult(status="error", message=str(e))


@app.get("/api/ml/status")
async def ml_status_api():
    from backend.common.config import LATE_LEARN_MODEL_PATH, ML_EVAL_REPORT_PATH, ML_METADATA_PATH
    from backend.ml.predictor import load_model
    payload = load_model()
    meta = {}
    if ML_METADATA_PATH.exists():
        try:
            with open(ML_METADATA_PATH, encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            pass
    if payload:
        meta = {**payload.get("meta", {}), **meta}
    if not payload and not meta:
        return {
            "method": "LATE-Learn",
            "loaded": False,
            "path": str(LATE_LEARN_MODEL_PATH),
            "label_source": None,
        }
    return {
        "method": "LATE-Learn",
        "loaded": payload is not None,
        "path": str(LATE_LEARN_MODEL_PATH),
        "meta": meta,
        "label_source": meta.get("label_source"),
        "oracle_agreement": meta.get("oracle_agreement"),
        "avg_regret": meta.get("avg_regret"),
        "public_trace_used": meta.get("public_trace_used"),
        "fallback_used": meta.get("fallback_used"),
        "evaluation_report": str(ML_EVAL_REPORT_PATH) if ML_EVAL_REPORT_PATH.exists() else None,
    }


# ---- LATE-RL API ----

@app.get("/api/rl/status")
async def rl_status_api():
    from backend.common.config import LATE_RL_METADATA_PATH, LATE_RL_MODEL_PATH
    if not LATE_RL_MODEL_PATH.exists():
        return {
            "late_rl_available": False,
            "message": "LATE-RL model not found. Run bash scripts/train_late_rl.sh first.",
            "fallback_enabled": True,
        }
    meta = {}
    if LATE_RL_METADATA_PATH.exists():
        try:
            with open(LATE_RL_METADATA_PATH, encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            pass
    return {
        "late_rl_available": True,
        "model_type": meta.get("model_type", "sklearn_fitted_q"),
        "episodes": meta.get("episodes"),
        "episode_length": meta.get("episode_length"),
        "avg_reward_last_10": meta.get("avg_reward_last_10"),
        "best_avg_reward": meta.get("best_avg_reward"),
        "epsilon_final": meta.get("epsilon_final"),
        "created_at": meta.get("created_at"),
        "fallback_enabled": True,
        "state_dim": meta.get("state_dim"),
    }


@app.post("/api/rl/reload")
async def rl_reload_api():
    from backend.rl.predictor import clear_agent_cache, load_agent
    clear_agent_cache()
    agent = load_agent()
    return {
        "status": "ok",
        "loaded": agent is not None,
        "message": "LATE-RL model reloaded" if agent else "LATE-RL model not found",
    }


# ---- Digital Twin API ----

@app.get("/api/digital_twin/status")
async def digital_twin_status_api():
    mc = metrics_collector
    edge_m = mc.get_node_metrics()
    cloud_cpu = 0.0
    cloud_mem = 0.0
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{CLOUD_SERVER_URL}/api/cloud/metrics")
            if resp.status_code == 200:
                cm = resp.json()
                cloud_cpu = cm.get("cpu_percent", 0)
                cloud_mem = cm.get("memory_percent", 0)
    except Exception:
        pass
    try:
        recent = db.get_recent_tasks(limit=100)
        recent_count = len(recent)
    except Exception:
        recent_count = 0
    cloud_delay = mc.network_delay_ms + mc.extra_cloud_delay_ms
    return {
        "digital_twin_enabled": True,
        "device_twin": {
            "device_count": len(REGISTERED_DEVICES),
            "device_types": ["temperature", "humidity", "smoke", "camera", "access_control"],
        },
        "network_twin": {
            "communication_modes": ["http_fallback", "mqtt_optional"],
            "current_cloud_delay_ms": round(cloud_delay, 1),
            "bandwidth_mbps": round(mc.bandwidth_usage * 100, 1),
        },
        "edge_twin": {
            "cpu_percent": round(edge_m.cpu_percent, 1),
            "memory_percent": round(edge_m.memory_percent, 1),
            "queue_depth": mc.queue_depth,
        },
        "cloud_twin": {
            "cpu_percent": round(cloud_cpu, 1),
            "memory_percent": round(cloud_mem, 1),
            "cloud_delay_ms": round(cloud_delay, 1),
        },
        "workload_twin": {
            "recent_task_count": recent_count,
            "scenario": edge_models.current_scenario,
            "current_strategy": edge_models.current_strategy,
        },
    }


# ---- Demo Mode API ----

_demo_mode_active = False


@app.post("/api/demo/reset_state")
async def demo_reset_state():
    """Reset in-memory strategy stats (use with reset_demo_data)."""
    metrics_collector.reset_strategy_stats()
    edge_models.current_scenario = Scenario.NORMAL.value
    edge_models.current_strategy = OffloadingStrategy.DYNAMIC.value
    metrics_collector.set_scenario(Scenario.NORMAL.value)
    await _sync_cloud_scenario(Scenario.NORMAL.value)
    return {"status": "ok", "message": "Runtime state reset"}


@app.post("/api/demo/start")
async def demo_start():
    global _demo_mode_active
    _demo_mode_active = True
    await _apply_scenario(Scenario.NORMAL.value)
    edge_models.current_strategy = OffloadingStrategy.DYNAMIC.value
    db.insert_alert(
        task_id="demo_start",
        device_id="system",
        message="Demo Mode started. Strategy=dynamic, Scenario=normal. Tip: set TASK_INTERVAL_SEC=1 for faster tasks.",
        alert_category="system",
        alert_level="info",
        alert_type="system_event",
    )
    return {"status": "ok", "demo_mode": True, "tip": "Optional: export TASK_INTERVAL_SEC=1 and restart simulator"}


@app.post("/api/demo/stop")
async def demo_stop():
    global _demo_mode_active
    _demo_mode_active = False
    await _apply_scenario(Scenario.NORMAL.value)
    edge_models.current_strategy = OffloadingStrategy.DYNAMIC.value
    db.insert_alert(
        task_id="demo_stop",
        device_id="system",
        message="Demo Mode stopped. Restored normal + dynamic.",
        alert_category="system",
        alert_level="info",
        alert_type="system_event",
    )
    return {"status": "ok", "demo_mode": False}


@app.post("/api/demo/trigger_smoke")
async def demo_trigger_smoke():
    """Submit a smoke alert task for demo purposes."""
    import uuid
    task_data = {
        "task_id": f"demo_smoke_{uuid.uuid4().hex[:8]}",
        "device_id": "smoke_sensor_01",
        "task_type": "smoke_alert",
        "priority": "high",
        "data_size_kb": 5.0,
        "compute_cost": 0.5,
        "deadline_ms": 200,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "topic": "smart_park/devices/smoke_sensor_01/tasks",
    }
    result = await process_task(task_data)
    return {"status": "ok", "task": result}


@app.post("/api/demo/scenario_tour")
async def demo_scenario_tour():
    """Cycle through four scenarios (immediate switch each; frontend controls dwell time)."""
    tour = ["normal", "cloud_delay", "edge_overload", "emergency"]
    for s in tour:
        await _apply_scenario(s)
    await _apply_scenario(Scenario.NORMAL.value)
    db.insert_alert(
        task_id="demo_tour",
        device_id="system",
        message="Scenario tour completed: normal → cloud_delay → edge_overload → emergency → normal",
        alert_category="system",
        alert_level="info",
        alert_type="system_event",
    )
    return {"status": "ok", "tour": tour, "final": "normal"}


@app.get("/api/demo/status")
async def demo_status():
    return {"demo_mode": _demo_mode_active, "scenario": edge_models.current_scenario, "strategy": edge_models.current_strategy}


from backend.agents.routes import router as agent_router

app.include_router(agent_router, prefix="/api/agent")

if IMAGES_DIR.is_dir():
    app.mount("/api/images", StaticFiles(directory=str(IMAGES_DIR)), name="dashboard_images")


# MQTT callback
def _mqtt_task_handler(payload: dict):
    asyncio.create_task(process_task(payload))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=EDGE_PORT)
