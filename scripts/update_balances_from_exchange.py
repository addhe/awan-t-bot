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
        raw_balances = await exchange.get_all_balances()

        if not raw_balances:
            logger.warning("No balances retrieved from exchange")
            print("❌ No balances retrieved from exchange")
            return False

        # Convert balance format to match expected structure
        formatted_balances = {}
        for asset, balance in raw_balances.items():
            if isinstance(balance, dict):
                # New format: {'BTC': {'free': 0.1, 'used': 0.0, 'total': 0.1}}
                formatted_balances[asset] = balance.get('total', 0)
            else:
                # Old format: {'BTC': 0.1}
                formatted_balances[asset] = balance

        # Get current status
        current_status = monitor.get_bot_status() or {}

        # Update balance in status
        current_status["balance"] = formatted_balances

        # Save updated status
        monitor.update_bot_status(current_status)


        # Print summary
        total_assets = len(formatted_balances)
        print(f"\n✅ Successfully updated balances for {total_assets} assets")

        # Print important balances with emojis
        important_assets = [
            ('USDT', '💵'),
            ('BTC', '₿'),
            ('ETH', 'Ξ'),
            ('SOL', '◎'),
            ('BNB', '🅱️'),
            ('XRP', '✕'),
            ('ADA', '₳'),
            ('DOGE', 'Ð'),
            ('SOLO', '🦍')
        ]

        print("\n💼 Balances:")
        for asset, emoji in important_assets:
            if asset in formatted_balances and formatted_balances[asset] > 0:
                print(f"   {emoji} {asset}: {formatted_balances[asset]:.8f}")

        # Print total USDT value if we can calculate it
        if 'USDT' in formatted_balances:
            print(f"\n💵 Total USDT: {formatted_balances['USDT']:.2f}")

        return True

    except Exception as e:
        logger.error(f"Error updating balances from exchange: {e}", exc_info=True)
        print(f"❌ Error updating balances from exchange: {e}")
        import traceback
        traceback.print_exc()
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
