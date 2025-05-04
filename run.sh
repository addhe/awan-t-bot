#!/bin/bash

# Configuration
BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_PATH="$BOT_DIR/bot.py"
LOG_FILE="$BOT_DIR/logs/trading_bot.log"
PID_FILE="$BOT_DIR/bot.pid"
MAX_RESTARTS=10  # Maksimum jumlah restart berturut-turut
RESTART_DELAY=5  # Delay awal (detik)

# Create logs directory if it doesn't exist
mkdir -p "$BOT_DIR/logs"

# Function to run the bot with logging
run_bot() {
    echo "$(date): Starting trading bot" >> "$LOG_FILE"

    # Set PYTHONPATH to include the project root
    export PYTHONPATH="$BOT_DIR:$PYTHONPATH"

    # Start the bot and save its PID
    python3 "$SCRIPT_PATH" >> "$LOG_FILE" 2>&1 &
    BOT_PID=$!
    echo $BOT_PID > "$PID_FILE"
    
    # Log the PID for debugging
    echo "$(date): Bot started with PID $BOT_PID" >> "$LOG_FILE"

    # Wait for the bot process
    wait $BOT_PID

    EXIT_CODE=$?
    echo "$(date): Trading bot stopped with exit code $EXIT_CODE" >> "$LOG_FILE"

    # Remove PID file when bot stops
    rm -f "$PID_FILE"

    return $EXIT_CODE
}

# Check if another instance is running
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
EXISTING_BOTS=$(pgrep -f "python3.*$SCRIPT_PATH")
if [ ! -z "$EXISTING_BOTS" ]; then
    echo "Warning: Found existing bot processes: $EXISTING_BOTS"
    echo "Consider running stop.sh first"
    exit 1
fi

# Infinite loop with exponential backoff for restarts
RESTART_COUNT=0
CURRENT_DELAY=$RESTART_DELAY

while true; do
    run_bot

    # If the bot was stopped by stop.sh (exit code 0), don't restart
    if [ $? -eq 0 ]; then
        echo "$(date): Bot stopped normally" >> "$LOG_FILE"
        break
    fi

    # Increment restart counter
    RESTART_COUNT=$((RESTART_COUNT + 1))
    
    # Check if we've reached the maximum number of restarts
    if [ $RESTART_COUNT -ge $MAX_RESTARTS ]; then
        echo "$(date): Maximum restart count ($MAX_RESTARTS) reached. Giving up." >> "$LOG_FILE"
        echo "$(date): Check logs for recurring errors." >> "$LOG_FILE"
        exit 1
    fi
    
    # Exponential backoff: double the delay each time, up to 5 minutes
    CURRENT_DELAY=$((CURRENT_DELAY * 2))
    if [ $CURRENT_DELAY -gt 300 ]; then
        CURRENT_DELAY=300
    fi
    
    echo "$(date): Restarting trading bot after failure (attempt $RESTART_COUNT/$MAX_RESTARTS, waiting ${CURRENT_DELAY}s)" >> "$LOG_FILE"
    sleep $CURRENT_DELAY
done
