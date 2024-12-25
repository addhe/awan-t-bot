import logging
from config.config import CONFIG

from src.modules.cleanup_old_orders import cleanup_old_orders

def emergency_stop(exchange):
    try:
        # Close all positions
        positions = exchange.fetch_positions([CONFIG['symbol']])
        for position in positions:
            if float(position['contracts']) != 0:
                side = 'sell' if float(position['contracts']) > 0 else 'buy'
                exchange.create_market_order(
                    symbol=CONFIG['symbol'],
                    type='market',
                    side=side,
                    amount=abs(float(position['contracts'])),
                    params={'reduceOnly': True}
                )
        
        # Cancel all orders
        cleanup_old_orders(exchange)
        
        logging.critical("Emergency stop executed")
        return True
    except Exception as e:
        logging.error(f"Error in emergency stop: {e}")
        return False