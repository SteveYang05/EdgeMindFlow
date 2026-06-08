"""
MQTT client — subscribes to IoT device task topics.

Topic design: smart_park/devices/{device_id}/tasks
HTTP fallback by default; MQTT is an optional enhancement.
"""
import json
import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger("edge_mqtt")

try:
    import paho.mqtt.client as mqtt
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False


class EdgeMQTTSubscriber:
    """Edge node MQTT subscriber."""

    def __init__(
        self,
        broker_host: str,
        broker_port: int,
        on_task: Callable[[dict], None],
    ):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.on_task = on_task
        self._client: Optional[object] = None
        self._connected = False

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            client.subscribe("smart_park/devices/+/tasks")
            logger.info("MQTT subscribed: smart_park/devices/+/tasks")
        else:
            logger.warning("MQTT connect failed rc=%s", rc)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            self.on_task(payload)
        except Exception as e:
            logger.error("MQTT message parse error: %s", e)

    def start(self) -> bool:
        """Start MQTT subscription (background thread)."""
        if not PAHO_AVAILABLE:
            logger.warning("paho-mqtt not available")
            return False
        try:
            client = mqtt.Client(client_id="edge_server_sub")
            client.on_connect = self._on_connect
            client.on_message = self._on_message
            client.connect(self.broker_host, self.broker_port, 60)
            self._client = client

            def loop():
                client.loop_forever()

            t = threading.Thread(target=loop, daemon=True)
            t.start()
            return True
        except Exception as e:
            logger.warning("MQTT subscriber start failed: %s", e)
            return False

    def stop(self):
        if self._client:
            self._client.disconnect()
