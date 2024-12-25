import logging
from config.config import CONFIG

def fetch_position_details(exchange):
    positions = exchange.fetch_positions([CONFIG['symbol']])
    position_details = {
        'buy': 0,
        'sell': 0,
        'total_buy': 0.0,
        'total_sell': 0.0
    }

    for position in positions:
        position_size = float(position['contracts'])
        if position_size > 0:
            position_details['buy'] += 1
            position_details['total_buy'] += position_size
        elif position_size < 0:
            position_details['sell'] += 1
            position_details['total_sell'] += abs(position_size)

    return position_details