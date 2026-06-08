"""HTTP 任务接入层 - Fallback 通信方案。"""
from backend.common.schemas import TaskSubmit


def normalize_task(payload: TaskSubmit) -> dict:
    """标准化任务 payload。"""
    data = payload.model_dump()
    if not data.get("topic"):
        data["topic"] = f"smart_park/devices/{data['device_id']}/tasks"
    return data
