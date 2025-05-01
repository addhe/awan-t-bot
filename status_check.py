#!/usr/bin/env python3
"""
Script to check bot status
"""
import os
import sys
from src.utils.status_monitor import BotStatusMonitor

def main():
    # Initialize monitor
    monitor = BotStatusMonitor()

    # Get current status
    status = monitor.get_bot_status()
    trades = monitor.get_active_trades()

    if not status:
        print("❌ Bot status not found. Is the bot running?")
        sys.exit(1)

    # Print formatted status
    print(monitor.format_status_message())

if __name__ == '__main__':
    main()
