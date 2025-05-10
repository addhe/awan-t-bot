#!/bin/bash

# Configuration
BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$BOT_DIR/bot.pid"
LOG_FILE="$BOT_DIR/logs/trading_bot.log"
RUN_SCRIPT="$BOT_DIR/run.sh"
SCRIPT_PATH="$BOT_DIR/bot.py"

# Function to get PID of run.sh
get_run_script_pid() {
    # More robust detection of run.sh processes
    pgrep -f "./run.sh" || pgrep -f "bash.*run.sh" || ps aux | grep "[r]un.sh" | awk '{print $2}'
}

# Function to get all bot.py PIDs
get_all_bot_pids() {
    # Get PIDs from pgrep
    local ALL_PIDS=$(pgrep -f "python3.*$SCRIPT_PATH")
    local VERIFIED_PIDS=""
    
    # Verify each PID is actually running
    for PID in $ALL_PIDS; do
        if ps -p $PID > /dev/null; then
            if [ -z "$VERIFIED_PIDS" ]; then
                VERIFIED_PIDS="$PID"
            else
                VERIFIED_PIDS="$VERIFIED_PIDS $PID"
            fi
        fi
    done
    
    echo "$VERIFIED_PIDS"
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

# First, stop the Python bot if it's running via PID file
if [ -f "$PID_FILE" ]; then
    BOT_PID=$(cat "$PID_FILE")

    # Verify Python process exists
    if kill -0 $BOT_PID 2>/dev/null; then
        stop_process $BOT_PID "trading bot (from PID file)"
        rm -f "$PID_FILE"
    else
        echo "Trading bot not running (stale PID file)"
        rm -f "$PID_FILE"
    fi
else
    echo "Trading bot PID file not found"
fi

# Then stop run.sh if it's running
RUN_PID=$(get_run_script_pid)
if [ ! -z "$RUN_PID" ]; then
    stop_process $RUN_PID "run.sh script"
else
    echo "run.sh script not found running"
fi

# Log the stop action
echo "$(date): Bot stopped by user" >> "$LOG_FILE"

# Stop ALL remaining bot.py processes
REMAINING_PYTHON=$(get_all_bot_pids)
if [ ! -z "$REMAINING_PYTHON" ]; then
    echo "Found remaining Python bot processes, stopping them..."
    for PID in $REMAINING_PYTHON; do
        stop_process $PID "additional bot process"
    done
fi

# Double check no run.sh processes are left
REMAINING_RUN=$(get_run_script_pid)
if [ ! -z "$REMAINING_RUN" ]; then
    echo "Found remaining run.sh processes, forcing stop..."
    kill -9 $REMAINING_RUN
fi

# Final verification
FINAL_CHECK=$(get_all_bot_pids)
if [ ! -z "$FINAL_CHECK" ]; then
    echo "WARNING: Some bot processes still running. Forcing stop..."
    kill -9 $FINAL_CHECK
fi

echo "Stop completed"
