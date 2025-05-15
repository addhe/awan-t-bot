#!/usr/bin/env python3
"""
Script to check current confidence levels for all trading pairs
"""
import sys
import os
import re
import asyncio
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from tabulate import tabulate

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.utils.status_monitor import BotStatusMonitor
from src.exchange.connector import ExchangeConnector
from src.utils.redis_manager import RedisManager
from config.settings import EXCHANGE_CONFIG, SYSTEM_CONFIG, STRATEGY_CONFIG


async def get_current_market_conditions(symbol):
    """Get current market conditions for a symbol"""
    exchange = ExchangeConnector(EXCHANGE_CONFIG, SYSTEM_CONFIG)
    redis_manager = RedisManager()
    
    # Get current price
    current_price = await exchange.get_current_price(symbol)
    
    # Get OHLCV data for different timeframes
    timeframes = ["15m", "1h", "4h", "1d"]
    timeframe_data = {}
    
    for tf in timeframes:
        try:
            # Try to get data from Redis first
            df = redis_manager.get_ohlcv(symbol, tf)
            
            # If not in Redis, fetch from exchange
            if df is None or df.empty:
                print(f"Data for {symbol} {tf} not found in Redis, fetching from exchange...")
                df = await exchange.fetch_ohlcv(symbol, timeframe=tf, limit=30)
            else:
                print(f"Using cached data for {symbol} {tf} from Redis")
                
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
    
    # Try to get indicators from Redis
    indicators = {}
    for tf in timeframes:
        try:
            tf_indicators = redis_manager.get_indicators(symbol, tf)
            if tf_indicators is not None:
                print(f"Using cached indicators for {symbol} {tf} from Redis")
                indicators[tf] = tf_indicators
        except Exception as e:
            print(f"Error fetching indicators for {symbol} {tf} from Redis: {e}")
    
    return {
        "symbol": symbol,
        "current_price": current_price,
        "timeframes": timeframe_data,
        "indicators": indicators
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
            # Get file size and seek to end minus ~1MB or start of file
            f.seek(0, 2)  # Seek to end
            file_size = f.tell()
            f.seek(max(0, file_size - 1000000), 0)  # Go back ~1MB (increased from 500KB)
            content = f.read()
            lines = content.split('\n')
            # Limit to last 10000 lines (increased from 5000)
            lines = lines[-10000:]
            print(f"Read {len(lines)} lines from log file (last ~1MB)")
    except Exception as e:
        print(f"⚠️ Error reading log file: {e}")
        return {}
    
    # Extract confidence levels using regex
    confidence_data = {}
    symbol_pattern = re.compile(r"Processing pair ([A-Z]+/[A-Z]+|[A-Z]+USDT)")
    
    current_symbol = None
    cutoff_time = datetime.now() - timedelta(hours=hours)
    print(f"Looking for logs since {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
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
    redis_manager = RedisManager()
    
    # Try to get confidence levels from Redis first
    redis_confidence = {}
    redis_data_found = False
    
    if redis_manager.is_connected():
        try:
            # Try to get confidence levels from Redis
            redis_conf_data = redis_manager.redis.get("confidence_levels")
            if redis_conf_data:
                redis_conf = json.loads(redis_conf_data)
                print(f"Retrieved confidence levels from Redis cache")
                for symbol, data in redis_conf.items():
                    if symbol != "last_updated" and isinstance(data, dict):
                        redis_confidence[symbol] = data
                        redis_data_found = True
            
            # If not found in confidence_levels, try to get from signal data
            if not redis_data_found:
                signal_keys = redis_manager.redis.keys("signal:*")
                if signal_keys:
                    print(f"Found {len(signal_keys)} signal keys in Redis")
                    for key in signal_keys:
                        try:
                            signal_data = redis_manager.redis.get(key)
                            if signal_data:
                                signal_dict = json.loads(signal_data)
                                symbol = signal_dict.get("symbol")
                                if symbol:
                                    redis_confidence[symbol] = {
                                        "confidence": signal_dict.get("confidence", 0.0),
                                        "signals_detected": 1 if signal_dict.get("signal") == "buy" else 0,
                                        "timestamp": signal_dict.get("timestamp", datetime.now().isoformat()),
                                        "analyzed_timeframes": signal_dict.get("timeframes", []),
                                        "calculation_method": "redis_signal"
                                    }
                                    redis_data_found = True
                        except Exception as e:
                            print(f"Error processing Redis signal key {key}: {e}")
        except Exception as e:
            print(f"Error retrieving confidence data from Redis: {e}")
    
    # Get stored confidence levels from file
    stored_confidence = monitor.get_confidence_levels() or {}
    
    # Get fresh confidence levels from logs
    log_confidence = await analyze_confidence_from_logs(hours, detailed)
    
    # Update status file and Redis if requested
    if update_status and log_confidence:
        try:
            # Update status file
            monitor.update_confidence_levels(log_confidence)
            print(f"✅ Updated confidence levels in status file for {len(log_confidence)} symbols")
            
            # Also update Redis
            if redis_manager.is_connected():
                # Combine with existing data
                combined_confidence = stored_confidence.copy()
                for symbol, data in log_confidence.items():
                    combined_confidence[symbol] = data
                combined_confidence["last_updated"] = datetime.now().isoformat()
                
                # Save to Redis
                redis_manager.redis.set("confidence_levels", json.dumps(combined_confidence))
                redis_manager.redis.expire("confidence_levels", 60 * 60 * 24)  # 1 day expiration
                print(f"Updated confidence levels in Redis for {len(log_confidence)} symbols")
                
                # Also save as individual signals
                for symbol, data in log_confidence.items():
                    confidence = data.get("confidence", 0.0)
                    timeframes = data.get("analyzed_timeframes", [])
                    signal_type = "buy" if confidence >= STRATEGY_CONFIG.get("min_confidence", 0.7) else "neutral"
                    redis_manager.save_signal(
                        symbol=symbol,
                        signal=signal_type,
                        confidence=confidence,
                        timeframes=timeframes
                    )
                    print(f"Saved signal to Redis for {symbol}")
            
            for symbol, data in log_confidence.items():
                print(f"  - {symbol}: {data['confidence']:.2f} (from log at {data['timestamp']})")
        except Exception as e:
            print(f"⚠️ Error updating confidence levels: {e}")
    elif update_status:
        print("\n⚠️ No new confidence data found in logs for the specified time period.")
        print("Possible reasons:")
        print("  - No trading pairs were processed in the specified time window")
        print("  - Log format has changed")
        print("  - Bot is not logging signal analysis")
        print("Keeping previous confidence levels if available.")
        
        # Display confidence levels from Redis or file
        if redis_data_found:
            print("\nCurrent confidence levels from Redis:")
            for symbol, data in redis_confidence.items():
                if isinstance(data, dict) and "confidence" in data:
                    try:
                        timestamp = datetime.fromisoformat(data.get('timestamp', '2025-01-01T00:00:00'))
                        age = datetime.now() - timestamp
                        age_str = f"{int(age.total_seconds() / 3600)}h {int((age.total_seconds() % 3600) / 60)}m ago"
                        print(f"  - {symbol}: {data['confidence']:.2f} (last updated: {timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {age_str})")
                    except:
                        print(f"  - {symbol}: {data['confidence']:.2f} (last updated: unknown)")
        elif any(k != "last_updated" for k in stored_confidence.keys()):
            print("\nCurrent confidence levels from status file:")
            for symbol, data in stored_confidence.items():
                if symbol != "last_updated" and isinstance(data, dict) and "confidence" in data:
                    try:
                        timestamp = datetime.fromisoformat(data.get('timestamp', '2025-01-01T00:00:00'))
                        age = datetime.now() - timestamp
                        age_str = f"{int(age.total_seconds() / 3600)}h {int((age.total_seconds() % 3600) / 60)}m ago"
                        print(f"  - {symbol}: {data['confidence']:.2f} (last updated: {timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {age_str})")
                    except:
                        print(f"  - {symbol}: {data['confidence']:.2f} (last updated: unknown)")
        else:
            print("No existing confidence levels found in status file or Redis.")
    
    # Combine all confidence data, preferring newer data
    all_confidence = {}
    
    # Add Redis confidence first (if available)
    for symbol, data in redis_confidence.items():
        all_confidence[symbol] = data
    
    # Add stored confidence from file (if not already in Redis)
    for symbol, data in stored_confidence.items():
        if symbol != "last_updated" and isinstance(data, dict) and symbol not in all_confidence:
            all_confidence[symbol] = data
    
    # Add/update with log confidence (newest data)
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
