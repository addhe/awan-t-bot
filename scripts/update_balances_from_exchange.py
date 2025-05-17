#!/usr/bin/env python3
"""
Script to update balances directly from exchange
"""
import sys
import asyncio
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.exchange.connector import ExchangeConnector
from src.utils.status_monitor import BotStatusMonitor
from src.utils.structured_logger import get_logger
from config.settings import EXCHANGE_CONFIG, SYSTEM_CONFIG

logger = get_logger("update_balances")

async def update_balances_from_exchange():
    """Update balances directly from exchange"""
    try:
        # Initialize components
        exchange = ExchangeConnector(EXCHANGE_CONFIG, SYSTEM_CONFIG)
        monitor = BotStatusMonitor()

        # Get current balances from exchange
        balances = await exchange.get_all_balances()

        if balances:
            # Get current status
            current_status = monitor.get_bot_status() or {}

            # Update balance in status
            current_status["balance"] = balances

            # Save updated status
            monitor.update_bot_status(current_status)

            # Print balances
            print(f"Updated balances for {len(balances)} assets from exchange")

            # Print important balances
            important_assets = ["USDT", "BTC", "ETH", "SOLO"]
            for asset in important_assets:
                if asset in balances:
                    print(f"{asset} Balance: {balances.get(asset, 0)}")

            return True
        else:
            logger.warning("No balances retrieved from exchange")
            print("No balances retrieved from exchange")
            return False
    except Exception as e:
        logger.error(f"Error updating balances from exchange: {e}", exc_info=True)
        print(f"Error updating balances from exchange: {e}")
        return False

def main():
    """Main function"""
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(update_balances_from_exchange())
    if result:
        print("✅ Balances updated successfully")
    else:
        print("❌ Failed to update balances")

if __name__ == "__main__":
    main()
