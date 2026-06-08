#!/bin/bash
# ComputerNet 一键启动脚本
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# 可选：加载 .env（LLM 相关配置，勿提交 .env）
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.env"
    set +a
fi

LOGS_DIR="$PROJECT_ROOT/logs"
PID_DIR="$LOGS_DIR/pids"
mkdir -p "$LOGS_DIR" "$PID_DIR" "$PROJECT_ROOT/data" "$PROJECT_ROOT/data/traces" "$PROJECT_ROOT/data/models"

# 安装/更新 Python 依赖（含 scikit-learn for LATE-Learn）
python -m pip install -q -r "$PROJECT_ROOT/requirements.txt" 2>/dev/null || true

# 默认下载 MEC / EUA trace（失败则 synthetic fallback）
if [ "${AUTO_DOWNLOAD_DATASETS:-1}" != "0" ]; then
    echo "[数据集] 尝试下载 MEC + EUA trace ..."
    python "$PROJECT_ROOT/scripts/download_datasets.py" > "$LOGS_DIR/datasets.log" 2>&1 || true
fi

# 默认 HTTP fallback 通信
export COMM_MODE="${COMM_MODE:-http}"
export PYTHONPATH="$PROJECT_ROOT"
export EDGE_PORT="${EDGE_PORT:-8000}"
export CLOUD_PORT="${CLOUD_PORT:-8001}"
export TASK_INTERVAL_SEC="${TASK_INTERVAL_SEC:-2.0}"

echo "=========================================="
echo " ComputerNet 系统启动"
echo " 项目目录: $PROJECT_ROOT"
echo " 通信模式: $COMM_MODE"
echo "=========================================="

# 检查 conda 环境
if [ -z "$CONDA_DEFAULT_ENV" ] || [ "$CONDA_DEFAULT_ENV" != "ComputerNet" ]; then
    echo "[警告] 当前未激活 ComputerNet conda 环境"
    echo "  请先运行: conda activate ComputerNet"
fi

# 启动前先停止旧进程
bash "$SCRIPT_DIR/stop_all.sh" 2>/dev/null || true
sleep 1

start_service() {
    local name=$1
    local cmd=$2
    local logfile="$LOGS_DIR/${name}.log"
    echo "[启动] $name ..."
    nohup bash -c "$cmd" > "$logfile" 2>&1 &
    echo $! > "$PID_DIR/${name}.pid"
    echo "  PID: $(cat $PID_DIR/${name}.pid) | 日志: $logfile"
}

# 可选: MQTT Broker
if [ "$COMM_MODE" = "mqtt" ]; then
    start_service "mqtt_broker" "cd '$PROJECT_ROOT' && python mqtt/broker.py"
    sleep 2
fi

# 1. Cloud Server (必须先启动)
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
        echo "[安装] 前端依赖..."
        export npm_config_cache="$PROJECT_ROOT/.npm-cache"
        mkdir -p "$npm_config_cache"
        cd "$PROJECT_ROOT/frontend" && npm install --cache "$npm_config_cache"
        cd "$PROJECT_ROOT"
    fi
    start_service "frontend" "cd '$PROJECT_ROOT/frontend' && npm run dev"
else
    echo "[跳过] 未检测到 npm，请手动安装 Node.js 后运行前端"
    echo "  cd frontend && npm install && npm run dev"
fi

sleep 3

echo ""
echo "=========================================="
echo " 启动完成!"
echo "------------------------------------------"
echo " Dashboard:  http://localhost:3000"
echo " Edge API:   http://localhost:8000/docs"
echo " Cloud API:  http://localhost:8001/docs"
echo "------------------------------------------"
echo " 停止: bash scripts/stop_all.sh"
echo " 测试: bash scripts/test_system.sh"
echo "=========================================="
