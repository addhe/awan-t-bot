#!/usr/bin/env python3
"""
Script to check bot status
"""
import sys
import os
import re
import json
import asyncio
from datetime import datetime as dt, timedelta
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.status_monitor import BotStatusMonitor
from src.exchange.connector import ExchangeConnector
from src.utils.redis_manager import RedisManager
from config.settings import EXCHANGE_CONFIG, SYSTEM_CONFIG


async def extract_confidence_from_logs(monitor):
    """Extract confidence levels from recent logs and update status"""
    # Get Redis signals first
    redis_manager = RedisManager()
    redis_confidence = {}

    if redis_manager.is_connected():
        try:
            # Get all keys matching signal:*
            signal_keys = redis_manager.redis.keys("signal:*")
            print(f"Found {len(signal_keys)} signal keys in Redis")

            # Process each signal
            for key in signal_keys:
                try:
                    # Extract symbol from key (format: signal:BTCUSDT:1h)
                    parts = key.split(":")
                    if len(parts) >= 2:
                        symbol = parts[1]
                        # Get signal data
                        signal_data = redis_manager.redis.get(key)
                        if signal_data:
                            signal_dict = json.loads(signal_data)
                            if "confidence" in signal_dict:
                                # Add to redis confidence
                                redis_confidence[symbol] = {
                                    "confidence": signal_dict.get("confidence", 0.0),
                                    "signals_detected": 1 if signal_dict.get("signal") == "buy" else 0,
                                    "timestamp": signal_dict.get("timestamp", dt.now().isoformat()),
                                    "analyzed_timeframes": signal_dict.get("timeframes", []),
                                    "calculation_method": "redis_signal"
                                }
                                print(f"Retrieved confidence for {symbol} from Redis: {redis_confidence[symbol]['confidence']:.2f}")
                except Exception as e:
                    print(f"Error processing Redis signal {key}: {e}")

            # If we have confidence data from Redis, update the monitor
            if redis_confidence:
                # Get existing confidence levels
                existing_levels = monitor.get_confidence_levels() or {}

                # Update with Redis data
                for symbol, data in redis_confidence.items():
                    existing_levels[symbol] = data

                # Update last updated timestamp
                existing_levels["last_updated"] = dt.now().isoformat()

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
        except Exception as e:
            print(f"Error retrieving confidence from Redis: {e}")

    # Now try to extract from logs
    log_file = Path("/app/logs/trading_bot.log")
    if not log_file.exists():
        # Try local path
        log_file = Path("logs/trading_bot.log")
        if not log_file.exists():
            print("❌ Log file not found")
            return

    # Read last ~1MB of log file
    try:
        with open(log_file, "r") as f:
            # Seek to end of file
            f.seek(0, 2)
            # Get file size
            file_size = f.tell()
            # Seek to max 1MB from end
            f.seek(max(0, file_size - 1024 * 1024), 0)
            # Read to end
            lines = f.readlines()

        print(f"Read {len(lines)} lines from log file (last ~1MB)")
    except Exception as e:
        print(f"❌ Error reading log file: {e}")
        return

    # Regular expressions for parsing
    confidence_pattern = re.compile(r"confidence: ([\d\.]+)")
    symbol_pattern = re.compile(r"Processing pair ([A-Z]+/[A-Z]+|[A-Z]+USDT)")

    current_symbol = None
    cutoff_time = dt.now() - timedelta(hours=8)  # Extended from 1 hour to 8 hours to capture more data
    print(f"Looking for logs since {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}")

    for line in lines:
        # Skip lines without timestamp
        if not re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", line):
            continue

        # Parse timestamp
        try:
            timestamp_str = line[:19]  # Format: 2023-01-01 12:34:56
            timestamp = dt.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

            # Skip old logs
            if timestamp < cutoff_time:
                continue
        except Exception:
            continue

        # Look for symbol
        symbol_match = symbol_pattern.search(line)
        if symbol_match:
            current_symbol = symbol_match.group(1)
            # Convert BTC/USDT format to BTCUSDT if needed
            if "/" in current_symbol:
                base, quote = current_symbol.split("/")
                current_symbol = f"{base}{quote}"

        # Look for confidence
        if current_symbol and "confidence:" in line:
            confidence_match = confidence_pattern.search(line)
            if confidence_match:
                confidence = float(confidence_match.group(1))

                # Get existing confidence levels
                existing_levels = monitor.get_confidence_levels() or {}

                # Update confidence for current symbol
                existing_levels[current_symbol] = {
                    "confidence": confidence,
                    "timestamp": timestamp.isoformat(),
                    "calculation_method": "log_extract"
                }

                # Update last updated timestamp
                existing_levels["last_updated"] = dt.now().isoformat()

                # Save to file
                monitor.update_confidence_levels(existing_levels)
                print(f"Updated confidence for {current_symbol} from logs: {confidence:.2f}")

    # Check if we found any new confidence data
    confidence_levels = monitor.get_confidence_levels()
    if not confidence_levels or len(confidence_levels) <= 1:  # 1 for last_updated key
        print("""
⚠️ No new confidence data found in logs for the specified time period.
Possible reasons:
  - No trading pairs were processed in the specified time window
  - Log format has changed
  - Bot is not logging signal analysis
Keeping previous confidence levels if available.
""")


async def update_balances_from_exchange(monitor):
    """Update balances directly from exchange"""
    try:
        # Initialize exchange connector
        exchange = ExchangeConnector(EXCHANGE_CONFIG, SYSTEM_CONFIG)

        # Get current balances from exchange
        balances = await exchange.get_all_balances()

        if balances:
            # Get current status
            current_status = monitor.get_bot_status() or {}

            # Update balance in status
            current_status["balance"] = balances

            # Save updated status
            monitor.update_bot_status(current_status)

            print(f"Updated balances for {len(balances)} assets from exchange")
            print(f"USDT Balance: {balances.get('USDT', 0)}")
            return True
        else:
            print("No balances retrieved from exchange")
            return False
    except Exception as e:
        print(f"Error updating balances from exchange: {e}")
        return False


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

    updated_trades = []
    for trade in trades:
        symbol = trade.get("symbol")
        entry_price = trade.get("entry_price", 0)

        if not symbol:
            continue

        try:
            # Extract base currency from symbol (e.g., BTCUSDT -> BTC)
            base_currency = symbol.replace("USDT", "")

            # Skip positions where the base currency balance is too low
            if base_currency and base_currency in balances:
                min_balance = 0.0001  # Minimum balance threshold
                if balances.get(base_currency, 0) < min_balance:
                    print(f"Skipping {symbol} as position appears to be closed ({base_currency} balance too low)")
                    continue

            # Try to get price from Redis first
            current_price = None

            if redis_manager.is_connected():
                try:
                    # Try to get OHLCV data from Redis
                    ohlcv_key = f"ohlcv:{symbol}:1m"
                    ohlcv_data = redis_manager.redis.get(ohlcv_key)

                    if ohlcv_data:
                        try:
                            # Parse JSON data
                            from io import StringIO
                            import pandas as pd
                            df = pd.read_json(StringIO(ohlcv_data))

                            if not df.empty:
                                # Check if data is recent (last 5 minutes)
                                last_timestamp = df.iloc[-1].name if hasattr(df.iloc[-1], 'name') else None
                                if last_timestamp and isinstance(last_timestamp, (int, float)):
                                    # Convert timestamp to datetime if it's a numeric value
                                    last_update = dt.fromtimestamp(last_timestamp / 1000)  # Convert ms to seconds
                                    now = dt.now()
                                    age_minutes = (now - last_update).total_seconds() / 60

                                    if age_minutes < 60:  # Less than 1 hour old
                                        current_price = df.iloc[-1]["close"]
                                        print(f"Using cached price for {symbol} from Redis: {current_price}")
                        except Exception as e:
                            print(f"Error parsing OHLCV data from Redis: {e}")
                except Exception as e:
                    print(f"Error getting price from Redis: {e}")

            # If we couldn't get price from Redis, fetch from exchange
            if current_price is None:
                # Always fetch from exchange first
                try:
                    ticker = await exchange.fetch_ticker(symbol)
                    if ticker and "last" in ticker:
                        current_price = ticker["last"]
                        print(f"Fetched price for {symbol} from exchange: {current_price}")
                except Exception as e:
                    print(f"Error fetching price from exchange: {e}")
                    # Try to use the last price from the trade if available
                    current_price = trade.get("current_price", entry_price)
                    print(f"Using last known price for {symbol}: {current_price}")

            # Calculate P/L
            if current_price and entry_price:
                pnl = ((current_price - entry_price) / entry_price) * 100
                pnl_formatted = f"{pnl:.2f}%"
            else:
                pnl = 0
                pnl_formatted = "0.00%"

            # Update trade with current price
            updated_trade = trade.copy()
            updated_trade["current_price"] = current_price
            updated_trade["pnl"] = pnl_formatted
            updated_trades.append(updated_trade)

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
                    "updated_at": dt.now().isoformat()
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

    # --- PATCH: Selalu update confidence level untuk semua pair sebelum tampilkan status ---
    from config.settings import TRADING_PAIRS, STRATEGY_CONFIG
    from src.strategies.boll_stoch_strategy import BollStochStrategy
    from src.exchange.connector import ExchangeConnector
    exchange = ExchangeConnector(EXCHANGE_CONFIG, SYSTEM_CONFIG)
    strategy = BollStochStrategy(**STRATEGY_CONFIG)
    confidence_data = {}
    for pair in TRADING_PAIRS:
        symbol = pair["symbol"]
        main_tf = pair.get("timeframes", ["1h"])[0]
        try:
            df = await exchange.fetch_ohlcv(symbol, main_tf)
            if df is not None and not df.empty:
                df_ind = strategy.calculate_indicators(df, symbol, main_tf)
                # Buat dictionary dengan timeframe sebagai key untuk analyze_signals
                timeframe_data = {main_tf: df_ind}
                # Gunakan analyze_signals yang tersedia di BollStochStrategy
                signal, confidence, _ = strategy.analyze_signals(timeframe_data)
                confidence_data[symbol] = {
                    "confidence": confidence,
                    "timestamp": dt.now().isoformat(),
                }
                print(f"[PATCH] Updated confidence for {symbol}: {confidence:.2f}")
            else:
                print(f"[PATCH] No OHLCV data for {symbol} {main_tf}")
        except Exception as e:
            print(f"[PATCH] Error updating confidence for {symbol}: {e}")
    if confidence_data:
        monitor.update_confidence_levels(confidence_data)
        print(f"[PATCH] Saved confidence levels for {len(confidence_data)} pairs.")
    # --- END PATCH ---

    # Extract confidence levels from logs
    await extract_confidence_from_logs(monitor)

    # Update balances from exchange
    await update_balances_from_exchange(monitor)

    # Update prices for active trades
    await update_active_trades_prices(monitor)

    # --- PATCH: Update uptime dan last_check ---
    # Hitung uptime yang benar (dari waktu start bot)
    import os
    import time

    # Coba baca waktu start bot dari file atau process
    try:
        # Coba dapatkan uptime dari proses
        bot_pid_file = "/app/bot.pid"
        if os.path.exists(bot_pid_file):
            with open(bot_pid_file, "r") as f:
                pid = f.read().strip()
                if pid.isdigit():
                    # Cek apakah proses masih berjalan
                    if os.path.exists(f"/proc/{pid}"):
                        # Baca waktu start dari stat
                        with open(f"/proc/{pid}/stat", "r") as stat_file:
                            stat = stat_file.read().split()
                            start_time_ticks = float(stat[21])
                            # Konversi ke timestamp
                            boot_time = time.time() - time.clock_gettime(time.CLOCK_MONOTONIC)
                            start_time = boot_time + (start_time_ticks / os.sysconf(os.sysconf_names['SC_CLK_TCK']))
                            # Hitung uptime dalam jam
                            uptime_hours = (time.time() - start_time) / 3600
                            print(f"[PATCH] Bot running for {uptime_hours:.2f} hours")
                            # Update status metrics
                            monitor.update_status_metrics({
                                "uptime_hours": round(uptime_hours, 2),
                                "last_updated": dt.now().isoformat(),
                            })
    except Exception as e:
        print(f"[PATCH] Error updating uptime: {e}")
        # Fallback: gunakan waktu sekarang sebagai last_updated
        monitor.update_status_metrics({
            "last_updated": dt.now().isoformat(),
        })
        print("[PATCH] Updated last_check to current time")
    # --- END PATCH ---

    # Print formatted status
    print(monitor.format_status_message())


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_main())


if __name__ == "__main__":
    main()
