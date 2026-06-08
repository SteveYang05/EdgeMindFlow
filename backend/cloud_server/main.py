"""
Cloud Server - cloud task processing service
Port: 8001
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.cloud_server.executor import execute_task
from backend.cloud_server.models import cloud_metrics
from backend.common.config import CLOUD_PORT
from backend.common.schemas import CloudExecuteRequest, CloudExecuteResponse, NodeMetrics

app = FastAPI(
    title="ComputerNet Cloud Server",
    description="Smart campus edge computing system — cloud service",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "cloud_server", "port": CLOUD_PORT}


@app.get("/api/cloud/metrics", response_model=NodeMetrics)
async def get_metrics():
    m = cloud_metrics.get_metrics()
    return NodeMetrics(
        cpu_percent=m.cpu_percent,
        memory_percent=m.memory_percent,
        simulated_load=m.simulated_load,
        network_delay_ms=m.network_delay_ms,
        bandwidth_usage_mbps=m.bandwidth_usage_mbps,
        active_tasks=m.active_tasks,
    )


@app.post("/api/cloud/execute", response_model=CloudExecuteResponse)
async def cloud_execute(req: CloudExecuteRequest):
    result = await execute_task(
        req.task_id,
        req.compute_cost,
        req.data_size_kb,
        cloud_metrics,
    )
    return CloudExecuteResponse(**result)


@app.post("/api/cloud/set_delay")
async def set_delay(payload: dict):
    delay = float(payload.get("delay_ms", 0))
    cloud_metrics.set_delay(delay)
    return {"status": "ok", "delay_ms": delay}


@app.post("/api/cloud/set_load")
async def set_load(payload: dict):
    load = float(payload.get("load", 0.3))
    cloud_metrics.set_load(load)
    return {"status": "ok", "load": load}


@app.get("/api/cloud/stats")
async def cloud_stats():
    return {
        "processed_count": cloud_metrics.processed_count,
        "metrics": cloud_metrics.get_metrics().model_dump(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=CLOUD_PORT)
