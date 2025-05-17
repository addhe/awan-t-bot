#!/usr/bin/env python
"""
Utility script to sell a specific asset on Binance
Usage: python src/utils/sell_asset.py SYMBOL [--amount AMOUNT] [--all]
Example: python src/utils/sell_asset.py SOLO --all
         python src/utils/sell_asset.py SOLO --amount 1.5
"""

import os
import sys
import asyncio
import argparse
from decimal import Decimal
from pathlib import Path

from src.exchange.connector import ExchangeConnector
from src.utils.structured_logger import get_logger
from config.settings import EXCHANGE_CONFIG

logger = get_logger("sell_asset")

async def get_ticker_info(exchange, symbol):
    """Get ticker information for a symbol"""
    try:
        ticker = await exchange.get_ticker(f"{symbol}USDT")
        return ticker
    except Exception as e:
        logger.error(f"Error getting ticker for {symbol}USDT: {e}")
        return None

async def get_balance(exchange, asset):
    """Get balance for a specific asset"""
    try:
        balances = await exchange.get_all_balances()
        return Decimal(balances.get(asset, '0'))
    except Exception as e:
        logger.error(f"Error getting balance for {asset}: {e}")
        return Decimal('0')

async def sell_asset(symbol, amount=None, sell_all=False):
    """Sell a specific asset"""
    # Initialize exchange connector
    exchange = ExchangeConnector(
        exchange_name=EXCHANGE_CONFIG["name"],
        api_key=EXCHANGE_CONFIG["api_key"],
        api_secret=EXCHANGE_CONFIG["api_secret"],
        testnet=EXCHANGE_CONFIG["testnet"]
    )
    
    # Connect to exchange
    await exchange.connect()
    
    # Get balance
    balance = await get_balance(exchange, symbol)
    
    if balance == 0:
        logger.error(f"No {symbol} balance found")
        return
    
    logger.info(f"Current {symbol} balance: {balance}")
    
    # Determine amount to sell
    sell_amount = balance if sell_all else (amount if amount is not None else balance)
    
    # Get ticker info
    market_symbol = f"{symbol}USDT"
    ticker = await get_ticker_info(exchange, symbol)
    
    if not ticker:
        logger.error(f"Could not get ticker information for {market_symbol}")
        return
    
    current_price = Decimal(ticker.get('last', '0'))
    
    if current_price == 0:
        logger.error(f"Invalid price for {market_symbol}")
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
        order = await exchange.create_market_sell_order(
            symbol=market_symbol,
            amount=float(sell_amount)
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
