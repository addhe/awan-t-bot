#!/bin/bash

# Configuration
BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$BOT_DIR/bot.pid"
LOG_FILE="$BOT_DIR/logs/trading_bot.log"
RUN_SCRIPT="$BOT_DIR/run.sh"

# Function to get PID of run.sh
get_run_script_pid() {
    pgrep -f "bash.*$RUN_SCRIPT"
}

# Function to stop processes gracefully
stop_process() {
    local pid=$1
    local process_name=$2

    echo "Stopping $process_name (PID: $pid)..."

    # Send SIGTERM signal
    kill -TERM $pid

    # Wait up to 30 seconds for the process to stop gracefully
    for i in {1..30}; do
        if ! kill -0 $pid 2>/dev/null; then
            echo "$process_name stopped successfully"
            return 0
        fi
        sleep 1
    done

    # If process hasn't stopped, force kill it
    echo "$process_name not responding to graceful shutdown, forcing stop..."
    kill -9 $pid
    echo "$process_name forcefully stopped"
}

# First, stop run.sh if it's running
RUN_PID=$(get_run_script_pid)
if [ ! -z "$RUN_PID" ]; then
    stop_process $RUN_PID "run.sh script"
else
    echo "run.sh script not found running"
fi

# Then stop the Python bot if it's running
if [ -f "$PID_FILE" ]; then
    BOT_PID=$(cat "$PID_FILE")

    # Verify Python process exists
    if kill -0 $BOT_PID 2>/dev/null; then
        stop_process $BOT_PID "trading bot"
        rm -f "$PID_FILE"
    else
        echo "Trading bot not running (stale PID file)"
        rm -f "$PID_FILE"
    fi
else
    echo "Trading bot PID file not found"
fi

# Log the stop action
echo "$(date): Bot stopped by user" >> "$LOG_FILE"

# Double check no processes are left
REMAINING_PYTHON=$(pgrep -f "python3.*main.py")
if [ ! -z "$REMAINING_PYTHON" ]; then
    echo "Found remaining Python processes, forcing stop..."
    kill -9 $REMAINING_PYTHON
fi

REMAINING_RUN=$(get_run_script_pid)
if [ ! -z "$REMAINING_RUN" ]; then
    echo "Found remaining run.sh processes, forcing stop..."
    kill -9 $REMAINING_RUN
fi

echo "Stop completed"
