"""Camera image recognition task simulator."""
import sys, time, logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from simulator.device_simulator import submit_task
from simulator.task_generator import generate_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("camera_sim")

if __name__ == "__main__":
    logger.info("Camera simulator started")
    while True:
        submit_task(generate_task("camera_01"))
        time.sleep(5)
