"""
Lightweight MQTT Broker startup script (optional).

Start broker on localhost:1883 using the amqtt library.
If amqtt is unavailable, use HTTP fallback (default).
"""
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mqtt_broker")


async def start_amqtt_broker(host="0.0.0.0", port=1883):
    """Start MQTT broker using amqtt."""
    try:
        from amqtt.broker import Broker
        config = {
            "listeners": {
                "default": {
                    "type": "tcp",
                    "bind": f"{host}:{port}",
                }
            }
        }
        broker = Broker(config)
        await broker.start()
        logger.info("AMQTT Broker running on %s:%d", host, port)
        while True:
            await asyncio.sleep(3600)
    except ImportError:
        logger.error("amqtt not installed. Use HTTP fallback: COMM_MODE=http")
        sys.exit(1)
    except Exception as e:
        logger.error("Broker start failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(start_amqtt_broker())
