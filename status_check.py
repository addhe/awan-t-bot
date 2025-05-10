#!/usr/bin/env python3
"""
Script to check bot status
"""
import sys
import os
import re
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from src.utils.status_monitor import BotStatusMonitor
from src.exchange.connector import ExchangeConnector
from config.settings import EXCHANGE_CONFIG, SYSTEM_CONFIG

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


async def extract_confidence_from_logs(monitor):
    """Extract confidence levels from recent logs and update status"""
    log_file = Path("logs/trading_bot.log")
    if not log_file.exists():
        print("⚠️ Log file not found, skipping confidence extraction")
        return
    
    # Read last 1000 lines from log file (to limit memory usage)
    try:
        with open(log_file, "r") as f:
            # Get file size and seek to end minus ~100KB or start of file
            f.seek(0, 2)  # Seek to end
            file_size = f.tell()
            f.seek(max(0, file_size - 100000), 0)  # Go back ~100KB
            lines = f.readlines()
            # Limit to last 1000 lines
            lines = lines[-1000:]
    except Exception as e:
        print(f"⚠️ Error reading log file: {e}")
        return
    
    # Extract confidence levels using regex
    confidence_data = {}
    signal_pattern = re.compile(r"Signal analysis complete across \d+ timeframes.*Context: \{.*?'signals_detected': (\d+).*?'timeframe_conditions': \{(.*?)\}\}")
    symbol_pattern = re.compile(r"Processing pair ([A-Z]+/[A-Z]+|[A-Z]+USDT)")
    
    current_symbol = None
    cutoff_time = datetime.now() - timedelta(hours=1)  # Only consider logs from last hour
    
    for line in lines:
        # Extract timestamp
        try:
            timestamp_str = line.split(" - ")[0].strip()
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
            if timestamp < cutoff_time:
                continue
        except Exception:
            continue
        
        # Extract symbol being processed
        symbol_match = symbol_pattern.search(line)
        if symbol_match:
            current_symbol = symbol_match.group(1)
            continue
        
        # Extract signal analysis data
        if current_symbol and "Signal analysis complete" in line:
            signal_match = signal_pattern.search(line)
            if signal_match:
                signals_detected = int(signal_match.group(1))
                timeframe_data = signal_match.group(2)
                
                # Calculate confidence based on conditions
                confidence = 0.0
                
                # Simple heuristic: check how many conditions are met in the timeframes
                conditions_met = 0
                total_conditions = 0
                
                for tf in ['1h', '4h']:
                    if tf in timeframe_data:
                        # Count positive conditions
                        if f"'is_oversold': True" in timeframe_data:
                            conditions_met += 1
                        if f"'price_above_ema': True" in timeframe_data:
                            conditions_met += 1
                        if f"'stoch_crossover': True" in timeframe_data:
                            conditions_met += 1
                        total_conditions += 3
                
                if total_conditions > 0:
                    confidence = conditions_met / total_conditions
                    
                    # Store the confidence level
                    confidence_data[current_symbol] = {
                        "confidence": confidence,
                        "timestamp": timestamp.isoformat(),
                        "signals_detected": signals_detected
                    }
    
    # Update confidence levels in status file
    if confidence_data:
        try:
            monitor.update_confidence_levels(confidence_data)
            print(f"✅ Updated confidence levels for {len(confidence_data)} symbols")
        except Exception as e:
            print(f"⚠️ Error updating confidence levels: {e}")

async def update_active_trades_prices(monitor):
    """Update prices for active trades before showing status"""
    # Initialize exchange connector
    exchange = ExchangeConnector(EXCHANGE_CONFIG, SYSTEM_CONFIG)

    # Get active trades
    trades = monitor.get_active_trades()
    if not trades:
        return

    # Get current balances to check if positions still exist
    balances = await exchange.get_all_balances()

    # Update current prices
    updated_trades = []
    for trade in trades:
        symbol = trade['symbol']
        try:
            # Check if this is a crypto position that's been closed
            # Extract the base currency from the symbol (e.g., 'ETH' from 'ETHUSDT')
            base_currency = None
            if symbol.endswith('USDT'):
                base_currency = symbol[:-4]  # Remove 'USDT'
            elif '/' in symbol:
                base_currency = symbol.split('/')[0]  # Split at '/' and take first part
            
            # Skip positions where the base currency balance is too low
            if base_currency and base_currency in balances:
                min_balance = 0.0001  # Minimum balance threshold
                if balances.get(base_currency, 0) < min_balance:
                    print(f"Skipping {symbol} as position appears to be closed ({base_currency} balance too low)")
                    continue

            current_price = await exchange.get_current_price(symbol)
            entry_price = trade["entry_price"]
            pnl = 0.0
            if entry_price != 0:
                pnl = ((current_price - entry_price) / entry_price) * 100

            updated_trades.append({
                "symbol": symbol,
                "entry_price": entry_price,
                "current_price": current_price,
                "quantity": trade["quantity"],
                "pnl": pnl,
            })
            print(f"Updated {symbol} price: {current_price}")
        except Exception as e:
            print(f"Error updating {symbol} price: {e}")
            # Don't keep trades with errors - they might be closed

    # Update trades file with fresh prices
    if updated_trades:
        monitor.update_trades(updated_trades)
    elif trades:  # If we had trades but now have none, clear the file
        print("All positions appear to be closed. Clearing active trades.")
        monitor.update_trades([])


async def async_main():
    # Initialize monitor
    monitor = BotStatusMonitor()

    # Get current status
    status = monitor.get_bot_status()

    if not status:
        print("❌ Bot status not found. Is the bot running?")
        sys.exit(1)

    # Extract confidence levels from logs
    await extract_confidence_from_logs(monitor)
    
    # Update prices for active trades
    await update_active_trades_prices(monitor)

    # Print formatted status
    print(monitor.format_status_message())


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_main())


if __name__ == "__main__":
    main()
