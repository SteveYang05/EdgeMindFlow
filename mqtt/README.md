# MQTT Communication Module

## Topic Design

```
smart_park/devices/{device_id}/tasks
```

## Option A: Lightweight MQTT (optional)

1. Start broker: `python mqtt/broker.py`
2. Set environment variable: `export COMM_MODE=mqtt`
3. Restart the system

## Option B: HTTP Fallback (default)

This project **defaults to HTTP fallback** — no Mosquitto installation required:

```
POST http://localhost:8000/api/tasks/submit
```

The request body still includes a `topic` field to reflect the MQTT architecture design.

## Switching Modes

Modify the `COMM_MODE` environment variable in `scripts/start_all.sh`.
