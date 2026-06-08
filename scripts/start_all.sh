#!/bin/bash
# ComputerNet one-click startup script
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Optional: load .env (LLM config; do not commit .env)
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.env"
    set +a
fi

LOGS_DIR="$PROJECT_ROOT/logs"
PID_DIR="$LOGS_DIR/pids"
mkdir -p "$LOGS_DIR" "$PID_DIR" "$PROJECT_ROOT/data" "$PROJECT_ROOT/data/traces" "$PROJECT_ROOT/data/models"

# Install/update Python dependencies (includes scikit-learn for LATE-Learn)
python -m pip install -q -r "$PROJECT_ROOT/requirements.txt" 2>/dev/null || true

# Download MEC / EUA trace by default (synthetic fallback on failure)
if [ "${AUTO_DOWNLOAD_DATASETS:-1}" != "0" ]; then
    echo "[Datasets] Attempting MEC + EUA trace download ..."
    python "$PROJECT_ROOT/scripts/download_datasets.py" > "$LOGS_DIR/datasets.log" 2>&1 || true
fi

# Default HTTP fallback communication
export COMM_MODE="${COMM_MODE:-http}"
export PYTHONPATH="$PROJECT_ROOT"
export EDGE_PORT="${EDGE_PORT:-8000}"
export CLOUD_PORT="${CLOUD_PORT:-8001}"
export TASK_INTERVAL_SEC="${TASK_INTERVAL_SEC:-2.0}"

echo "=========================================="
echo " ComputerNet system startup"
echo " Project directory: $PROJECT_ROOT"
echo " Communication mode: $COMM_MODE"
echo "=========================================="

# Check conda environment
if [ -z "$CONDA_DEFAULT_ENV" ] || [ "$CONDA_DEFAULT_ENV" != "ComputerNet" ]; then
    echo "[Warning] ComputerNet conda environment is not active"
    echo "  Run first: conda activate ComputerNet"
fi

# Stop old processes before starting
bash "$SCRIPT_DIR/stop_all.sh" 2>/dev/null || true
sleep 1

start_service() {
    local name=$1
    local cmd=$2
    local logfile="$LOGS_DIR/${name}.log"
    echo "[Starting] $name ..."
    nohup bash -c "$cmd" > "$logfile" 2>&1 &
    echo $! > "$PID_DIR/${name}.pid"
    echo "  PID: $(cat $PID_DIR/${name}.pid) | Log: $logfile"
}

# Optional: MQTT Broker
if [ "$COMM_MODE" = "mqtt" ]; then
    start_service "mqtt_broker" "cd '$PROJECT_ROOT' && python mqtt/broker.py"
    sleep 2
fi

# 1. Cloud Server (must start first)
start_service "cloud_server" "cd '$PROJECT_ROOT' && python -m backend.cloud_server.main"
sleep 2

# 2. Edge Server
start_service "edge_server" "cd '$PROJECT_ROOT' && python -m backend.edge_server.main"
sleep 2

# 3. IoT Device Simulator
start_service "device_simulator" "cd '$PROJECT_ROOT' && python simulator/device_simulator.py"

# 4. Frontend Dashboard
if command -v npm &> /dev/null; then
    if [ ! -d "$PROJECT_ROOT/frontend/node_modules" ]; then
        echo "[Installing] frontend dependencies..."
        export npm_config_cache="$PROJECT_ROOT/.npm-cache"
        mkdir -p "$npm_config_cache"
        cd "$PROJECT_ROOT/frontend" && npm install --cache "$npm_config_cache"
        cd "$PROJECT_ROOT"
    fi
    start_service "frontend" "cd '$PROJECT_ROOT/frontend' && npm run dev"
else
    echo "[Skip] npm not found — install Node.js manually to run frontend"
    echo "  cd frontend && npm install && npm run dev"
fi

sleep 3

echo ""
echo "=========================================="
echo " Startup complete!"
echo "------------------------------------------"
echo " Dashboard:  http://localhost:3000"
echo " Edge API:   http://localhost:8000/docs"
echo " Cloud API:  http://localhost:8001/docs"
echo "------------------------------------------"
echo " Stop: bash scripts/stop_all.sh"
echo " Test: bash scripts/test_system.sh"
echo "=========================================="
