#!/bin/bash

# Configuration
BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$BOT_DIR/logs/trading_bot.log"
PID_FILE="$BOT_DIR/bot.pid"

# Create logs directory if it doesn't exist
mkdir -p "$BOT_DIR/logs"

# Check if the bot is already running
if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    echo "Trading bot is already running!"
    exit 1
fi

# Start the bot in the background
echo "Starting trading bot..."
nohup "$BOT_DIR/run.sh" > /dev/null 2>&1 &

# Wait a moment to check if the bot started successfully
sleep 2

if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    echo "Trading bot started successfully!"
    echo "Check $LOG_FILE for logs"
else
    echo "Failed to start trading bot. Check $LOG_FILE for details"
    exit 1
fi
