#!/bin/bash

# Configuration
BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_PATH="$BOT_DIR/main.py"
LOG_FILE="$BOT_DIR/logs/trading_bot.log"
PID_FILE="$BOT_DIR/bot.pid"

# Create logs directory if it doesn't exist
mkdir -p "$BOT_DIR/logs"

# Function to run the bot with logging
run_bot() {
    echo "$(date): Starting trading bot" >> "$LOG_FILE"

    # Set PYTHONPATH to include the project root
    export PYTHONPATH="$BOT_DIR:$PYTHONPATH"

    # Start the bot and save its PID
    python3 "$SCRIPT_PATH" >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"

    # Wait for the bot process
    wait $!

    EXIT_CODE=$?
    echo "$(date): Trading bot stopped with exit code $EXIT_CODE" >> "$LOG_FILE"

    # Remove PID file when bot stops
    rm -f "$PID_FILE"

    return $EXIT_CODE
}

# Check if another instance is running
if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    echo "Trading bot is already running!"
    exit 1
fi

# Infinite loop to keep the bot running in case of script failure
while true; do
    run_bot

    # If the bot was stopped by stop.sh (exit code 0), don't restart
    if [ $? -eq 0 ]; then
        echo "$(date): Bot stopped normally" >> "$LOG_FILE"
        break
    fi

    echo "$(date): Restarting trading bot after failure" >> "$LOG_FILE"
    sleep 5
done
