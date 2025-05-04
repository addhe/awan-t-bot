#!/bin/bash

# Configuration
BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$BOT_DIR/logs/trading_bot.log"
PID_FILE="$BOT_DIR/bot.pid"
RUN_SCRIPT="$BOT_DIR/run.sh"
STARTUP_WAIT=10  # Waktu tunggu untuk startup (detik)

# Create logs directory if it doesn't exist
mkdir -p "$BOT_DIR/logs"

# Check if the bot is already running
if [ -f "$PID_FILE" ]; then
    BOT_PID=$(cat "$PID_FILE")
    if kill -0 $BOT_PID 2>/dev/null; then
        echo "Trading bot is already running with PID $BOT_PID!"
        exit 1
    else
        echo "Found stale PID file, removing..."
        rm -f "$PID_FILE"
    fi
fi

# Check for any existing bot.py processes
SCRIPT_PATH="$BOT_DIR/bot.py"
EXISTING_BOTS=$(pgrep -f "python3.*$SCRIPT_PATH")
if [ ! -z "$EXISTING_BOTS" ]; then
    # Verify each process is actually running
    ACTUAL_RUNNING_BOTS=""
    for PID in $EXISTING_BOTS; do
        if ps -p $PID > /dev/null; then
            if [ -z "$ACTUAL_RUNNING_BOTS" ]; then
                ACTUAL_RUNNING_BOTS="$PID"
            else
                ACTUAL_RUNNING_BOTS="$ACTUAL_RUNNING_BOTS $PID"
            fi
        fi
    done
    
    if [ ! -z "$ACTUAL_RUNNING_BOTS" ]; then
        echo "Warning: Found existing bot processes: $ACTUAL_RUNNING_BOTS"
        echo "Consider running stop.sh first"
        exit 1
    else
        echo "Detected stale process references, continuing..."
    fi
fi

# Start the bot in the background
echo "Starting trading bot..."
nohup "$RUN_SCRIPT" > "$BOT_DIR/logs/run_script.log" 2>&1 &
RUN_PID=$!

echo "Run script started with PID $RUN_PID"

# Wait for the bot to start
echo "Waiting up to ${STARTUP_WAIT}s for bot to start..."
for i in $(seq 1 $STARTUP_WAIT); do
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        BOT_PID=$(cat "$PID_FILE")
        echo "Trading bot started successfully with PID $BOT_PID!"
        echo "Check $LOG_FILE for logs"
        exit 0
    fi
    sleep 1
    echo -n "."
done

echo ""
echo "Failed to start trading bot within ${STARTUP_WAIT} seconds."
echo "Check $LOG_FILE and logs/run_script.log for details"

# If we got here, the bot didn't start properly
# Try to clean up the run.sh process
if kill -0 $RUN_PID 2>/dev/null; then
    echo "Terminating run script process..."
    kill $RUN_PID
fi

exit 1
