#!/usr/bin/env python
"""
Utility script to sell a specific asset on Binance
Usage: python scripts/sell_asset.py SYMBOL [--amount AMOUNT] [--all]
Example: python scripts/sell_asset.py SOLO --all
         python scripts/sell_asset.py SOLO --amount 1.5
"""

import os
import sys
import asyncio
import argparse
from decimal import Decimal
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.exchange.connector import ExchangeConnector
from src.utils.structured_logger import get_logger
from config.settings import EXCHANGE_CONFIG, SYSTEM_CONFIG

logger = get_logger("sell_asset")

async def get_current_price(exchange, symbol):
    """Get current price for a symbol"""
    try:
        # Use fetch_ticker method which is available in ExchangeConnector
        ticker = await exchange.fetch_ticker(f"{symbol}USDT")
        if ticker and 'last' in ticker:
            return Decimal(str(ticker['last']))
        return Decimal('0')
    except Exception as e:
        logger.error(f"Error getting price for {symbol}USDT: {e}")
        return Decimal('0')

async def get_balance(exchange, asset):
    """Get balance for a specific asset"""
    try:
        balances = await exchange.get_all_balances()
        return Decimal(str(balances.get(asset, '0')))
    except Exception as e:
        logger.error(f"Error getting balance for {asset}: {e}")
        return Decimal('0')

async def sell_asset(symbol, amount=None, sell_all=False):
    """Sell a specific asset"""
    # Initialize exchange connector with correct parameters
    exchange = ExchangeConnector(
        exchange_config=EXCHANGE_CONFIG,
        system_config=SYSTEM_CONFIG
    )
    
    # ExchangeConnector doesn't have a connect() method, it's initialized automatically
    
    # Get balance
    balance = await get_balance(exchange, symbol)
    
    if balance == 0:
        logger.error(f"No {symbol} balance found")
        return
    
    logger.info(f"Current {symbol} balance: {balance}")
    
    # Determine amount to sell
    sell_amount = balance if sell_all else (amount if amount is not None else balance)
    
    # Get current price
    market_symbol = f"{symbol}USDT"
    current_price = await get_current_price(exchange, symbol)
    
    if current_price == 0:
        logger.error(f"Could not get current price for {market_symbol}")
        return
    
    logger.info(f"Current price for {market_symbol}: {current_price} USDT")
    
    # Calculate total value
    total_value = sell_amount * current_price
    logger.info(f"Selling {sell_amount} {symbol} (approx. {total_value} USDT)")
    
    # Confirm with user
    confirm = input(f"Are you sure you want to sell {sell_amount} {symbol} for approximately {total_value} USDT? (y/n): ")
    
    if confirm.lower() != 'y':
        logger.info("Sell operation cancelled by user")
        return
    
    # Execute sell order
    try:
        # Use place_market_sell method which is available in ExchangeConnector
        order = await exchange.place_market_sell(
            symbol=market_symbol,
            quantity=float(sell_amount)
        )
        
        logger.info(f"Sell order executed successfully: {order}")
        logger.info(f"Sold {sell_amount} {symbol} at approximately {current_price} USDT")
        
        # Get updated balance
        new_balance = await get_balance(exchange, symbol)
        logger.info(f"New {symbol} balance: {new_balance}")
        
    except Exception as e:
        logger.error(f"Error executing sell order: {e}")

def main():
    parser = argparse.ArgumentParser(description='Sell a specific asset on Binance')
    parser.add_argument('symbol', type=str, help='Symbol to sell (without USDT)')
    parser.add_argument('--amount', type=float, help='Amount to sell')
    parser.add_argument('--all', action='store_true', help='Sell all available balance')
    
    args = parser.parse_args()
    
    if not args.amount and not args.all:
        print("Error: Either --amount or --all must be specified")
        parser.print_help()
        return
    
    asyncio.run(sell_asset(args.symbol, args.amount, args.all))

if __name__ == "__main__":
    main()
