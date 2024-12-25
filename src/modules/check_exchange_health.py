import logging

# Applying more robust checks and alerts to handle critical failures
def check_exchange_health(exchange):
    try:
        # Verify if the exchange is connected and healthy
        exchange.load_markets()
        logging.info("Exchange is healthy")
    except Exception as e:
        logging.critical(f"Exchange failure: {e}")
        raise