#!/bin/bash
# ComputerNet 停止脚本
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PID_DIR="$PROJECT_ROOT/logs/pids"

echo "正在停止 ComputerNet 服务..."

# 通过 PID 文件停止
if [ -d "$PID_DIR" ]; then
    for pidfile in "$PID_DIR"/*.pid; do
        [ -f "$pidfile" ] || continue
        name=$(basename "$pidfile" .pid)
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            echo "  已停止 $name (PID $pid)"
        fi
        rm -f "$pidfile"
    done
fi

# 兜底: 按端口和进程名清理
for port in 8000 8001 3000 1883; do
    pids=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill -9 2>/dev/null || true
        echo "  已释放端口 $port"
    fi
done

pkill -f "backend.edge_server.main" 2>/dev/null || true
pkill -f "backend.cloud_server.main" 2>/dev/null || true
pkill -f "device_simulator" 2>/dev/null || true
pkill -f "mqtt/broker" 2>/dev/null || true
pkill -f "vite.*3000" 2>/dev/null || true

echo "所有服务已停止。"
