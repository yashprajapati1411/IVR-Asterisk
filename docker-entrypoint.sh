#!/bin/bash
set -e

echo "=== Starting Asterisk Gujarati IVR System ==="

# 1. Initialize DB and seed tables if not already done
python3 /app/scripts/seed_db.py

# 2. Start Python FastAGI Server & FastAPI Dashboard Server in background
echo "Starting FastAGI Server on 0.0.0.0:4573..."
python3 /app/agi/server.py --host 0.0.0.0 --port 4573 &
FASTAGI_PID=$!

echo "Starting Receptionist Dashboard Web Server on 0.0.0.0:8000..."
python3 -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 &
DASHBOARD_PID=$!

# Wait briefly for servers to bind
sleep 2

# Check if FastAGI process is running
if ! kill -0 $FASTAGI_PID 2>/dev/null; then
    echo "ERROR: FastAGI Server failed to start!"
    exit 1
fi

echo "FastAGI Server running (PID $FASTAGI_PID) and Dashboard running (PID $DASHBOARD_PID)."

# Handle shutdown signals
trap "echo 'Stopping Asterisk & FastAGI...'; kill $FASTAGI_PID $DASHBOARD_PID 2>/dev/null; asterisk -rx 'core stop now'; exit 0" SIGINT SIGTERM

# 3. Start Asterisk in foreground
echo "Starting Asterisk PBX..."
exec asterisk -f -vvvg
