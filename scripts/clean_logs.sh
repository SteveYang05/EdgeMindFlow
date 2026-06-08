#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="$(dirname "$SCRIPT_DIR")/logs"
echo "Cleaning logs directory: $LOGS_DIR"
rm -f "$LOGS_DIR"/*.log
rm -rf "$LOGS_DIR/pids"
echo "Done."
