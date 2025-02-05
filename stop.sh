#!/bin/bash

# Configuration
BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$BOT_DIR/bot.pid"
LOG_FILE="$BOT_DIR/logs/trading_bot.log"

# Function to stop the bot gracefully
stop_bot() {
    local pid=$1
    echo "Stopping trading bot (PID: $pid)..."

    # Send SIGTERM signal
    kill -TERM $pid

    # Wait up to 30 seconds for the bot to stop gracefully
    for i in {1..30}; do
        if ! kill -0 $pid 2>/dev/null; then
            echo "Trading bot stopped successfully"
            rm -f "$PID_FILE"
            return 0
        fi
        sleep 1
    done

    # If bot hasn't stopped, force kill it
    echo "Bot not responding to graceful shutdown, forcing stop..."
    kill -9 $pid
    rm -f "$PID_FILE"
    echo "Trading bot forcefully stopped"
}

# Check if the bot is running
if [ ! -f "$PID_FILE" ]; then
    echo "Trading bot is not running"
    exit 0
fi

# Get PID from file
PID=$(cat "$PID_FILE")

# Verify PID exists
if ! kill -0 $PID 2>/dev/null; then
    echo "Trading bot not running (stale PID file)"
    rm -f "$PID_FILE"
    exit 0
fi

# Stop the bot
stop_bot $PID

echo "$(date): Bot stopped by user" >> "$LOG_FILE"
