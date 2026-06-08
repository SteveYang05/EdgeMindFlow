"""Edge server runtime state models."""
from backend.common.schemas import OffloadingStrategy, Scenario
from backend.edge_server.metrics import EdgeMetricsCollector

# Global singleton state
metrics_collector = EdgeMetricsCollector()
current_strategy: str = OffloadingStrategy.DYNAMIC.value
current_scenario: str = Scenario.NORMAL.value

# Registered device list
REGISTERED_DEVICES = [
    {
        "device_id": "temperature_sensor_01",
        "type": "sensor",
        "task_types": ["temperature_report"],
        "status": "online",
    },
    {
        "device_id": "humidity_sensor_01",
        "type": "sensor",
        "task_types": ["humidity_report"],
        "status": "online",
    },
    {
        "device_id": "smoke_sensor_01",
        "type": "sensor",
        "task_types": ["smoke_alert"],
        "status": "online",
    },
    {
        "device_id": "camera_01",
        "type": "camera",
        "task_types": ["image_detection"],
        "status": "online",
    },
    {
        "device_id": "access_control_01",
        "type": "access",
        "task_types": ["access_control"],
        "status": "online",
    },
]
