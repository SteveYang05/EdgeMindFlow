"""Global configuration — ports, weights, scenario defaults, etc."""
import os
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
RESULTS_DIR = PROJECT_ROOT / "results"
BACKUPS_DIR = PROJECT_ROOT / "backups"
TRACES_DIR = DATA_DIR / "traces"
MODELS_DIR = DATA_DIR / "models"
DB_PATH = DATA_DIR / "computernet.db"
LATE_LEARN_MODEL_PATH = MODELS_DIR / "late_learn.pkl"
ML_MODELS_DIR = PROJECT_ROOT / "ml" / "models"
ML_METADATA_PATH = ML_MODELS_DIR / "model_metadata.json"
ML_EVAL_REPORT_PATH = ML_MODELS_DIR / "evaluation_report.json"

# Service ports
EDGE_PORT = int(os.getenv("EDGE_PORT", "8000"))
CLOUD_PORT = int(os.getenv("CLOUD_PORT", "8001"))
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", "3000"))

# Communication mode: http | mqtt
COMM_MODE = os.getenv("COMM_MODE", "http").lower()

# Cloud Server URL
CLOUD_SERVER_URL = os.getenv("CLOUD_SERVER_URL", f"http://localhost:{CLOUD_PORT}")
EDGE_SERVER_URL = os.getenv("EDGE_SERVER_URL", f"http://localhost:{EDGE_PORT}")

# Task offloading score weights (LATE-Offload / Dynamic)
WEIGHT_LATENCY = float(os.getenv("W_LATENCY", "0.30"))
WEIGHT_LOAD = float(os.getenv("W_LOAD", "0.20"))
WEIGHT_TRANSFER = float(os.getenv("W_TRANSFER", "0.15"))
WEIGHT_DEADLINE = float(os.getenv("W_DEADLINE", "0.15"))
WEIGHT_PRIORITY = float(os.getenv("W_PRIORITY", "0.10"))
WEIGHT_QOS = float(os.getenv("W_QOS", "0.10"))

# Node compute capacity (abstract MIPS)
LOCAL_COMPUTE_CAPACITY = float(os.getenv("LOCAL_COMPUTE_CAPACITY", "25.0"))
EDGE_COMPUTE_CAPACITY = float(os.getenv("EDGE_COMPUTE_CAPACITY", "120.0"))
CLOUD_COMPUTE_CAPACITY = float(os.getenv("CLOUD_COMPUTE_CAPACITY", "500.0"))

# Offloading bias: controls local/edge/cloud distribution ratio
LOCAL_STABILITY_PENALTY = float(os.getenv("LOCAL_STABILITY_PENALTY", "0.18"))
EDGE_PREFERENCE_BONUS = float(os.getenv("EDGE_PREFERENCE_BONUS", "0.10"))
CLOUD_TRANSFER_PENALTY = float(os.getenv("CLOUD_TRANSFER_PENALTY", "0.12"))
CLOUD_DELAY_SCENARIO_PENALTY = float(os.getenv("CLOUD_DELAY_SCENARIO_PENALTY", "0.45"))
EDGE_OVERLOAD_PENALTY = float(os.getenv("EDGE_OVERLOAD_PENALTY", "0.35"))

# Small-task threshold (KB)
SMALL_TASK_KB = float(os.getenv("SMALL_TASK_KB", "10.0"))
LARGE_TASK_KB = float(os.getenv("LARGE_TASK_KB", "100.0"))

# Default network parameters (ms, Mbps)
DEFAULT_EDGE_CLOUD_DELAY_MS = 50.0
DEFAULT_BANDWIDTH_MBPS = 100.0
DEFAULT_UPLOAD_BASE_MS = 5.0

# Simulator task generation interval (seconds)
TASK_INTERVAL_SEC = float(os.getenv("TASK_INTERVAL_SEC", "2.0"))

# Dataset download (MEC / EUA attempted by default; see docs/datasets.md for Google / Alibaba)
AUTO_DOWNLOAD_DATASETS = os.getenv("AUTO_DOWNLOAD_DATASETS", "1").lower() in ("1", "true", "yes")
MEC_EDGE_DATASET_URL = os.getenv("MEC_EDGE_DATASET_URL", "")
EUA_DATASET_URL = os.getenv("EUA_DATASET_URL", "")
EUA_EDGE_SITES_URL = os.getenv("EUA_EDGE_SITES_URL", "")

# LATE-Learn training
LATE_LEARN_MIN_SAMPLES = int(os.getenv("LATE_LEARN_MIN_SAMPLES", "50"))
LATE_LEARN_LABEL_SOURCE = os.getenv("LATE_LEARN_LABEL_SOURCE", "oracle")
LATE_LEARN_ABLATION_SAMPLES = int(os.getenv("LATE_LEARN_ABLATION_SAMPLES", "2000"))

# LATE-RL training
LATE_RL_MODEL_PATH = MODELS_DIR / "late_rl.pkl"
LATE_RL_METADATA_PATH = MODELS_DIR / "late_rl_metadata.json"
RL_CANDIDATES_DIR = MODELS_DIR / "rl_candidates"
RL_TRAIN_EPISODES = int(os.getenv("RL_TRAIN_EPISODES", "200"))
RL_EPISODE_LENGTH = int(os.getenv("RL_EPISODE_LENGTH", "200"))
RL_RANDOM_SEED = int(os.getenv("RL_RANDOM_SEED", "42"))
RL_EVAL_EPISODES = int(os.getenv("RL_EVAL_EPISODES", "20"))
RL_EVAL_EPISODE_LENGTH = int(os.getenv("RL_EVAL_EPISODE_LENGTH", "100"))

# Automated experiments
EXPERIMENT_DURATION_SEC = int(os.getenv("EXPERIMENT_DURATION_SEC", "30"))
DEMO_EXPERIMENT_DURATION_SEC = int(os.getenv("DEMO_EXPERIMENT_DURATION_SEC", "20"))

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
TRACES_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
ML_MODELS_DIR.mkdir(parents=True, exist_ok=True)
RL_CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
