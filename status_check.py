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

    # Update current prices
    updated_trades = []
    for trade in trades:
        symbol = trade['symbol']
        try:
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
            updated_trades.append(trade)  # Keep original trade data

    # Update trades file with fresh prices
    if updated_trades:
        monitor.update_trades(updated_trades)


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
