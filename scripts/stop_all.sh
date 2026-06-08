#!/bin/bash
# ComputerNet stop script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PID_DIR="$PROJECT_ROOT/logs/pids"

echo "Stopping ComputerNet services..."

# Stop via PID files
if [ -d "$PID_DIR" ]; then
    for pidfile in "$PID_DIR"/*.pid; do
        [ -f "$pidfile" ] || continue
        name=$(basename "$pidfile" .pid)
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            echo "  Stopped $name (PID $pid)"
        fi
        rm -f "$pidfile"
    done
fi

# Fallback: clean up by port and process name
for port in 8000 8001 3000 1883; do
    pids=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill -9 2>/dev/null || true
        echo "  Released port $port"
    fi
done

pkill -f "backend.edge_server.main" 2>/dev/null || true
pkill -f "backend.cloud_server.main" 2>/dev/null || true
pkill -f "device_simulator" 2>/dev/null || true
pkill -f "mqtt/broker" 2>/dev/null || true
pkill -f "vite.*3000" 2>/dev/null || true

echo "All services stopped."
