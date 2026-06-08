"""温湿度传感器专用模拟器（可被 device_simulator 替代）。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulator.device_simulator import submit_task
from simulator.task_generator import generate_task
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sensor_sim")

DEVICES = ["temperature_sensor_01", "humidity_sensor_01"]

if __name__ == "__main__":
    logger.info("Sensor simulator started")
    while True:
        for d in DEVICES:
            task = generate_task(d)
            submit_task(task)
            time.sleep(3)
