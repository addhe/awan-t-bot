import logging
from config.config import CONFIG

def cleanup_old_orders(exchange):
    try:
        open_orders = exchange.fetch_open_orders(CONFIG['symbol'])
        for order in open_orders:
            try:
                exchange.cancel_order(order['id'], CONFIG['symbol'])
                logging.info(f"Cancelled old order {order['id']}")
            except Exception as e:
                logging.error(f"Error cancelling order {order['id']}: {e}")
    except Exception as e:
        logging.error(f"Error cleaning up orders: {e}")