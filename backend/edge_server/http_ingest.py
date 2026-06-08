"""HTTP task ingest layer — fallback communication."""
from backend.common.schemas import TaskSubmit


def normalize_task(payload: TaskSubmit) -> dict:
    """Normalize task payload."""
    data = payload.model_dump()
    if not data.get("topic"):
        data["topic"] = f"smart_park/devices/{data['device_id']}/tasks"
    return data
