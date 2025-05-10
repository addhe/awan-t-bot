#!/usr/bin/env python3
"""
Script to check current confidence levels for all trading pairs
"""
import sys
import os
import re
import asyncio
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from tabulate import tabulate

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.utils.status_monitor import BotStatusMonitor
from src.exchange.connector import ExchangeConnector
from config.settings import EXCHANGE_CONFIG, SYSTEM_CONFIG, STRATEGY_CONFIG


async def get_current_market_conditions(symbol):
    """Get current market conditions for a symbol"""
    exchange = ExchangeConnector(EXCHANGE_CONFIG, SYSTEM_CONFIG)
    
    # Get current price
    current_price = await exchange.get_current_price(symbol)
    
    # Get OHLCV data for different timeframes
    timeframes = ["15m", "1h", "4h", "1d"]
    timeframe_data = {}
    
    for tf in timeframes:
        try:
            df = await exchange.fetch_ohlcv(symbol, timeframe=tf, limit=30)
            if not df.empty:
                # Calculate basic metrics
                latest = df.iloc[-1]
                prev = df.iloc[-2]
                change_pct = ((latest["close"] - prev["close"]) / prev["close"]) * 100
                
                timeframe_data[tf] = {
                    "price": latest["close"],
                    "change_pct": change_pct,
                    "volume": latest["volume"],
                }
        except Exception as e:
            print(f"Error fetching {tf} data for {symbol}: {e}")
    
    return {
        "symbol": symbol,
        "current_price": current_price,
        "timeframes": timeframe_data
    }


async def analyze_confidence_from_logs(hours=1, detailed=False):
    """Analyze confidence levels from log files"""
    log_file = Path("logs/trading_bot.log")
    if not log_file.exists():
        print("⚠️ Log file not found")
        return {}
    
    # Read last part of log file
    try:
        with open(log_file, "r") as f:
            # Get file size and seek to end minus ~500KB or start of file
            f.seek(0, 2)  # Seek to end
            file_size = f.tell()
            f.seek(max(0, file_size - 500000), 0)  # Go back ~500KB
            content = f.read()
            lines = content.split('\n')
            # Limit to last 5000 lines
            lines = lines[-5000:]
    except Exception as e:
        print(f"⚠️ Error reading log file: {e}")
        return {}
    
    # Extract confidence levels using regex
    confidence_data = {}
    symbol_pattern = re.compile(r"Processing pair ([A-Z]+/[A-Z]+|[A-Z]+USDT)")
    
    current_symbol = None
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    # Process lines in reverse to get most recent data first
    for i, line in enumerate(lines):
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
        if current_symbol and "Signal analysis complete across" in line:
            # Get the timeframe conditions from the log
            try:
                # Extract the JSON-like part containing timeframe conditions
                start_idx = line.find("'timeframe_conditions': {")
                if start_idx == -1:
                    continue
                    
                # Find the matching closing brace
                brace_count = 0
                end_idx = -1
                for j in range(start_idx, len(line)):
                    if line[j] == '{':
                        brace_count += 1
                    elif line[j] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = j + 1
                            break
                
                if end_idx == -1:
                    continue
                    
                # Extract the timeframe conditions part
                timeframe_part = line[start_idx:end_idx]
                
                # Extract signals detected
                signals_detected = 0
                signals_match = re.search(r"'signals_detected': (\d+)", line)
                if signals_match:
                    signals_detected = int(signals_match.group(1))
                
                # Extract conditions for each timeframe
                timeframe_conditions = {}
                
                # Extract 1h timeframe conditions
                for tf in ['1h', '4h']:
                    tf_pattern = f"'{tf}': \{{(.*?)\}}"
                    tf_match = re.search(tf_pattern, timeframe_part)
                    if tf_match:
                        tf_data = tf_match.group(1)
                        conditions = {}
                        
                        # Extract boolean conditions
                        for condition in ['is_oversold', 'is_overbought', 'stoch_crossover', 
                                         'stoch_crossunder', 'price_below_bb_lower', 'price_above_bb_upper',
                                         'price_above_ema', 'price_below_ema']:
                            cond_pattern = f"'{condition}': np\.([A-Za-z_]+)"
                            cond_match = re.search(cond_pattern, tf_data)
                            if cond_match:
                                conditions[condition] = cond_match.group(1) == 'True_'
                        
                        # Extract numeric values
                        for value in ['price', 'bb_upper', 'bb_lower', 'ema', 'stoch_k', 'stoch_d']:
                            val_pattern = f"'{value}': np\.float64\(([\d\.]+)\)"
                            val_match = re.search(val_pattern, tf_data)
                            if val_match:
                                conditions[value] = float(val_match.group(1))
                        
                        timeframe_conditions[tf] = conditions
                
                # Calculate confidence based on buy conditions
                conditions_met = 0
                total_conditions = 0
                
                # Check conditions for each timeframe
                for tf, conditions in timeframe_conditions.items():
                    # Buy conditions from strategy
                    if conditions.get('is_oversold', False):
                        conditions_met += 1
                    if conditions.get('price_above_ema', False):
                        conditions_met += 1
                    if conditions.get('stoch_crossover', False):
                        conditions_met += 1
                    if conditions.get('price_below_bb_lower', False):
                        conditions_met += 1
                    total_conditions += 4
                
                # Calculate confidence
                confidence = 0.0
                if total_conditions > 0:
                    confidence = conditions_met / total_conditions
                
                # Store the confidence level
                if current_symbol not in confidence_data or timestamp > datetime.fromisoformat(confidence_data[current_symbol]["timestamp"]):
                    confidence_data[current_symbol] = {
                        "confidence": confidence,
                        "timestamp": timestamp.isoformat(),
                        "signals_detected": signals_detected,
                        "conditions": timeframe_conditions if detailed else None,
                        "calculation_method": "confidence_check",
                        "analyzed_timeframes": list(timeframe_conditions.keys())
                    }
            except Exception as e:
                print(f"⚠️ Error parsing conditions for {current_symbol}: {e}")
                continue
    
    return confidence_data


async def display_confidence_levels(hours=1, detailed=False, update_status=True):
    """Display confidence levels for all trading pairs"""
    monitor = BotStatusMonitor()
    
    # Get stored confidence levels
    stored_confidence = monitor.get_confidence_levels()
    
    # Get fresh confidence levels from logs
    log_confidence = await analyze_confidence_from_logs(hours, detailed)
    
    # Update status file if requested
    if update_status and log_confidence:
        try:
            monitor.update_confidence_levels(log_confidence)
            print(f"✅ Updated confidence levels for {len(log_confidence)} symbols")
        except Exception as e:
            print(f"⚠️ Error updating confidence levels: {e}")
    
    # Combine stored and log confidence data, preferring newer data
    all_confidence = {}
    
    # Add stored confidence first
    for symbol, data in stored_confidence.items():
        if symbol != "last_updated" and isinstance(data, dict):
            all_confidence[symbol] = data
    
    # Add/update with log confidence
    for symbol, data in log_confidence.items():
        all_confidence[symbol] = data
    
    # Get trading pairs from config
    trading_pairs = STRATEGY_CONFIG.get("trading_pairs", [])
    
    # Get current market conditions for each pair
    market_data = {}
    for symbol in trading_pairs:
        try:
            market_data[symbol] = await get_current_market_conditions(symbol)
        except Exception as e:
            print(f"Error getting market data for {symbol}: {e}")
    
    # Prepare data for display
    table_data = []
    for symbol in sorted(all_confidence.keys()):
        data = all_confidence[symbol]
        confidence = data.get("confidence", 0)
        timestamp = data.get("timestamp", "Unknown")
        signals = data.get("signals_detected", 0)
        calculation_method = data.get("calculation_method", "Unknown")
        analyzed_timeframes = data.get("analyzed_timeframes", [])
        
        # Format timestamp
        try:
            dt = datetime.fromisoformat(timestamp)
            formatted_time = dt.strftime("%H:%M:%S")
            formatted_date = dt.strftime("%Y-%m-%d")
            age = datetime.now() - dt
            age_str = f"{int(age.total_seconds() / 60)}m ago"
        except:
            formatted_time = "Unknown"
            formatted_date = "Unknown"
            age_str = "Unknown"
        
        # Get market data if available
        price = "N/A"
        if symbol in market_data:
            price = market_data[symbol].get("current_price", "N/A")
        
        # Add row to table
        table_data.append([
            symbol,
            f"{confidence:.2f}",
            signals,
            f"{formatted_date} {formatted_time}",
            age_str,
            price,
            ", ".join(analyzed_timeframes)
        ])
    
    # Display table
    if table_data:
        headers = ["Symbol", "Confidence", "Signals", "Timestamp", "Age", "Current Price", "Timeframes"]
        print("\n🎯 Confidence Levels Report\n")
        print(tabulate(table_data, headers=headers, tablefmt="pretty"))
        print(f"\nAnalyzed logs from the past {hours} hour(s)")
        
        # Min confidence threshold from config
        min_confidence = STRATEGY_CONFIG.get("min_confidence", 0.7)
        print(f"\nBot trading threshold: {min_confidence:.2f}")
        
        # Show detailed conditions if requested
        if detailed:
            print("\n📊 Detailed Conditions:\n")
            for symbol in sorted(log_confidence.keys()):
                data = log_confidence[symbol]
                conditions = data.get("conditions", {})
                if conditions:
                    print(f"\n{symbol}:")
                    for tf, tf_conditions in conditions.items():
                        print(f"  {tf}: {tf_conditions}")
    else:
        print("\n⚠️ No confidence data found in logs")
        
    # Show active trades
    active_trades = monitor.get_active_trades()
    if active_trades:
        print("\n📊 Active Trades:")
        for trade in active_trades:
            print(f"  {trade['symbol']}: Entry {trade['entry_price']}, Current {trade.get('current_price', 'N/A')}")
    else:
        print("\n📊 No active trades")


async def async_main():
    """Main async function"""
    parser = argparse.ArgumentParser(description="Check trading bot confidence levels")
    parser.add_argument("-t", "--time", type=int, default=1, help="Hours of logs to analyze (default: 1)")
    parser.add_argument("-d", "--detailed", action="store_true", help="Show detailed conditions")
    parser.add_argument("-n", "--no-update", action="store_true", help="Don't update status file")
    args = parser.parse_args()
    
    await display_confidence_levels(hours=args.time, detailed=args.detailed, update_status=not args.no_update)


def main():
    """Main entry point"""
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_main())


if __name__ == "__main__":
    main()
