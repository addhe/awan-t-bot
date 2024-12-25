#!/bin/bash

# Define the path to your Python script
SCRIPT_PATH="/root/awan-t-bot/main.py"

# Define logging file
LOG_FILE="trading_bot.log"

# Function to run the bot with logging
run_bot() {
  echo "$(date): Starting trading bot" >> $LOG_FILE
  python3 "$SCRIPT_PATH"
  EXIT_CODE=$?
  echo "$(date): Trading bot stopped with exit code $EXIT_CODE" >> $LOG_FILE
}

# Infinite loop to keep the bot running in case of script failure
while true; do
  run_bot
  # Add a sleep to wait for a few seconds before restart, this avoids immediate restart on failure.
  echo "$(date): Restarting trading bot after failure" >> $LOG_FILE
  sleep 10
done