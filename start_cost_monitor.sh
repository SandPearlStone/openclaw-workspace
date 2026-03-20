#!/bin/bash
# Start OpenClaw Cost Monitor with Prometheus exporter

set -e

WORKSPACE="/home/sandro/.openclaw/workspace"
LOG_FILE="$WORKSPACE/cost_monitor.log"
PID_FILE="$WORKSPACE/cost_monitor.pid"

cd "$WORKSPACE"

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "⚠️  Cost monitor already running (PID $OLD_PID)"
        exit 1
    else
        rm "$PID_FILE"
    fi
fi

# Start exporter in background
echo "🚀 Starting OpenClaw Cost Monitor (Prometheus exporter on :9200)"
python3 prometheus_exporter.py > "$LOG_FILE" 2>&1 &
NEW_PID=$!

# Save PID
echo $NEW_PID > "$PID_FILE"

echo "✅ Cost monitor started (PID $NEW_PID)"
echo "   Metrics: http://localhost:9200/metrics"
echo "   Health: http://localhost:9200/health"
echo "   Grafana: http://localhost:3000"
echo "   Logs: tail -f $LOG_FILE"
