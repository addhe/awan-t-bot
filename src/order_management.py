import logging
from typing import Dict, Any, Optional, Tuple
import time
import ccxt

def place_order_with_sl_tp(exchange: ccxt.Exchange, side: str, amount: float,
                          market_price: float, initial_stop_loss_price: float,
                          take_profit_price: float) -> Dict[str, Any]:
    try:
        # Place the main order
        main_order = exchange.create_order(
            symbol=exchange.symbol,
            type='market',
            side=side,
            amount=amount
        )

        # Wait for the main order to be filled
        while True:
            order = exchange.fetch_order(main_order['id'])
            if order['status'] == 'closed':
                break
            time.sleep(1)

        # Place stop loss order
        stop_loss_order = exchange.create_order(
            symbol=exchange.symbol,
            type='stop',
            side='sell' if side == 'buy' else 'buy',
            amount=amount,
            price=initial_stop_loss_price,
            params={'stopPrice': initial_stop_loss_price}
        )

        # Place take profit order
        take_profit_order = exchange.create_order(
            symbol=exchange.symbol,
            type='limit',
            side='sell' if side == 'buy' else 'buy',
            amount=amount,
            price=take_profit_price
        )

        return {
            'main_order': main_order,
            'stop_loss_order': stop_loss_order,
            'take_profit_order': take_profit_order
        }
    except Exception as e:
        logging.error(f"Error placing orders: {e}")
        raise

def set_leverage(exchange: ccxt.Exchange) -> bool:
    try:
        # Get market info
        market = exchange.market(exchange.symbol)

        # Set maximum leverage based on available margin
        max_leverage = min(market['limits']['leverage']['max'], 5)  # Cap at 5x leverage

        # Set leverage
        exchange.set_leverage(max_leverage, exchange.symbol)
        logging.info(f"Leverage set to {max_leverage}x")

        return True
    except Exception as e:
        logging.error(f"Error setting leverage: {e}")
        return False

def check_funding_rate(exchange: ccxt.Exchange, intended_side: Optional[str] = None) -> Dict[str, Any]:
    try:
        # Fetch funding rate
        funding_rate = exchange.fetch_funding_rate(exchange.symbol)

        # Analyze funding rate
        current_rate = funding_rate['fundingRate']
        next_funding_time = funding_rate['fundingTimestamp']

        # Determine if funding rate is favorable
        is_favorable = False
        if intended_side == 'buy':
            is_favorable = current_rate < -0.01  # Favorable for longs if negative
        elif intended_side == 'sell':
            is_favorable = current_rate > 0.01   # Favorable for shorts if positive

        return {
            'current_rate': current_rate,
            'next_funding_time': next_funding_time,
            'is_favorable': is_favorable,
            'should_wait': abs(current_rate) > 0.05  # Wait if funding rate is extreme
        }
    except Exception as e:
        logging.error(f"Error checking funding rate: {e}")
        raise

def handle_order_error(e: Exception, side: str, amount: float) -> Dict[str, Any]:
    error_info = {
        'error_type': type(e).__name__,
        'error_message': str(e),
        'side': side,
        'amount': amount,
        'timestamp': time.time(),
        'requires_retry': False
    }

    if isinstance(e, ccxt.InsufficientFunds):
        error_info['action'] = 'reduce_position_size'
    elif isinstance(e, ccxt.RequestTimeout):
        error_info['requires_retry'] = True
        error_info['retry_delay'] = 5
    else:
        error_info['action'] = 'abort_trade'

    return error_info

def close_position(exchange: ccxt.Exchange, position: Dict[str, Any]) -> Dict[str, Any]:
    try:
        # Close the position
        close_order = exchange.create_order(
            symbol=exchange.symbol,
            type='market',
            side='sell' if position['side'] == 'buy' else 'buy',
            amount=abs(position['amount'])
        )

        # Cancel any existing stop loss or take profit orders
        open_orders = exchange.fetch_open_orders(symbol=exchange.symbol)
        for order in open_orders:
            exchange.cancel_order(order['id'])

        return {
            'success': True,
            'close_order': close_order,
            'position': position
        }
    except Exception as e:
        logging.error(f"Error closing position: {e}")
        return {
            'success': False,
            'error': str(e),
            'position': position
        }
