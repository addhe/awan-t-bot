#!/usr/bin/env python3
"""
Script to check bot status
"""
import sys
import os
import asyncio
from src.utils.status_monitor import BotStatusMonitor
from src.exchange.connector import ExchangeConnector
from config.settings import EXCHANGE_CONFIG, SYSTEM_CONFIG

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


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

    # Update prices for active trades
    await update_active_trades_prices(monitor)

    # Print formatted status
    print(monitor.format_status_message())


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_main())


if __name__ == "__main__":
    main()
