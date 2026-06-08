"""Access control pass-record task simulator."""
import sys, time, logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from simulator.device_simulator import submit_task
from simulator.task_generator import generate_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("access_sim")

if __name__ == "__main__":
    logger.info("Access control simulator started")
    while True:
        submit_task(generate_task("access_control_01"))
        time.sleep(4)
