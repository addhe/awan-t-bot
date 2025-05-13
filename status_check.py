#!/usr/bin/env python3
"""
Script to check bot status
"""
import sys
import os
import re
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from src.utils.status_monitor import BotStatusMonitor
from src.exchange.connector import ExchangeConnector
from src.utils.redis_manager import RedisManager
from config.settings import EXCHANGE_CONFIG, SYSTEM_CONFIG

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


async def extract_confidence_from_logs(monitor):
    """Extract confidence levels from recent logs and update status"""
    redis_manager = RedisManager()
    
    # First, try to get confidence levels from Redis
    redis_confidence = {}
    try:
        if redis_manager.is_connected():
            # Get all keys matching the signal pattern
            signal_keys = redis_manager.redis.keys("signal:*")
            if signal_keys:
                print(f"Found {len(signal_keys)} signal keys in Redis")
                for key in signal_keys:
                    try:
                        # Get signal data
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
                                print(f"Retrieved confidence for {symbol} from Redis: {redis_confidence[symbol]['confidence']:.2f}")
                    except Exception as e:
                        print(f"Error processing Redis signal key {key}: {e}")
    except Exception as e:
        print(f"Error accessing Redis for confidence levels: {e}")
    
    # If we found confidence data in Redis, use it
    if redis_confidence:
        try:
            # Get existing confidence levels
            existing_levels = monitor.get_confidence_levels() or {}
            
            # Update with Redis data
            for symbol, data in redis_confidence.items():
                existing_levels[symbol] = data
            
            # Update last updated timestamp
            existing_levels["last_updated"] = datetime.now().isoformat()
            
            # Save to file
            monitor.update_confidence_levels(existing_levels)
            print(f"Updated confidence levels for {len(redis_confidence)} symbols from Redis")
            
            # Also save to Redis for quick access
            try:
                redis_manager.redis.set("confidence_levels", json.dumps(existing_levels))
                redis_manager.redis.expire("confidence_levels", 60 * 60 * 24)  # 1 day expiration
                print("Saved confidence levels to Redis")
            except Exception as e:
                print(f"Error saving confidence levels to Redis: {e}")
                
            return
        except Exception as e:
            print(f"⚠️ Error updating confidence levels from Redis: {e}")
    
    # If Redis doesn't have confidence data, fall back to log extraction
    print("No confidence data found in Redis, falling back to log extraction")
    
    log_file = Path("logs/trading_bot.log")
    if not log_file.exists():
        print("⚠️ Log file not found, skipping confidence extraction")
        return
    
    # Read last part of log file (to limit memory usage)
    try:
        with open(log_file, "r") as f:
            # Get file size and seek to end minus ~500KB or start of file to capture more data
            f.seek(0, 2)  # Seek to end
            file_size = f.tell()
            f.seek(max(0, file_size - 500000), 0)  # Go back ~500KB (increased from 100KB)
            lines = f.readlines()
            # Limit to last 5000 lines (increased from 1000)
            lines = lines[-5000:]
            print(f"Read {len(lines)} lines from log file (last ~500KB)")
    except Exception as e:
        print(f"⚠️ Error reading log file: {e}")
        return
    
    # Extract confidence levels using regex
    confidence_data = {}
    symbol_pattern = re.compile(r"Processing pair ([A-Z]+/[A-Z]+|[A-Z]+USDT)")
    
    current_symbol = None
    cutoff_time = datetime.now() - timedelta(hours=8)  # Extended from 1 hour to 8 hours to capture more data
    print(f"Looking for logs since {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
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
        if current_symbol and "Signal analysis complete across" in line:
            # Get the timeframe conditions from the log
            try:
                # Extract the JSON-like part containing timeframe conditions
                start_idx = line.find("'timeframe_conditions': {")
                if start_idx == -1:
                    continue
            except Exception as e:
                print(f"Error finding timeframe_conditions in line: {e}")
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
                
                # Extract 1h and 4h timeframe conditions
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
                
                # Store data
                confidence_data[current_symbol] = {
                    "confidence": confidence,
                    "signals_detected": signals_detected,
                    "timestamp": timestamp.isoformat(),
                    "conditions": timeframe_conditions,
                    "analyzed_timeframes": list(timeframe_conditions.keys()),
                    "calculation_method": "log_extraction"
                }
                
                print(f"Extracted confidence for {current_symbol}: {confidence:.2f}")
                
                # Also save to Redis for future use
                try:
                    if redis_manager.is_connected():
                        # Save as a signal
                        signal_type = "buy" if confidence >= 0.7 else "neutral"
                        redis_manager.save_signal(
                            symbol=current_symbol,
                            signal=signal_type,
                            confidence=confidence,
                            timeframes=list(timeframe_conditions.keys())
                        )
                        print(f"Saved signal to Redis for {current_symbol}")
                except Exception as e:
                    print(f"Error saving signal to Redis for {current_symbol}: {e}")
                continue
    
    # Update confidence levels in status file
    if confidence_data:
        try:
            # Get existing confidence levels
            existing_levels = monitor.get_confidence_levels() or {}
            
            # Update with new data
            for symbol, data in confidence_data.items():
                existing_levels[symbol] = data
            
            # Update last updated timestamp
            existing_levels["last_updated"] = datetime.now().isoformat()
            
            # Save to file
            monitor.update_confidence_levels(existing_levels)
            print(f"✅ Updated confidence levels for {len(confidence_data)} symbols")
            for symbol, data in confidence_data.items():
                print(f"  - {symbol}: {data['confidence']:.2f} (from log at {data['timestamp']})")
            
            # Also save to Redis for quick access
            try:
                if redis_manager.is_connected():
                    redis_manager.redis.set("confidence_levels", json.dumps(existing_levels))
                    redis_manager.redis.expire("confidence_levels", 60 * 60 * 24)  # 1 day expiration
                    print("Saved confidence levels to Redis")
            except Exception as e:
                print(f"Error saving confidence levels to Redis: {e}")
                
        except Exception as e:
            print(f"⚠️ Error updating confidence levels: {e}")
    else:
        print("⚠️ No confidence data found in logs. Possible reasons:")
        print("  - No trading pairs were processed in the time window")
        print("  - Log format has changed")
        print("  - Bot is not logging signal analysis")
        print("Keeping previous confidence levels if available.")
        
        # Try to get confidence levels from Redis
        try:
            if redis_manager.is_connected():
                redis_conf_data = redis_manager.redis.get("confidence_levels")
                if redis_conf_data:
                    redis_conf = json.loads(redis_conf_data)
                    print("\nFound confidence levels in Redis:")
                    for symbol, data in redis_conf.items():
                        if symbol != "last_updated" and isinstance(data, dict) and "confidence" in data:
                            print(f"  - {symbol}: {data['confidence']:.2f} (last updated: {data.get('timestamp', 'unknown')})")
                    return
        except Exception as e:
            print(f"Error getting confidence levels from Redis: {e}")
        
        # Try to display current confidence levels from file
        current_levels = monitor.get_confidence_levels()
        if current_levels and any(k != "last_updated" for k in current_levels.keys()):
            print("\nCurrent confidence levels in status file:")
            for symbol, data in current_levels.items():
                if symbol != "last_updated" and isinstance(data, dict) and "confidence" in data:
                    print(f"  - {symbol}: {data['confidence']:.2f} (last updated: {data.get('timestamp', 'unknown')})")
        else:
            print("No existing confidence levels found in status file.")

async def update_active_trades_prices(monitor):
    """Update prices for active trades before showing status"""
    # Initialize exchange connector and Redis manager
    exchange = ExchangeConnector(EXCHANGE_CONFIG, SYSTEM_CONFIG)
    redis_manager = RedisManager()

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

            # Try to get current price from Redis first
            current_price = None
            try:
                # Get the most recent OHLCV data from Redis
                for timeframe in ['1m', '5m', '15m', '1h']:
                    df = redis_manager.get_ohlcv(symbol, timeframe)
                    if df is not None and not df.empty:
                        current_price = df.iloc[-1]['close']
                        print(f"Using cached price for {symbol} from Redis ({timeframe}): {current_price}")
                        break
            except Exception as e:
                print(f"Error getting price from Redis for {symbol}: {e}")

            # If not found in Redis, fetch from exchange
            if current_price is None:
                current_price = await exchange.get_current_price(symbol)
                print(f"Fetched price for {symbol} from exchange: {current_price}")

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

            # Also save the trade info to Redis for quick access
            try:
                redis_key = f"active_trade:{symbol}"
                # Use hset instead of deprecated hmset
                redis_manager.redis.hset(redis_key, mapping={
                    "symbol": symbol,
                    "entry_price": str(entry_price),
                    "current_price": str(current_price),
                    "quantity": str(trade["quantity"]),
                    "pnl": str(pnl),
                    "updated_at": datetime.now().isoformat()
                })
                # Set expiration to 1 day
                redis_manager.redis.expire(redis_key, 60 * 60 * 24)
            except Exception as e:
                print(f"Error saving trade to Redis for {symbol}: {e}")
                
        except Exception as e:
            print(f"Error updating {symbol} price: {e}")
            # Don't keep trades with errors - they might be closed

    # Update trades file with fresh prices
    if updated_trades:
        monitor.update_trades(updated_trades)
        
        # Also save all active trades to Redis
        try:
            redis_manager.redis.set("active_trades", json.dumps(updated_trades))
            redis_manager.redis.expire("active_trades", 60 * 60 * 24)  # 1 day expiration
            print(f"Saved {len(updated_trades)} active trades to Redis")
        except Exception as e:
            print(f"Error saving active trades to Redis: {e}")
            
    elif trades:  # If we had trades but now have none, clear the file
        print("All positions appear to be closed. Clearing active trades.")
        monitor.update_trades([])
        
        # Also clear Redis
        try:
            redis_manager.redis.delete("active_trades")
            for trade in trades:
                redis_manager.redis.delete(f"active_trade:{trade['symbol']}")
            print("Cleared active trades from Redis")
        except Exception as e:
            print(f"Error clearing active trades from Redis: {e}")


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
